# Private iCAP Yellow business implementation. Do not publish.
import os
import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))
import requests
import pandas as pd
from services.multi_ruler2.aisf_yitu.system_prompt import skill_select_sys_prompt as sys_prompt
from services.multi_ruler2.aisf_yitu.skill_description import tunnel_A_skill_description, tunnel_B_skill_description
import time
import json
import re
import ast
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import warnings
import threading
from datetime import datetime
from services import logger
from utils.io_utils import dump_jsonl_data, DumpMode
thread_controls = {}
thread_controls_lock = threading.Lock()

class _TaskLogger:
    """任务级日志器：持有独立文件句柄，文件名固定为 eval_log.log。

    与 memory / gaixie 业务的日志方式一致（任务私有文件），
    同时避免 services.Logger 依赖 logging 同名单例导致的并发串写。
    """

    def __init__(self, log_dir):
        os.makedirs(log_dir, exist_ok=True)
        self._f = open(os.path.join(log_dir, 'eval_log.log'), 'w', encoding='utf-8')
        self._f.write(f'[{datetime.now()}] eval_log 启动\n\n')
        self._f.flush()

    def info(self, msg):
        self._f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self._f.flush()

    def error(self, msg):
        self.info(msg)

    def close(self):
        try:
            self._f.close()
        except Exception:
            pass

def pause_thread(thread_id):
    """暂停指定线程的任务提交"""
    with thread_controls_lock:
        if thread_id in thread_controls:
            thread_controls[thread_id]['paused'] = True
            logger.global_logger.info(f'Thread {thread_id} paused. Current tasks will complete, but no new tasks will be submitted.')
        else:
            logger.global_logger.info(f'Thread control for {thread_id} not found')

def resume_thread(thread_id):
    """恢复指定线程的任务提交"""
    with thread_controls_lock:
        if thread_id in thread_controls:
            thread_controls[thread_id]['paused'] = False
            with thread_controls[thread_id]['condition']:
                thread_controls[thread_id]['condition'].notify_all()
            logger.global_logger.info(f'Thread {thread_id} resumed')
        else:
            logger.global_logger.info(f'Thread control for {thread_id} not found')
warnings.filterwarnings('ignore')

def qwen_32b(messages, url, model_name, temp, api_key, logger=None):
    _L = logger or logger.global_logger
    if isinstance(api_key, tuple):
        auth_string = api_key[0]
    else:
        auth_string = api_key
    if auth_string is None or auth_string == 'EMPTY' or auth_string == '':
        auth_string = None
    if model_name.startswith('openpangu-2.0'):
        payload = {'model': model_name, 'messages': messages, 'temperature': temp, 'thinking': {'type': 'disabled'}}
    else:
        payload = {'model': model_name, 'messages': messages, 'temperature': temp, 'chat_template_kwargs': {'enable_thinking': False}}
    if auth_string is not None and auth_string != 'EMPTY' and (auth_string != ''):
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {auth_string}'}
    else:
        headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, json=payload, headers=headers, verify=True, timeout=360)
        response.raise_for_status()
        response_data = response.json()
        content = response_data['choices'][0]['message']['content']
        token_usage = response_data.get('usage', {})
        cleaned = re.sub('```(?:json|python)?\\s*([\\s\\S]*?)```', '\\1', content, flags=re.MULTILINE).strip()
        array_match = re.search('(\\[.*\\])', cleaned, re.DOTALL)
        if array_match:
            cleaned = array_match.group(1)
        elif cleaned.strip().startswith('{') and 'skill_name' in cleaned:
            candidate = cleaned.strip()
            candidate = candidate.rstrip(',').rstrip()
            wrapped = f'[{candidate}]'
            try:
                json.loads(wrapped)
                cleaned = wrapped
            except (json.JSONDecodeError, Exception):
                pass
        return (cleaned, token_usage)
    except Exception as e:
        _L.error(f'请求失败: {e}')
        try:
            if 'response' in locals():
                return (response.text, {})
            else:
                return (str(e), {})
        except Exception:
            return (str(e), {})

