# Private iCAP Yellow business implementation. Do not publish.
import re
import difflib
import os
import json
import time
import math
import shutil
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
url = ''
model_name = ''
COORDINATOR_JUDGE_URL = 'http://127.0.0.1:1/unconfigured'
COORDINATOR_JUDGE_API_TOKEN = 'EMPTY'
COORDINATOR_JUDGE_MODEL_NAME = 'gpt-5.6-sol'
COORDINATOR_JUDGE_CONCURRENCY = 8
COORDINATOR_JUDGE_TEMPERATURE = 0.0
COORDINATOR_JUDGE_MAX_RETRIES = 3
COORDINATOR_JUDGE_TIMEOUT = 120
COORDINATOR_JUDGE_OVERLOAD_STOP_THRESHOLD = 5

def model_call(messages, url, model_name, temp):
    import time
    payload = {'model': model_name, 'messages': messages, 'temperature': temp, 'chat_template_kwargs': {'enable_thinking': False}}
    headers = {'Content-Type': 'application/json'}
    start_time = time.time()
    response = requests.request('POST', url, json=payload, headers=headers, verify=True)
    try:
        cleaned = re.sub('```$', '', response.json()['choices'][0]['message']['content'], flags=re.MULTILINE)
        elapsed = time.time() - start_time
        return (elapsed, cleaned)
    except Exception as e:
        print(e)
        print(messages)
        return (-1, response.text)

