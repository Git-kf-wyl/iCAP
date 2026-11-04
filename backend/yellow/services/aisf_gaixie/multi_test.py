# Private iCAP Yellow business implementation. Do not publish.
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import requests
import services.aisf_gaixie.prompt_without_thought as sp
from services.aisf_gaixie.local_few_shot_retriever import search_fewshot
import services.aisf_gaixie.compare as compare
INPUT_FILE = 'gaixie/test.xlsx'
INPUT_SHEET_NAME = 0
OUTPUT_XLSX = 'result_local_faiss_32B_cur_query_index.xlsx'
MODEL_URL = 'http://127.0.0.1:1/unconfigured'
MODEL_NAME = 'Qwen3-32B'
API_KEY = ''
MODEL_VERIFY_SSL = False
MODEL_TIMEOUT = 300
EMBEDDING_URL = 'http://127.0.0.1:1/unconfigured'
EMBEDDING_MODEL = 'bge-small-zh'
FEWSHOT_INDEX_DIR = 'D:\\AI_Visualization\\CCNModelEvalService\\backend\\services\\aisf_gaixie\\index'
FEWSHOT_RETRIEVAL_MODE = 'query'
FEWSHOT_EXAMPLE_FIELD = 'no_thought_example'
ENABLE_FEWSHOT = True
ENABLE_FIXED_FEWSHOT = True
FEWSHOT_TOP_K = 5
FEWSHOT_SCORE_THRESHOLD = 0.61
MAX_FEWSHOT_EXAMPLES = 5
MAX_CONTEXT_TURNS = 5
USE_NO_FEWSHOT_SYS_PROMPT_WHEN_EMPTY = True
STRICT_FEWSHOT_RETRIEVAL = False
FIXED_FEWSHOT_EXAMPLES_WITH_THOUGHT = ['上下文：我想看黄渤的电影\n当前输入：2025年的\n输出：{"思考":"继承:黄渤电影;追加:2025年","意图":"我想看黄渤2025年的电影"}', '上下文：我在纠结两部电影，一部偏喜剧，一部偏悬疑。\n当前用户输入：前者好看吗？\n输出：{"思考":"消解:前者=偏喜剧那部","意图":"偏喜剧的那部电影好看吗？"}', '上下文：有什么好看的电影吗？\n《功夫》，《少林足球》\n当前用户输入：播放第2个\n输出：{"思考":"原样:播放控制","意图":"播放第2个"}']
FIXED_FEWSHOT_EXAMPLES_NO_THOUGHT = ['上下文：我想看黄渤的电影\n当前输入：2025年的\n输出：{"意图":"我想看黄渤2025年的电影"}\n说明：继承黄渤电影，追加2025年。', '上下文：我在纠结两部电影，一部偏喜剧，一部偏悬疑。\n当前用户输入：前者好看吗？\n输出：{"意图":"偏喜剧的那部电影好看吗？"}\n说明：消解“前者”为“偏喜剧的那部”。', '上下文：有什么好看的电影吗？\n《功夫》，《少林足球》\n当前用户输入：播放第2个\n输出：{"意图":"播放第2个"}\n说明：播放控制类请求不改写。']

def get_fixed_fewshot_examples(example_field=None):
    field = example_field if example_field is not None else FEWSHOT_EXAMPLE_FIELD
    if field == 'no_thought_example':
        return FIXED_FEWSHOT_EXAMPLES_NO_THOUGHT
    return FIXED_FEWSHOT_EXAMPLES_WITH_THOUGHT

def clean_text(value):
    if value is None:
        return ''
    if pd.isna(value):
        return ''
    return str(value).strip()

def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default

def to_json_text(value):
    return json.dumps(value, ensure_ascii=False)