def parse_LLM_output(LLM_output, logger=None):
    _L = logger or logger.global_logger
    '\n    解析LLM输出，双重兜底：\n    1. 优先 json.loads（标准JSON），处理 true/false/null\n    2. 失败后尝试 ast.literal_eval（Python风格 True/False/None）\n    3. 如果返回的是单个 dict，包装为 list\n    '
    if not LLM_output or not LLM_output.strip():
        _L.info('model answer is empty')
        return None
    text = LLM_output.strip()
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return [result]
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    try:
        result = ast.literal_eval(text)
        if isinstance(result, dict):
            return [result]
        if isinstance(result, list):
            return result
        _L.error(f'model answer type wrong: {result}')
        return None
    except Exception as e:
        _L.error(f'model answer format wrong: {e}')
    try:
        array_match = re.search('(\\[.*\\])', text, re.DOTALL)
        if array_match:
            candidate = array_match.group(1)
            try:
                result = json.loads(candidate)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass
            try:
                result = ast.literal_eval(candidate)
                if isinstance(result, list):
                    return result
            except Exception:
                pass
    except Exception:
        pass
    try:
        text_stripped = text.strip()
        if text_stripped.startswith('{') and 'skill_name' in text_stripped:
            candidate = text_stripped.rstrip(',').rstrip()
            wrapped = f'[{candidate}]'
            try:
                result = json.loads(wrapped)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass
            try:
                result = ast.literal_eval(wrapped)
                if isinstance(result, list):
                    return result
            except Exception:
                pass
    except Exception:
        pass
    return None

def judge(A_evaluate, A_star, logger=None):
    _L = logger or logger.global_logger
    try:
        if not A_evaluate and (not A_star):
            return True
        if not isinstance(A_evaluate, list) or not isinstance(A_star, list):
            return False
        if A_evaluate == A_star:
            return True
        elif len(A_evaluate) == len(A_star):
            intents_num = len(A_evaluate)
            for i in range(intents_num):
                A_evaluate_intent, A_star_intent = (A_evaluate[i], A_star[i])
                A_evaluate_intent_name = A_evaluate_intent['skill_name']
                A_evaluate_intent_param = A_evaluate_intent['depends_on']
                A_star_intent_name = A_star_intent['skill_name']
                A_star_intent_param = A_star_intent['depends_on']
                if A_evaluate_intent_name != A_star_intent_name:
                    return False
                if A_evaluate_intent_param != A_star_intent_param:
                    return False
            return True
        else:
            return False
    except Exception as e:
        _L.error(f'judge错误: {e}')
        return False

def build_history(row):
    history = []
    for i in range(1, 100):
        q_col = f'query{i}'
        a_col = f'answer{i}'
        if q_col in row and pd.notna(row[q_col]):
            history.append({'role': 'user', 'content': str(row[q_col])})
        if a_col in row and pd.notna(row[a_col]):
            history.append({'role': 'assistant', 'content': str(row[a_col])})
    return history

def build_messages(cur_query, history, skill_description, system_prompt):
    merged_system = system_prompt + '\n\n# 可用助手描述\n' + '# 可用助手描述\n{{skill_description}}'.replace('{{skill_description}}', skill_description)
    messages = [{'role': 'system', 'content': merged_system}]
    messages.extend(history)
    messages.append({'role': 'user', 'content': '# 用户输入\n{{user_input}}'.replace('{{user_input}}', str(cur_query))})
    return messages

def clean_result(parsed_result, fallback_skill_name):
    if not isinstance(parsed_result, list):
        return []
    return [each for each in parsed_result if isinstance(each, dict) and each.get('skill_name') and (each.get('skill_name') != fallback_skill_name)]