def process_row(index, row):
    """处理单条数据，返回索引和模型结果。"""

    def _unescape_double_backslash(obj):
        """
        递归清理解析后的对象：将所有字符串值中的 '\\\\' 替换为 '\\'。
        适用于 Excel 中 JSON 字符串二次转义导致的问题。
        """
        if isinstance(obj, str):
            return obj.replace('\\\\', '\\')
        elif isinstance(obj, dict):
            return {k: _unescape_double_backslash(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_unescape_double_backslash(item) for item in obj]
        return obj

    def _parse_json_value(val):
        """
        安全解析 JSON 值（支持字符串或已解析的 dict/list），空值返回 {}。
        解析后会自动将 '\\\\' 替换为 '\\'。
        """
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return {}
        if isinstance(val, dict):
            return _unescape_double_backslash(val)
        if isinstance(val, list):
            return _unescape_double_backslash(val)
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return {}
            try:
                parsed = json.loads(val)
                return _unescape_double_backslash(parsed)
            except json.JSONDecodeError:
                cleaned = _unescape_double_backslash(val)
                return {'content': cleaned}
        return {}
    system_prompt = _parse_json_value(row['system_prompt'])
    skill_desc = _parse_json_value(row['skill_description'])
    memory_info = _parse_json_value(row['memory_location_time'])
    system_parts = []
    content = system_prompt.get('content', '')
    if content:
        system_parts.append(content)
    content = skill_desc.get('content', '')
    if content:
        system_parts.append(content)
    content = memory_info.get('content', '')
    if content:
        system_parts.append(content)
    system_text = '\n\n'.join(system_parts)
    messages = []
    if system_text:
        messages.append({'role': 'system', 'content': system_text})
    user_content_cols = ['query1', 'answer1', 'query2', 'answer2', 'query3', 'answer3', 'query4', 'answer4', 'query5', 'answer5']
    for col in user_content_cols:
        val = _parse_json_value(row[col])
        if val:
            messages.append({'role': 'user', 'content': val.get('content', '')})
    direct_cols = ['user_input', 'assistant_skill_select', 'tool1', 'tool2', 'tool3', 'tool4', 'tool5']
    for col in direct_cols:
        val = _parse_json_value(row[col])
        if val:
            messages.append(val)
    try:
        times, result = model_call(messages=messages, url=url, model_name=model_name, temp=0)
        return {'index': index, 'times': round(times, 2), 'model_output': result, 'error': ''}
    except Exception as e:
        return {'index': index, 'times': '', 'model_output': '', 'error': str(e)}

def atomic_save_excel(df: pd.DataFrame, output_excel_path: str, max_retries: int=5):
    """
    原子写入 Excel:
    先写到临时文件，再替换正式文件，避免中途写坏导致 Excel 打不开。

    Windows 上 os.replace 在目标文件被其他进程占用（如 Excel/WPS 打开、
    杀毒软件或索引服务正在扫描）时会抛出 [WinError 5] 拒绝访问。
    此处加入退避重试；重试仍失败则用 shutil.copy2 覆盖写入目标内容，
    并给出明确提示。
    """
    dir_name = os.path.dirname(output_excel_path) or '.'
    base_name = os.path.basename(output_excel_path)
    tmp_path = os.path.join(dir_name, f'~${base_name}.tmp.xlsx')
    df.to_excel(tmp_path, index=False)
    for attempt in range(1, max_retries + 1):
        try:
            os.replace(tmp_path, output_excel_path)
            return
        except PermissionError:
            if attempt < max_retries:
                time.sleep(attempt * 1.0)
                continue
            try:
                shutil.copy2(tmp_path, output_excel_path)
                os.remove(tmp_path)
                print(f'[WARN] 目标 Excel 文件被其他程序占用，已改用复制覆盖方式写入: {output_excel_path}。若仍失败，请关闭占用该文件的 Excel/WPS 后重试。')
                return
            except Exception:
                print(f'[ERROR] 写入 Excel 失败，临时文件已保留: {tmp_path}，目标文件: {output_excel_path}。文件可能正被其他程序打开，请关闭后重新运行。')
                raise

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
    基于本地数据计算 model_output 与标准答案的相似度评分。
    
    """

    def _parse_json_value(val):
        """安全解析 JSON 值，返回纯文本字符串。"""
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return ''
        if isinstance(val, (dict, list)):
            return json.dumps(val, ensure_ascii=False)
        return str(val).strip()

    def _extract_skill_name(val):
        """
        从 output 中提取 <skill_select>...</skill_select> 里的 skill_name。
        返回 skill_name 字符串，提取失败返回空字符串。
        """
        raw = _parse_json_value(val)
        if not raw:
            return ''
        match = re.search('<skill_select>\\s*(.*?)\\s*</skill_select>', raw, re.DOTALL)
        if not match:
            return ''
        json_str = match.group(1).strip()
        try:
            obj = json.loads(json_str)
            if isinstance(obj, list):
                if not obj:
                    return ''
                skill = obj[0].get('skill_name')
                if skill:
                    return str(skill).strip()
        except (json.JSONDecodeError, AttributeError):
            pass
        return ''

    def _compute_similarity(a: str, b: str) -> float:
        """计算两个字符串的相似度，返回 0.0 ~ 1.0。"""

        def _norm(s: str) -> str:
            s = s.lower().strip()
            s = ' '.join(s.split())
            s = ''.join((c for c in s if c.isalnum() or c.isspace()))
            return s
        a_norm = _norm(a)
        b_norm = _norm(b)
        if not a_norm and (not b_norm):
            return 1.0
        if not a_norm or not b_norm:
            return 0.0
        return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()
    model_output_raw = row.get('model_output', '')
    ground_truth_raw = row.get('ground_truth', '')
    raw_str = _parse_json_value(model_output_raw)
    gt_str = _parse_json_value(ground_truth_raw)
    if '<empty>' == gt_str:
        if '<empty>' == raw_str:
            result = '1'
            reason = '匹配规则: ground_truth 和 model_output 为 <empty>，直接通过'
            raw_response = {'result': result, 'reason': reason}
        else:
            result = '0'
            reason = '匹配规则: ground_truth 为 <empty>，但 model_output 非 <empty>'
            raw_response = {'result': result, 'reason': reason}
    elif gt_str.startswith('<skill_select>'):
        gt_skill_name = _extract_skill_name(ground_truth_raw)
        raw_skill_name = _extract_skill_name(model_output_raw)
        if gt_skill_name == raw_skill_name:
            result = '1'
            reason = f'匹配规则: model_output 包含 skill_name ({gt_skill_name})，直接通过'
            raw_response = {'result': result, 'reason': reason}
        else:
            result = '0'
            reason = f'匹配规则: model_output 输出 ({raw_skill_name})，与 ground_truth 的 ({gt_skill_name}) 不符'
            raw_response = {'result': result, 'reason': reason}
    else:
        similarity = _compute_similarity(raw_str, gt_str)
        threshold = 0.3
        if similarity >= threshold:
            result = '1'
        else:
            result = '0'
        reason = f"相似度: {similarity:.2%} | 模型输出({len(raw_str)}字) vs 标准答案({len(gt_str)}字) | 判定: {('通过' if similarity >= threshold else '未通过')}"
        raw_response = {'result': result, 'reason': reason}
    return {'pos': pos, 'original_idx': original_idx, 'raw_response': raw_response, 'result': result, 'reason': reason, 'success': True, 'is_overload': False}

def evaluate_dataframe(df: pd.DataFrame, judge_url: str, api_token: str, judge_model_name: str, output_excel_path: str, concurrency: int=5, temperature: float=0.0, max_retries: int=3, timeout: int=120, overload_stop_threshold: int=None):
    required_cols = ['query1', 'answer5', 'system_prompt', 'skill_description', 'memory_location_time', 'user_input', 'assistant_skill_select', 'tool3', 'ground_truth', 'model_output']
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
            output_df.at[original_idx, 'raw_response'] = str(item['raw_response'])
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
    history = history[-10:]
    return history