def read_input_table(file_path, sheet_name=0):
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f'找不到输入文件：{path.resolve()}')
    suffix = path.suffix.lower()
    if suffix in ['.xlsx', '.xls']:
        df = pd.read_excel(path, sheet_name=sheet_name)
    elif suffix == '.csv':
        df = pd.read_csv(path, encoding='utf-8-sig')
    else:
        raise ValueError(f'不支持的文件类型：{suffix}，请使用 .xlsx / .xls / .csv')
    df.columns = [clean_text(c) for c in df.columns]
    df = df.fillna('')
    rows = df.to_dict(orient='records')
    headers = list(df.columns)
    if not rows:
        raise ValueError('输入文件没有数据')
    return (rows, headers)

def get_query_turn_numbers(headers):
    turn_nums = set()
    for col in headers:
        match = re.fullmatch('query(\\d+)', clean_text(col))
        if match:
            turn_nums.add(int(match.group(1)))
    if not turn_nums:
        raise ValueError('没有找到 queryN 格式的列，例如 query1、query2')
    return sorted(turn_nums)

def write_output_excel(output_path, results, fewshot_detail, performance):
    output_path = Path(output_path)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        pd.DataFrame(results).to_excel(writer, sheet_name='results', index=False)
        pd.DataFrame(fewshot_detail).to_excel(writer, sheet_name='fewshot_detail', index=False)
        pd.DataFrame(performance).to_excel(writer, sheet_name='performance', index=False)
    print(f'\n已保存结果：{output_path.resolve()}')

def call_chat_model(messages, temperature=0.0, api_key=API_KEY, model_url=MODEL_URL, model_name=MODEL_NAME):
    if model_name.startswith('openpangu-2.0'):
        payload = {'model': model_name, 'messages': messages, 'temperature': temperature, 'thinking': {'type': 'disabled'}}
    else:
        payload = {'model': model_name, 'messages': messages, 'temperature': temperature, 'chat_template_kwargs': {'enable_thinking': False}}
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    proxies = {}
    start_time = time.time()
    resp = requests.request('POST', model_url, json=payload, headers=headers, verify=True)
    resp.raise_for_status()
    data = resp.json()
    elapsed = time.time() - start_time
    content = data['choices'][0]['message']['content']
    usage = data.get('usage', {})
    return {'content': content, 'model_elapsed_time': elapsed, 'input_tokens': usage.get('prompt_tokens', 0), 'output_tokens': usage.get('completion_tokens', 0)}

def get_item_score(item):
    return safe_float(item.get('score', 0.0))

def get_item_example_text(item, example_field=None):
    field = example_field if example_field is not None else FEWSHOT_EXAMPLE_FIELD
    return clean_text(item.get(field, ''))

def format_fewshot_blocks(example_bodies):
    blocks = []
    for idx, body in enumerate(example_bodies, start=1):
        body = clean_text(body)
        if body:
            blocks.append(f'示例{idx}：\n{body}')
    return '\n\n---\n\n'.join(blocks)

def select_items_by_threshold(items, threshold, max_examples, example_field=None):
    """
    L2 距离筛选：
    - score 越小越相似
    - score < threshold 才保留
    """
    valid_items = [item for item in items if get_item_example_text(item, example_field)]
    sorted_asc = sorted(valid_items, key=get_item_score)
    selected = [item for item in sorted_asc if get_item_score(item) < threshold][:max_examples]
    debug = {'method': 'l2_score_lt_threshold', 'threshold': threshold, 'raw_count': len(items), 'valid_count': len(valid_items), 'selected_count': len(selected), 'scores_asc': [get_item_score(item) for item in sorted_asc], 'selected_scores_asc': [get_item_score(item) for item in selected], 'selected_items': [{'score': get_item_score(item), 'id': item.get('id'), 'hit_source': item.get('hit_source'), 'rule_type': item.get('rule_type'), 'labels': item.get('labels'), 'current_query': item.get('current_query'), 'prev_current_query': item.get('prev_current_query')} for item in selected]}
    return (selected, debug)

