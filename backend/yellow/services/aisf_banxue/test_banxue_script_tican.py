# Private iCAP Yellow business implementation. Do not publish.
import re
import os
import json
import time
import math
import ast
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
url = 'http://127.0.0.1:1/unconfigured'
model_name = 'Qwen3-8B'
max_workers = 4

def model_call(messages, url, model_name, temp):
    import time
    payload = {'model': model_name, 'messages': messages, 'temperature': temp, 'chat_template_kwargs': {'enable_thinking': False}}
    headers = {'Content-Type': 'application/json'}
    start_time = time.time()
    response = requests.request('POST', url, json=payload, headers=headers, verify=True)
    try:
        data = response.json()
        cleaned = re.sub('```$', '', data['choices'][0]['message']['content'], flags=re.MULTILINE)
        elapsed = time.time() - start_time
        usage = data.get('usage') or {}
        prompt_tokens = usage.get('prompt_tokens', 0) or 0
        completion_tokens = usage.get('completion_tokens', 0) or 0
        return (elapsed, cleaned, prompt_tokens, completion_tokens)
    except Exception as e:
        print(e)
        return (-1, response.text, 0, 0)

def process_row(index, row):
    """处理单条数据，返回索引和模型结果。"""
    messages = [{'role': 'system', 'content': row['system_prompt']}, {'role': 'user', 'content': row['input']}]
    try:
        times, result, prompt_tokens, completion_tokens = model_call(messages=messages, url=url, model_name=model_name, temp=0)
        return {'index': index, 'times': round(times, 2), 'model_output': result, 'prompt_tokens': int(prompt_tokens), 'completion_tokens': int(completion_tokens), 'error': ''}
    except Exception as e:
        return {'index': index, 'times': '', 'model_output': '', 'prompt_tokens': 0, 'completion_tokens': 0, 'error': str(e)}

def atomic_save_excel(df: pd.DataFrame, output_excel_path: str):
    """
    原子写入 Excel:
    先写到临时文件，再替换正式文件，避免中途写坏导致 Excel 打不开。
    """
    dir_name = os.path.dirname(output_excel_path) or '.'
    base_name = os.path.basename(output_excel_path)
    tmp_path = os.path.join(dir_name, f'~${base_name}.tmp.xlsx')
    df.to_excel(tmp_path, index=False)
    os.replace(tmp_path, output_excel_path)

def is_overload_error(error_msg: str) -> bool:
    """
    判断是否属于“访问过多/限流/服务繁忙”类错误。
    """
    if not error_msg:
        return False
    msg = str(error_msg).lower()
    keywords = ['429', 'rate limit', 'too many requests', 'quota', 'exceeded', 'overloaded', 'server is busy', 'service unavailable', 'temporarily unavailable', 'try again later', '请求过于频繁', '访问过多', '限流', '频率过高', '服务繁忙']
    return any((k in msg for k in keywords))

def call_openai_compatible_model(messages: list, judge_url: str, api_token: str, judge_model_name: str, temperature: float=0.0, max_retries: int=3, timeout: int=120, row_idx=None):
    """
    调用 OpenAI 兼容格式的 Judge 模型接口。

    messages 由调用方完整构造，当前格式为：
    1. judge_system_prompt：system
    2. 格式化后的 judge_user_prompt_template：第一个 user
    3. judge_user_prompt：第二个 user
    """

    def log(msg: str):
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        prefix = f'[{now}]'
        if row_idx is not None:
            prefix += f' [row={row_idx}]'
        print(f'{prefix} {msg}')
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_token}'}
    payload = {'model': judge_model_name, 'messages': messages, 'temperature': temperature}
    last_error = None
    for attempt in range(1, max_retries + 1):
        response = None
        try:
            log(f'开始请求 Judge 模型，第 {attempt}/{max_retries} 次，model={judge_model_name}, judge_url={judge_url}')
            response = requests.post(judge_url, headers=headers, json=payload, timeout=timeout, verify=True, allow_redirects=False)
            log(f'收到HTTP响应，status_code={response.status_code}')
            response.raise_for_status()
            data = response.json()
            if 'error' in data and data['error']:
                error_info = data['error']
                if isinstance(error_info, dict):
                    error_msg = error_info.get('message', str(error_info))
                else:
                    error_msg = str(error_info)
                log(f'API返回报错: {error_msg}')
                last_error = error_msg
                if attempt < max_retries:
                    sleep_s = 2 ** (attempt - 1)
                    log(f'准备重试，{sleep_s} 秒后发起下一次请求')
                    time.sleep(sleep_s)
                    continue
                return {'success': False, 'raw_content': '', 'error': error_msg}
            raw_content = data['choices'][0]['message']['content']
            log('请求成功，已拿到 Judge 模型返回内容')
            return {'success': True, 'raw_content': raw_content, 'error': ''}
        except requests.exceptions.HTTPError as e:
            try:
                err_text = response.text if response is not None else str(e)
            except Exception:
                err_text = str(e)
            last_error = f'HTTP错误: {str(e)} | 响应内容: {err_text}'
            log(f'API返回报错: {last_error}')
        except requests.exceptions.Timeout as e:
            last_error = f'请求超时: {str(e)}'
            log(f'API返回报错: {last_error}')
        except requests.exceptions.RequestException as e:
            last_error = f'请求异常: {str(e)}'
            log(f'API返回报错: {last_error}')
        except Exception as e:
            last_error = f'其他异常: {str(e)}'
            log(f'API返回报错: {last_error}')
        if attempt < max_retries:
            sleep_s = 2 ** (attempt - 1)
            log(f'准备重试，{sleep_s} 秒后发起下一次请求')
            time.sleep(sleep_s)
        else:
            log('达到最大重试次数，请求失败')
            return {'success': False, 'raw_content': '', 'error': last_error or '未知错误'}