def parse_expected_output(value, logger=None):
    _L = logger or logger.global_logger
    try:
        if pd.isna(value):
            return []
        return ast.literal_eval(str(value))
    except Exception as e:
        _L.error(f'expected_output解析失败: {e}, value={value}')
        return []

def process_one_sample(index, row, url, model_name, temp, api_key, system_prompt, logger=None):
    """
    一个样本内部串行：
    1. 请求A通道
    2. 请求B通道

    多个样本之间由线程池并行。
    """
    _L = logger or logger.global_logger
    try:
        cur_query = row['cur_query']
        history = build_history(row)
        _L.info(f'***********开始处理第 {index} 条**************')
        _L.info(f'用户问题：{cur_query}')
        messages_A = build_messages(cur_query=cur_query, history=history, skill_description=tunnel_A_skill_description, system_prompt=system_prompt)
        start_time_A = time.time()
        resultA, token_usage_A = qwen_32b(messages_A, url, model_name, temp, api_key, logger=_L)
        end_time_A = time.time()
        cost_time_A = end_time_A - start_time_A
        messages_B = build_messages(cur_query=cur_query, history=history, skill_description=tunnel_B_skill_description, system_prompt=system_prompt)
        start_time_B = time.time()
        resultB, token_usage_B = qwen_32b(messages_B, url, model_name, temp, api_key, logger=_L)
        end_time_B = time.time()
        cost_time_B = end_time_B - start_time_B
        _L.info(f'通道A原始返回（前200字）: {resultA[:200]}')
        _L.info(f'通道B原始返回（前200字）: {resultB[:200]}')
        resultA_parse = parse_LLM_output(resultA, logger=_L)
        resultB_parse = parse_LLM_output(resultB, logger=_L)
        _L.info(f'通道A解析结果：{resultA_parse}')
        _L.info(f'通道B解析结果：{resultB_parse}')
        tunnel_A_clean_result = clean_result(resultA_parse, 'fallback-c')
        tunnel_B_clean_result = clean_result(resultB_parse, 'fallback-a')
        expected_output_A = parse_expected_output(row['expected_output_A'], logger=_L)
        expected_output_B = parse_expected_output(row['expected_output_B'], logger=_L)
        tunnel_A_is_right = '1' if judge(tunnel_A_clean_result, expected_output_A, logger=_L) else '0'
        tunnel_B_is_right = '1' if judge(tunnel_B_clean_result, expected_output_B, logger=_L) else '0'
        _L.info(f'第 {index} 条处理完成')
        _L.info(f'通道A输出结果：{tunnel_A_clean_result}')
        _L.info(f'通道B输出结果：{tunnel_B_clean_result}')
        token_usage_A_dict = token_usage_A if isinstance(token_usage_A, dict) else {}
        token_usage_B_dict = token_usage_B if isinstance(token_usage_B, dict) else {}
        return {'index': index, 'messages_A': json.dumps(messages_A, ensure_ascii=False), 'messages_B': json.dumps(messages_B, ensure_ascii=False), 'tunnel_A_result': resultA, 'tunnel_B_result': resultB, 'tunnel_A_clean_result': str(tunnel_A_clean_result), 'tunnel_B_clean_result': str(tunnel_B_clean_result), 'tunnel_A_is_right': tunnel_A_is_right, 'tunnel_B_is_right': tunnel_B_is_right, 'tunnel_A_prompt_tokens': token_usage_A_dict.get('prompt_tokens', 0), 'tunnel_A_completion_tokens': token_usage_A_dict.get('completion_tokens', 0), 'tunnel_A_total_tokens': token_usage_A_dict.get('total_tokens', 0), 'tunnel_A_cost_time': cost_time_A, 'tunnel_B_prompt_tokens': token_usage_B_dict.get('prompt_tokens', 0), 'tunnel_B_completion_tokens': token_usage_B_dict.get('completion_tokens', 0), 'tunnel_B_total_tokens': token_usage_B_dict.get('total_tokens', 0), 'tunnel_B_cost_time': cost_time_B, 'error': ''}
    except Exception as e:
        error_msg = traceback.format_exc()
        _L.error(f'第 {index} 条处理失败: {e}')
        _L.error(error_msg)
        return {'index': index, 'messages_A': '', 'messages_B': '', 'tunnel_A_result': '', 'tunnel_B_result': '', 'tunnel_A_clean_result': '', 'tunnel_B_clean_result': '', 'tunnel_A_is_right': '0', 'tunnel_B_is_right': '0', 'tunnel_A_prompt_tokens': 0, 'tunnel_A_completion_tokens': 0, 'tunnel_A_total_tokens': 0, 'tunnel_A_cost_time': 0, 'tunnel_B_prompt_tokens': 0, 'tunnel_B_completion_tokens': 0, 'tunnel_B_total_tokens': 0, 'tunnel_B_cost_time': 0, 'error': error_msg}