def build_final_fewshot_text(selected_items, example_field=None, enable_fixed_fewshot=ENABLE_FIXED_FEWSHOT, max_fewshot_examples=MAX_FEWSHOT_EXAMPLES):
    """
    规则：
    - 没有动态示例：返回空字符串，外层切无 few-shot prompt
    - 有动态示例：固定示例补齐到 max_fewshot_examples
    - 动态示例按 score 降序拼，让最低 score 的最相关示例放最后
    """
    if not selected_items:
        return ('', {'selected_dynamic_count': 0, 'fixed_used_count': 0, 'final_example_count': 0, 'reason': 'no_selected_items'})
    fixed_examples = get_fixed_fewshot_examples(example_field) if enable_fixed_fewshot else []
    selected_asc = sorted(selected_items, key=get_item_score)[:max_fewshot_examples]
    dynamic_count = len(selected_asc)
    fixed_capacity = max(0, max_fewshot_examples - dynamic_count)
    selected_fixed = fixed_examples[:fixed_capacity]
    selected_dynamic_for_prompt = sorted(selected_asc, key=get_item_score, reverse=True)
    dynamic_bodies = [get_item_example_text(item, example_field) for item in selected_dynamic_for_prompt if get_item_example_text(item, example_field)]
    final_bodies = selected_fixed + dynamic_bodies
    final_bodies = final_bodies[:max_fewshot_examples]
    fewshot_text = format_fewshot_blocks(final_bodies)
    debug = {'selected_dynamic_count': dynamic_count, 'fixed_used_count': len(selected_fixed), 'final_example_count': len(final_bodies), 'dynamic_order': 'score_desc_lowest_score_last', 'final_dynamic_items': [{'score': get_item_score(item), 'id': item.get('id'), 'hit_source': item.get('hit_source'), 'rule_type': item.get('rule_type'), 'labels': item.get('labels'), 'current_query': item.get('current_query'), 'prev_current_query': item.get('prev_current_query')} for item in selected_dynamic_for_prompt]}
    return (fewshot_text, debug)

def build_prev_current_query_value(history_turns, current_user_msg):
    current_user_msg = clean_text(current_user_msg)
    if not history_turns:
        return current_user_msg
    prev_query = clean_text(history_turns[-1].get('query', ''))
    if not prev_query:
        return current_user_msg
    return f'上一轮用户输入：{prev_query}\n当前用户输入：{current_user_msg}'

def build_messages(system_prompt_template, history_turns, current_user_msg, user_prompt_template, fewshot_text, max_context_turns=MAX_CONTEXT_TURNS):
    system_content = system_prompt_template
    system_content = system_content.replace('{{few_shot}}', fewshot_text)
    system_content = system_content.replace('{{few_shots}}', fewshot_text)
    messages = [{'role': 'system', 'content': system_content}]
    recent_history = history_turns[-max_context_turns:]
    for turn in recent_history:
        messages.append({'role': 'user', 'content': turn['query']})
        messages.append({'role': 'assistant', 'content': turn['assistant']})
    user_content = user_prompt_template
    user_content = user_content.replace('{{query}}', current_user_msg)
    user_content = user_content.replace('{{few_shot}}', fewshot_text)
    user_content = user_content.replace('{{few_shots}}', fewshot_text)
    messages.append({'role': 'user', 'content': user_content})
    return messages