def safe_text(value) -> str:
    """将 Excel 单元格安全转换为字符串，NaN 转为空字符串。"""
    if pd.isna(value):
        return ''
    return str(value)

def build_judge_template_prompt(row: pd.Series) -> str:
    """
    格式化 judge_user_prompt_template。

    Excel 模板使用双大括号，例如：{{system_prompt}}，因此这里显式替换，
    不使用 str.format()，避免双大括号被识别为普通文本。
    """
    template = safe_text(row['judge_user_prompt_template'])
    replacements = {'system_prompt': safe_text(row['system_prompt']), 'input': safe_text(row['input']), 'ground_truth': safe_text(row['ground_truth']), 'model_output': safe_text(row['model_output'])}
    for key, value in replacements.items():
        template = template.replace('{{' + key + '}}', value)
    return template

def parse_model_output(raw_content: str):
    """
    解析 Judge 模型返回，目标格式：
    {"result": "0/1", "reason": "空/错误理由"}

    同时兼容 result 为整数 0/1，并自动移除 ```json 代码块。
    """
    try:
        cleaned = safe_text(raw_content).strip()
        cleaned = re.sub('^```(?:json)?\\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub('\\s*```$', '', cleaned).strip()
        obj = json.loads(cleaned)
        result = str(obj.get('result', '0')).strip()
        reason = obj.get('reason', obj.get('reaosn', ''))
        if result not in {'0', '1'}:
            result = '0'
            reason = f'result字段非法；{reason}' if reason else 'result字段非法'
        if not isinstance(reason, str):
            reason = str(reason)
        return (result, reason)
    except Exception as e:
        return ('0', f'解析错误: {str(e)}')

def evaluate_single_row(pos: int, original_idx, row: pd.Series, judge_url: str, api_token: str, judge_model_name: str, temperature: float, max_retries: int, timeout: int):
    """
    并发处理单条 Judge 样本：
    1. row["judge_system_prompt"] 作为 system prompt；
    2. 格式化后的 row["judge_user_prompt_template"] 作为第一个 user prompt；
    3. row["judge_user_prompt"] 作为第二个 user prompt；
    4. 解析 {"result": "0/1", "reason": "..."}。
    """
    messages = [{'role': 'system', 'content': safe_text(row['judge_system_prompt'])}, {'role': 'user', 'content': build_judge_template_prompt(row)}, {'role': 'user', 'content': safe_text(row['judge_user_prompt'])}]
    call_result = call_openai_compatible_model(messages=messages, judge_url=judge_url, api_token=api_token, judge_model_name=judge_model_name, temperature=temperature, max_retries=max_retries, timeout=timeout, row_idx=original_idx)
    if not call_result['success']:
        return {'pos': pos, 'original_idx': original_idx, 'raw_response': '', 'result': '0', 'reason': f"请求错误: {call_result['error']}", 'success': False, 'is_overload': is_overload_error(call_result['error'])}
    raw_content = call_result['raw_content']
    result, reason = parse_model_output(raw_content)
    return {'pos': pos, 'original_idx': original_idx, 'raw_response': raw_content, 'result': result, 'reason': reason, 'success': True, 'is_overload': False}

def evaluate_dataframe(df: pd.DataFrame, judge_url: str, api_token: str, judge_model_name: str, output_excel_path: str, concurrency: int=5, temperature: float=0.0, max_retries: int=3, timeout: int=120, overload_stop_threshold: int=None):
    required_cols = ['judge_system_prompt', 'judge_user_prompt_template', 'judge_user_prompt', 'system_prompt', 'input', 'ground_truth', 'model_output']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f'df缺少必要列: {col}')
    output_df = df.copy()
    if 'raw_response' not in output_df.columns:
        output_df['raw_response'] = ''
    if 'result' not in output_df.columns:
        output_df['result'] = ''
    if 'reason' not in output_df.columns:
        output_df['reason'] = ''
    if 'status' not in output_df.columns:
        output_df['status'] = 'pending'
    atomic_save_excel(output_df, output_excel_path)
    total = len(output_df)
    completed = 0
    if overload_stop_threshold is None:
        overload_stop_threshold = max(1, math.ceil(concurrency / 2))
    all_tasks = list(enumerate(output_df.iterrows()))
    stop_early = False
    for batch_start in range(0, len(all_tasks), concurrency):
        batch = all_tasks[batch_start:batch_start + concurrency]
        batch_id = batch_start // concurrency + 1
        batch_size = len(batch)
        print(f'\n[主线程] 开始第 {batch_id} 批，请求数={batch_size}')
        batch_results = []
        batch_overload_errors = 0
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = []
            for pos, (original_idx, row) in batch:
                future = executor.submit(evaluate_single_row, pos, original_idx, row, judge_url, api_token, judge_model_name, temperature, max_retries, timeout)
                futures.append(future)
            for future in as_completed(futures):
                item = future.result()
                batch_results.append(item)
                if item['is_overload']:
                    batch_overload_errors += 1
        for item in batch_results:
            original_idx = item['original_idx']
            output_df.at[original_idx, 'raw_response'] = item['raw_response']
            output_df.at[original_idx, 'result'] = str(item['result'])
            output_df.at[original_idx, 'reason'] = str(item['reason'])
            output_df.at[original_idx, 'status'] = 'done' if item['success'] else 'failed'
            completed += 1
        print(f'[主线程] 第 {batch_id} 批完成，batch_overload_errors={batch_overload_errors}，累计完成={completed}/{total}，准备统一写入 Excel')
        atomic_save_excel(output_df, output_excel_path)
        print(f'[主线程] 第 {batch_id} 批结果已安全写入: {output_excel_path}')
        if batch_overload_errors >= overload_stop_threshold:
            print(f'[主线程] 检测到当前批次 overload 错误过多 ({batch_overload_errors} >= {overload_stop_threshold})，提前终止程序。')
            stop_early = True
            break
    if stop_early:
        print(f'[主线程] 已提前终止，但当前结果已安全保存到: {output_excel_path}')
    else:
        print(f'[主线程] 全部完成，结果已保存到: {output_excel_path}')
    return output_df

def build_history(row):
    history = []
    for i in range(1, 100):
        q_col = f'query{i}'
        a_col = f'answer{i}'
        if q_col in row and pd.notna(row[q_col]):
            history.append({'role': 'user', 'content': str(row[q_col])})
        if a_col in row and pd.notna(row[a_col]):
            history.append({'role': 'assistant', 'content': str(row[a_col])})
    history = history[-6:]
    return history

def judge(ground_truth, model_output):
    """
    输入格式：
    [
        {"studyDuration": 60},
        {"breakCount": 2},
        {"breakDuration": 5}
    ]

    返回：
    {
        "result": "0/1",
        "reason": "错误原因"
    }
    """
    try:
        if isinstance(ground_truth, str):
            ground_truth = ast.literal_eval(ground_truth)
        if isinstance(model_output, str):
            model_output = ast.literal_eval(model_output)
            model_output = {k: v for k, v in model_output.items() if v != ''}
    except:
        return {'result': '0', 'reason': '模型输出解析失败'}
    missing_params = [key for key in ground_truth if key not in model_output]
    wrong_params = [key for key in ground_truth if key in model_output and ground_truth[key] != model_output[key]]
    extra_params = [key for key in model_output if key not in ground_truth]
    if not missing_params and (not wrong_params) and (not extra_params):
        return {'result': '1', 'reason': ''}
    reasons = []
    if missing_params:
        reasons.append('缺失参数：' + '、'.join(missing_params))
    if wrong_params:
        reasons.append('参数值错误：' + '、'.join((f'{key}（期望={ground_truth[key]}，实际={model_output[key]}）' for key in wrong_params)))
    if extra_params:
        reasons.append('多余参数：' + '、'.join(extra_params))
    return {'result': '0', 'reason': '\n'.join(reasons)}