def gen_review_jsonl(combined_data, review_path, dataset_name, subset_name='default', logger=None):
    """
    生成jsonl评审文件，每条数据包含A/B两个通道的完整信息。
    参考outfit项目gen_review_jsonl模式。
    """
    review_lines = []
    for index, item in enumerate(combined_data):
        review_lines.append({'raw_input': {'Question': item['query'], 'expected_A': item['expected_A'], 'expected_B': item['expected_B'], 'No': index}, 'choices': [{'review': {'gold': item['expected_A'], 'pred': item['clean_result_A'], 'result': item['is_right_A'], 'tunnel': 'tunnel_A'}, 'message': {'content': item['model_answer_raw_A']}}, {'review': {'gold': item['expected_B'], 'pred': item['clean_result_B'], 'result': item['is_right_B'], 'tunnel': 'tunnel_B'}, 'message': {'content': item['model_answer_raw_B']}}], 'index': index, 'subset_name': subset_name, 'usage': item['token统计'], 'response_time': item['处理时间']})
    review_file = os.path.join(review_path, f'{dataset_name}_{subset_name}.jsonl')
    dump_jsonl_data(review_lines, review_file, dump_mode=DumpMode.OVERWRITE)
    (logger or logger.global_logger).info(f'已生成review jsonl: {review_file}')

def gen_report_json(model_name, dataset_name, report_path, acc_A, acc_B, acc_both, total_count, df=None, logger=None):
    """生成测评报告json，参考outfit项目gen_report_json模式"""
    subsets = []
    if df is not None and 'intent_count' in df.columns:
        intent_labels = {1: '单意图', 2: '两意图', 3: '三意图'}
        for intent_val in [1, 2, 3]:
            subset_df = df[df['intent_count'] == intent_val]
            subset_total = len(subset_df)
            if subset_total > 0:
                subset_suc_both = sum((1 for _, r in subset_df.iterrows() if r.get('tunnel_A_is_right', '0') == '1' and r.get('tunnel_B_is_right', '0') == '1'))
                subset_score = subset_suc_both / subset_total
            else:
                subset_suc_both = 0
                subset_score = 0
            subsets.append({'name': intent_labels.get(intent_val, str(intent_val)), 'num': subset_total, 'score': subset_score, 'correct_num': subset_suc_both})
    else:
        subsets.append({'name': 'default', 'num': total_count, 'score': acc_both, 'correct_num': int(total_count * acc_both)})
    report_map = {'name': f'{model_name}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_name, 'score': acc_both, 'metrics': [{'categories': [{'macro_score': acc_both, 'name': ['tunnel_A_and_B'], 'num': total_count, 'score': acc_both, 'subsets': subsets}], 'macro_score': acc_both, 'name': '双通道均正确', 'num': total_count, 'score': acc_both}]}
    report_path_file = os.path.join(report_path, f'{dataset_name}.json')
    os.makedirs(os.path.dirname(report_path_file), exist_ok=True)
    with open(report_path_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report_map, ensure_ascii=False, indent=4))
    (logger or logger.global_logger).info(f'已生成报告json: {report_path_file}')