def process(report_dir, file_path=INPUT_FILE, output_xlsx=OUTPUT_XLSX, model_url=MODEL_URL, model_name=MODEL_NAME, fewshot_index_dir=FEWSHOT_INDEX_DIR, fewshot_retrieval_mode=FEWSHOT_RETRIEVAL_MODE, fewshot_example_field=FEWSHOT_EXAMPLE_FIELD, enable_fewshot=ENABLE_FEWSHOT, enable_fixed_fewshot=ENABLE_FIXED_FEWSHOT, fewshot_top_k=FEWSHOT_TOP_K, fewshot_score_threshold=FEWSHOT_SCORE_THRESHOLD, max_fewshot_examples=MAX_FEWSHOT_EXAMPLES, max_context_turns=MAX_CONTEXT_TURNS, dataset_name='', log_dir=None, limit=None, temperature=0.0, api_key=API_KEY, task_id='', model_id='', retry_content_none=False, retry_enabled=False):
    """改写评测主流程。

    所有参数均可通过关键字注入，默认从模块级全局变量取值，
    因此 __main__ 直接调用 process() 保持向后兼容。

    注意：本函数可能被多个业务线程并发调用（run_test_server 对每个任务
    各起一个 Thread），因此严禁写模块级全局变量 globals()，内部必须
    只使用本函数的局部参数，避免线程间互相覆盖配置。
    """
    fewshot_index_dir = fewshot_index_dir if fewshot_index_dir else FEWSHOT_INDEX_DIR
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        _log_file = open(os.path.join(log_dir, 'eval_log.log'), 'w', encoding='utf-8')
    else:
        _log_file = None

    def log(msg):
        if _log_file:
            _log_file.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            _log_file.flush()
        print(msg)
    log(f'[{datetime.now()}] gaixie process 启动')
    log(f'  model_id:      {model_id}')
    log(f'  model_name:    {model_name}')
    log(f'  task_id:       {task_id}')
    log(f'  dataset_name:  {dataset_name}')
    log(f'  api_url:       {model_url}')
    log(f'  api_key:       {api_key[:8]}...')
    log(f'  temperature:   {temperature}')
    log(f'  limit:         {limit}')
    log(f'  enable_fewshot:         {enable_fewshot}')
    log(f'fewshot_index_dir = {fewshot_index_dir}')
    rows, headers = read_input_table(file_path, sheet_name=INPUT_SHEET_NAME)
    if limit is not None and limit > 0:
        rows = rows[:limit]
        log(f'已限制执行前 {limit} 条用例')
    turn_nums = get_query_turn_numbers(headers)
    result_records = []
    fewshot_records = []
    performance_records = []
    reuse_map = {}
    if retry_enabled:
        try:
            prev_path = Path(output_xlsx)
            _reuse_n = 0
            if prev_path.exists():
                _prev_df = pd.read_excel(prev_path, sheet_name='results')
                _prev_df = _prev_df.fillna('')
                for _, _prev_row in _prev_df.iterrows():
                    try:
                        _sid = int(_prev_row.get('sample_id'))
                        _tid = int(_prev_row.get('turn'))
                    except Exception:
                        continue
                    _resp = clean_text(_prev_row.get('model_response', ''))
                    _valid = _resp and (not _resp.startswith('[ERROR]')) and (not _resp.startswith('[TIMEOUT]'))
                    if retry_content_none and (not _valid):
                        continue
                    reuse_map[_sid, _tid] = {'model_response': _resp, 'model_elapsed_time': safe_float(_prev_row.get('model_elapsed_time')), 'input_tokens': safe_float(_prev_row.get('input_tokens')), 'output_tokens': safe_float(_prev_row.get('output_tokens'))}
                    _reuse_n += 1
            log(f'续测已加载 {_reuse_n} 条已完成 (sample_id, turn) 结果（retry_content_none={retry_content_none}）')
        except Exception as e:
            log(f'⚠️ 续测加载上次结果失败，将全部重新执行：{e}')
            reuse_map = {}
    log('')
    log('=' * 70)
    log('批量测试配置')
    log('=' * 70)
    log(f'输入文件: {file_path}')
    log(f'样本数: {len(rows)}')
    log(f'FEWSHOT_RETRIEVAL_MODE: {fewshot_retrieval_mode}')
    log(f'FEWSHOT_EXAMPLE_FIELD: {fewshot_example_field}')
    log(f'FEWSHOT_TOP_K: {fewshot_top_k}')
    log(f'FEWSHOT_SCORE_THRESHOLD: {fewshot_score_threshold}')
    log('score 规则：L2 距离，score < 阈值才保留，越小越相关')
    log('=' * 70)
    for sample_idx, row in enumerate(rows):
        log('')
        log('=' * 50)
        log(f'Processing Sample {sample_idx}')
        log('=' * 50)
        history_turns = []
        for turn_idx, n in enumerate(turn_nums, start=1):
            round_start_time = time.time()
            q_key = f'query{n}'
            a_key = f'assistant{n}'
            user_msg = clean_text(row.get(q_key, ''))
            assistant_msg = clean_text(row.get(a_key, '')) or '无可用助手回复'
            if not user_msg:
                break
            prev_current_query_value = build_prev_current_query_value(history_turns=history_turns, current_user_msg=user_msg)
            raw_fewshot_text = ''
            fewshot_text = ''
            fewshot_debug = ''
            ordered_items = []
            selected_items = []
            threshold_debug = {}
            final_fewshot_debug = {}
            has_fewshot = False
            embedding_recall_elapsed_time = 0.0
            if enable_fewshot:
                try:
                    recall_start = time.time()
                    raw_fewshot_text, api_debug, api_has_fewshot, ordered_items = search_fewshot(query_value=user_msg, prev_current_query_value=prev_current_query_value, top_k=fewshot_top_k, index_dir=fewshot_index_dir, embedding_url=EMBEDDING_URL, embedding_model=EMBEDDING_MODEL, retrieval_mode=fewshot_retrieval_mode, example_field=fewshot_example_field)
                    embedding_recall_elapsed_time = time.time() - recall_start
                    selected_items, threshold_debug = select_items_by_threshold(items=ordered_items, threshold=fewshot_score_threshold, max_examples=max_fewshot_examples, example_field=fewshot_example_field)
                    fewshot_text, final_fewshot_debug = build_final_fewshot_text(selected_items=selected_items, example_field=fewshot_example_field, enable_fixed_fewshot=enable_fixed_fewshot, max_fewshot_examples=max_fewshot_examples)
                    has_fewshot = bool(clean_text(fewshot_text))
                    fewshot_debug = '\n'.join([api_debug, '', '====== 阈值筛选 Debug ======', json.dumps(threshold_debug, ensure_ascii=False, indent=2), '', '====== 最终 few-shot Debug ======', json.dumps(final_fewshot_debug, ensure_ascii=False, indent=2), '', '====== 最终 few-shot 内容 ======', fewshot_text])
                except Exception as e:
                    fewshot_debug = f'[FEWSHOT_LOCAL_FAISS_ERROR] {str(e)}'
                    fewshot_text = ''
                    has_fewshot = False
                    ordered_items = []
                    selected_items = []
                    log(f'⚠️ Few-shot 本地召回失败: {e}')
                    if STRICT_FEWSHOT_RETRIEVAL:
                        raise
            selected_sys_prompt = sp.SYS_PROMPT
            prompt_variant = 'sys_with_fewshot'
            if enable_fewshot and USE_NO_FEWSHOT_SYS_PROMPT_WHEN_EMPTY and (not has_fewshot):
                selected_sys_prompt = getattr(sp, 'SYS_PROMPT_NO_FEWSHOT', sp.SYS_PROMPT)
                prompt_variant = 'sys_no_fewshot_fallback'
                fewshot_text = ''
            if not enable_fewshot:
                selected_sys_prompt = getattr(sp, 'SYS_PROMPT_NO_FEWSHOT', sp.SYS_PROMPT)
                prompt_variant = 'sys_no_fewshot_disabled'
                fewshot_text = ''
                has_fewshot = False
            messages = build_messages(system_prompt_template=selected_sys_prompt, history_turns=history_turns, current_user_msg=user_msg, user_prompt_template=sp.user_prompt, fewshot_text=fewshot_text, max_context_turns=max_context_turns)
            _reused = False
            if retry_enabled:
                _prev = reuse_map.get((sample_idx, turn_idx))
                if _prev is not None:
                    response = _prev['model_response']
                    model_elapsed_time = _prev['model_elapsed_time']
                    input_tokens = _prev['input_tokens']
                    output_tokens = _prev['output_tokens']
                    _reused = True
                    log(f'[Sample {sample_idx}, Turn {turn_idx}] 复用上次结果，跳过模型调用')
            if not _reused:
                try:
                    model_data = call_chat_model(messages, temperature=temperature, api_key=api_key, model_url=model_url, model_name=model_name)
                    response = model_data['content']
                    model_elapsed_time = model_data['model_elapsed_time']
                    input_tokens = model_data['input_tokens']
                    output_tokens = model_data['output_tokens']
                except Exception as e:
                    log(f'❌ 模型调用出错 Sample={sample_idx}, Turn={turn_idx}: {e}')
                    response = f'[ERROR] {str(e)}'
                    model_elapsed_time = 0.0
                    input_tokens = 0
                    output_tokens = 0
            total_round_elapsed_time = time.time() - round_start_time
            log('')
            log(f'[Sample {sample_idx}, Turn {turn_idx}]')
            log(f'用户原始输入：{user_msg}')
            log(f'模型输出：{response}')
            log(f'Embedding召回时延：{embedding_recall_elapsed_time:.4f}s')
            log(f'模型时延：{model_elapsed_time:.4f}s')
            raw_items_summary = [{'score': item.get('score'), 'id': item.get('id'), 'hit_source': item.get('hit_source'), 'route_scores': item.get('route_scores'), 'rule_type': item.get('rule_type'), 'labels': item.get('labels'), 'current_query': item.get('current_query'), 'prev_current_query': item.get('prev_current_query'), 'example_empty': not bool(get_item_example_text(item))} for item in ordered_items]
            selected_items_summary = [{'score': item.get('score'), 'id': item.get('id'), 'hit_source': item.get('hit_source'), 'rule_type': item.get('rule_type'), 'labels': item.get('labels'), 'current_query': item.get('current_query'), 'prev_current_query': item.get('prev_current_query')} for item in selected_items]
            context_text = '\n'.join((f"[{msg['role']}]: {msg['content']}" for msg in messages))
            system_prompt_text = messages[0]['content'] if messages else ''
            history_context_text = '\n'.join((f"[{msg['role']}]: {msg['content']}" for msg in messages[1:]))
            result_records.append({'sample_id': sample_idx, 'turn': turn_idx, 'original_query': user_msg, 'gold_assistant': assistant_msg, 'model_response': response, 'fewshot_enabled': enable_fewshot, 'has_fewshot': has_fewshot, 'prompt_variant': prompt_variant, 'fewshot_retrieval_mode': fewshot_retrieval_mode, 'fewshot_example_field': fewshot_example_field, 'fewshot_top_k': fewshot_top_k, 'fewshot_score_threshold': fewshot_score_threshold, 'selected_fewshot_count': len(selected_items), 'final_example_count': final_fewshot_debug.get('final_example_count', ''), 'retrieval_query_text': user_msg, 'prev_current_query_value': prev_current_query_value, 'embedding_recall_elapsed_time': embedding_recall_elapsed_time, 'model_elapsed_time': model_elapsed_time, 'total_round_elapsed_time': total_round_elapsed_time, 'input_tokens': input_tokens, 'output_tokens': output_tokens, 'total_tokens': input_tokens + output_tokens, 'full_context_json': to_json_text(messages), 'context_text': context_text, 'prompt': system_prompt_text, 'context': history_context_text})
            fewshot_records.append({'sample_id': sample_idx, 'turn': turn_idx, 'original_query': user_msg, 'prev_current_query_value': prev_current_query_value, 'has_fewshot': has_fewshot, 'prompt_variant': prompt_variant, 'fewshot_retrieval_mode': fewshot_retrieval_mode, 'fewshot_example_field': fewshot_example_field, 'fewshot_score_threshold': fewshot_score_threshold, 'raw_items': to_json_text(raw_items_summary), 'selected_items': to_json_text(selected_items_summary), 'threshold_debug': to_json_text(threshold_debug), 'final_fewshot_debug': to_json_text(final_fewshot_debug), 'raw_fewshot_text': raw_fewshot_text, 'final_fewshot_text': fewshot_text, 'fewshot_debug': fewshot_debug})
            performance_records.append({'sample_id': sample_idx, 'turn': turn_idx, 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'), 'query': user_msg, 'embedding_recmodel_elapsed_timeall_elapsed_time': embedding_recall_elapsed_time, '': model_elapsed_time, 'total_round_elapsed_time': total_round_elapsed_time, 'input_tokens': input_tokens, 'output_tokens': output_tokens, 'total_tokens': input_tokens + output_tokens, 'has_fewshot': has_fewshot, 'selected_fewshot_count': len(selected_items), 'final_example_count': final_fewshot_debug.get('final_example_count', '')})
            history_turns.append({'query': user_msg, 'assistant': assistant_msg})
            if len(history_turns) > max_context_turns:
                history_turns = history_turns[-max_context_turns:]
    try:
        write_output_excel(output_path=output_xlsx, results=result_records, fewshot_detail=fewshot_records, performance=performance_records)
        output_dir = os.path.dirname(output_xlsx)
        output_file_path = os.path.join(output_dir, f'对比结果_{dataset_name}.xlsx')
        result_df = compare.compare_intents(output_xlsx, file_path, col_name='model_response', output_file=output_file_path, log_fn=log)
        review_lines = []
        subset_name = '外挂fewshot库' if enable_fewshot else '不外挂fewshot库'
        for idx, (rec, (_, cmp_row)) in enumerate(zip(result_records, result_df.iterrows())):
            is_correct = cmp_row['最终结果'] == '正确'
            review_lines.append({'raw_input': {'Question': rec['original_query'], 'expected': rec['gold_assistant'], 'prompt': rec.get('prompt', ''), 'context': rec.get('context', ''), 'No': idx}, 'choices': [{'review': {'gold': rec['gold_assistant'], 'pred': rec['model_response'], 'result': '1' if is_correct else '0'}, 'message': {'content': rec['model_response']}}], 'index': idx, 'dialogue_round': f"{rec['sample_id']}-{rec['turn']}", 'subset_name': subset_name, 'usage': {'prompt_tokens': rec.get('input_tokens', 0), 'completion_tokens': rec.get('output_tokens', 0), 'total_tokens': rec.get('total_tokens', 0)}, 'response_time': rec.get('total_round_elapsed_time', 0)})
        review_file = os.path.join(output_dir, f'{dataset_name}_{subset_name}.jsonl')
        with open(review_file, 'w', encoding='utf-8') as f:
            for line in review_lines:
                f.write(json.dumps(line, ensure_ascii=False) + '\n')
        log(f'已生成 review jsonl: {review_file}')
        total_count = len(result_df)
        correct_count = (result_df['最终结果'] == '正确').sum()
        acc = correct_count / total_count if total_count > 0 else 0
        report_map = {'name': f'{model_name}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_name, 'score': round(acc, 2), 'metrics': [{'categories': [{'macro_score': round(acc, 2), 'name': ['改写'], 'num': total_count, 'score': round(acc, 2), 'subsets': [{'name': subset_name, 'num': total_count, 'score': round(acc, 2), 'correct_num': int(correct_count)}]}], 'macro_score': round(acc, 2), 'name': subset_name, 'num': total_count, 'score': round(acc, 2)}]}
        os.makedirs(report_dir, exist_ok=True)
        report_file = os.path.join(report_dir, f'{dataset_name}.json')
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_map, f, ensure_ascii=False, indent=4)
        log(f'已生成 report json: {report_file}')
    finally:
        if _log_file:
            _log_file.close()