def run_pipeline(task_id, input_path, output_path, url, model_name, model_id, api_key, system_prompt, temp, dataset_name, MAX_WORKERS=2, LIMIT=None, SAVE_EVERY=10, thread_id=None, retry_content_none=False, retry_enabled=False):
    """
    主执行逻辑：读取excel -> 多线程处理(支持暂停/恢复) -> 保存excel结果 -> 生成jsonl/review文件
    output_path: 本次测评任务目录
    thread_id: 线程控制ID（用于暂停/恢复）
    retry_content_none: True=内容续测（内容为空的重新生成），False=索引续测
    retry_enabled: 是否启用续测（use_cache + retry_content_none 显式传入时置True）
    """
    if not system_prompt:
        system_prompt = sys_prompt
    config = {'task_id': task_id, 'input_path': input_path, 'output_path': output_path, 'url': url, 'model_name': model_name, 'api_key': api_key, 'system_prompt': system_prompt, 'temp': temp, 'dataset_name': dataset_name, 'MAX_WORKERS': MAX_WORKERS, 'LIMIT': LIMIT, 'SAVE_EVERY': SAVE_EVERY, 'thread_id': thread_id}
    formatted_config = json.dumps(config, indent=2, ensure_ascii=False)
    review_dir = os.path.join(output_path, 'reviews', model_id)
    report_dir = os.path.join(output_path, 'reports', model_id)
    os.makedirs(review_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)
    out_file = os.path.join(review_dir, f'{dataset_name}_{task_id}.xlsx')
    log_path = os.path.join(output_path, 'logs')
    task_logger = _TaskLogger(log_path)
    logger.global_logger = task_logger
    task_logger.info(f'开始模型评测: {model_id}')
    task_logger.info(f'**** Start evaluating on AISF-意图 ****')
    task_logger.info(f'任务参数: \n{formatted_config}')
    df = pd.read_excel(input_path, sheet_name='Sheet1')
    if LIMIT is not None:
        df = df.head(LIMIT)
        task_logger.info(f'已限制执行前 {LIMIT} 条用例')
    output_columns = ['messages_A', 'messages_B', 'tunnel_A_result', 'tunnel_B_result', 'tunnel_A_clean_result', 'tunnel_B_clean_result', 'tunnel_A_is_right', 'tunnel_B_is_right', 'error']
    for col in output_columns:
        if col not in df.columns:
            df[col] = ''
    if thread_id:
        with thread_controls_lock:
            thread_controls[thread_id] = {'paused': False, 'condition': threading.Condition()}
    done_idx_set = set()
    if retry_enabled and os.path.exists(out_file):
        try:
            prev_df = pd.read_excel(out_file, sheet_name='Sheet1')
            for prev_idx, prow in prev_df.iterrows():
                if prev_idx >= len(df):
                    continue
                tunnel_a = str(prow.get('tunnel_A_result') or '').strip()
                tunnel_b = str(prow.get('tunnel_B_result') or '').strip()
                if not tunnel_a or not tunnel_b:
                    continue
                if retry_content_none:
                    clean_a = str(prow.get('tunnel_A_clean_result') or '').strip()
                    clean_b = str(prow.get('tunnel_B_clean_result') or '').strip()
                    if not clean_a or not clean_b:
                        continue
                for col in output_columns:
                    df.loc[prev_idx, col] = prow.get(col, '')
                done_idx_set.add(prev_idx)
            task_logger.info(f'续测：复用旧结果 {len(done_idx_set)} 行')
        except Exception as e:
            task_logger.warning(f'续测：读取旧结果Excel失败({out_file})，将全量重跑：{e}')
            done_idx_set = set()
    pending_tasks = [(i, r) for i, r in df.iterrows() if i not in done_idx_set]
    total_tasks = len(pending_tasks)
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    active_futures = {}
    finished_count = 0
    try:
        while pending_tasks or active_futures:
            is_paused = False
            if thread_id:
                with thread_controls_lock:
                    control_info = thread_controls.get(thread_id, {'paused': False})
                    is_paused = control_info['paused']
            done_futures = []
            for future in list(active_futures.keys()):
                if future.done():
                    done_futures.append(future)
            for future in done_futures:
                idx, _ = active_futures.pop(future)
                result = future.result()
                for col in output_columns:
                    df.loc[idx, col] = result[col]
                finished_count += 1
                task_logger.info(f'当前已完成: {finished_count}/{total_tasks}')
                if finished_count % SAVE_EVERY == 0:
                    df.to_excel(out_file, index=False)
                    task_logger.info(f'已保存中间结果: {out_file}')
            if is_paused:
                time.sleep(0.5)
                continue
            while pending_tasks and len(active_futures) < MAX_WORKERS:
                index, row = pending_tasks.pop(0)
                future = executor.submit(process_one_sample, index, row, url, model_name, temp, api_key, system_prompt, task_logger)
                active_futures[future] = (index, row)
            if active_futures:
                done, _ = concurrent.futures.wait(list(active_futures.keys()), timeout=0.5, return_when=concurrent.futures.FIRST_COMPLETED)
            else:
                time.sleep(0.1)
    finally:
        executor.shutdown(wait=True)
    df.to_excel(out_file, index=False)
    task_logger.info(f'全部完成，最终结果已保存: {out_file}')
    task_logger.info('**** 开始生成review jsonl与report ****')
    total = len(df)
    combined_data = []
    suc_A = 0
    suc_B = 0
    suc_both = 0
    for _, row in df.iterrows():
        is_right_A = row.get('tunnel_A_is_right', '0')
        is_right_B = row.get('tunnel_B_is_right', '0')
        token_total = {'prompt_tokens': int(row.get('tunnel_A_prompt_tokens', 0)) + int(row.get('tunnel_B_prompt_tokens', 0)), 'completion_tokens': int(row.get('tunnel_A_completion_tokens', 0)) + int(row.get('tunnel_B_completion_tokens', 0)), 'total_tokens': int(row.get('tunnel_A_total_tokens', 0)) + int(row.get('tunnel_B_total_tokens', 0))}
        cost_time_total = float(row.get('tunnel_A_cost_time', 0)) + float(row.get('tunnel_B_cost_time', 0))
        combined_data.append({'query': row.get('cur_query', ''), 'expected_A': str(row.get('expected_output_A', '')), 'expected_B': str(row.get('expected_output_B', '')), 'model_answer_raw_A': row.get('tunnel_A_result', ''), 'model_answer_raw_B': row.get('tunnel_B_result', ''), 'clean_result_A': row.get('tunnel_A_clean_result', ''), 'clean_result_B': row.get('tunnel_B_clean_result', ''), 'is_right_A': is_right_A, 'is_right_B': is_right_B, 'token统计': token_total, '处理时间': cost_time_total})
        if is_right_A == '1':
            suc_A += 1
        if is_right_B == '1':
            suc_B += 1
        if is_right_A == '1' and is_right_B == '1':
            suc_both += 1
    acc_A = suc_A / total if total > 0 else 0
    acc_B = suc_B / total if total > 0 else 0
    acc_both = suc_both / total if total > 0 else 0
    task_logger.info(f'通道A准确率: {suc_A}/{total} = {acc_A:.4f}')
    task_logger.info(f'通道B准确率: {suc_B}/{total} = {acc_B:.4f}')
    task_logger.info(f'双通道均正确: {suc_both}/{total} = {acc_both:.4f}')
    gen_review_jsonl(combined_data, review_dir, dataset_name=dataset_name, logger=task_logger)
    gen_report_json(model_name, dataset_name, report_dir, acc_A, acc_B, acc_both, total, df=df, logger=task_logger)
    task_logger.close()
