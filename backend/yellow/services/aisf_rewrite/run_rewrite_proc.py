# Private iCAP Yellow business implementation. Do not publish.
"""改写（aisf_rewrite 集成）—— 独立子进程入口（壳封装）。

由 run_test_server.py 以 subprocess 方式启动（见 CUSTOM_RULER2_PROC_DISPATCH['改写']），
使该测评任务的存活不依赖 flask 服务进程（与 aisf_guiTican / aisf_coordinator 等业务一致）。

设计原则：不改动原工程业务逻辑（batch_rewrite_test_dual_rules_v2.py 的上下文解析 /
messages 组装 / 关键字+黑名单宽松规则与"不改写"严格规则双重阅卷），本文件只做"壳封装"：
  1. 将项目根目录与业务源码目录加入 sys.path；
  2. 解析 --config 传入的运行参数（model_config / task_id / user_req 等）；
  3. 把被测模型 endpoint / model_name / 生成超参注入 batch_rewrite_test_dual_rules_v2 的模块级全局变量；
  4. Test 阶段：壳内并发编排每行（组装 messages → 调用被测模型），产出 model_output / messages_json
     / token / 耗时；
  5. Judge 阶段：调用 rewrite_biz.judge_response / judge_strict_rule 做本地规则阅卷
     （宽松：改写关键字全命中 + 黑名单全不命中；严格：宽松基础上对"审核结果=不改写"用例做去除标点的硬匹配）；
  6. 产出四份文件：logs/eval_log.log（由 spawn_eval_proc 重定向写入）+ 结果 excel
     （测试明细 / 总体统计 / 维度统计 三个 Sheet）+ review jsonl + 总体结果 json；
  7. 由本文件兜底 finalize_task 收尾任务状态。
"""
from state_storage import open_state, state_exists, state_isfile
import os
import sys
import json
import re
import time
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _find_project_root():
    """向上查找项目根目录（run_test_server.py + services 所在），供 import 项目模块。"""
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if state_isfile(os.path.join(d, 'run_test_server.py')) and os.path.isdir(os.path.join(d, 'services')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
_PROJECT_ROOT = _find_project_root()
if _PROJECT_ROOT and _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_BIZ_DIR = os.path.dirname(os.path.abspath(__file__))
if _BIZ_DIR not in sys.path:
    sys.path.insert(0, _BIZ_DIR)
from utils.consts import REWRITE_DATASET_PATH
from utils.eval_utils import get_limit
from services.custom_proc_common import parse_config, finalize_task, extract_generation_config
from services.aisf_rewrite import batch_rewrite_test_dual_rules_v2 as rewrite_biz
_ILLEGAL_EXCEL_CHAR_RE = re.compile('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]')

def _safe_text(value):
    """Excel 单元格安全转字符串，并剔除 openpyxl 无法写入的非法字符。"""
    if pd.isna(value):
        return ''
    return _ILLEGAL_EXCEL_CHAR_RE.sub('', str(value))

def _to_int(value):
    try:
        return max(0, int(float(value)))
    except (ValueError, TypeError):
        return 0

def _find_dataset_xlsx(dataset_dir):
    """在数据集目录下寻找第一个 .xlsx 测试集文件。"""
    if not os.path.isdir(dataset_dir):
        return None
    for fname in os.listdir(dataset_dir):
        fpath = os.path.join(dataset_dir, fname)
        if state_isfile(fpath) and os.path.splitext(fname)[1].lower() == '.xlsx':
            if fname.startswith('~$'):
                continue
            return fpath
    return None

def _locate_dataset_xlsx(dataset_name):
    """定位改写测试集 excel。

    优先按 `<REWRITE_DATASET_PATH>/<dataset_name>` 定位；
    未命中时从 backend/config/field_testcase_cfg.json 中按配置的 input_path 兜底，
    兼容「dataset_name 与测试集目录名不一致」的注册配置（如改写_0804 → AISF/改写）。
    """
    dataset_dir = os.path.join(REWRITE_DATASET_PATH, dataset_name)
    excel_path = _find_dataset_xlsx(dataset_dir)
    if excel_path:
        return excel_path
    try:
        cfg_path = os.path.join('backend', 'config', 'field_testcase_cfg.json')
        with open_state(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        looked = set()
        for info in cfg.values():
            if not isinstance(info, dict):
                continue
            if info.get('dataset_name') != dataset_name:
                continue
            input_path = info.get('input_path')
            if not input_path or input_path in looked:
                continue
            looked.add(input_path)
            excel_path = _find_dataset_xlsx(input_path.lstrip('./').replace('\\', os.sep))
            if excel_path:
                return excel_path
    except Exception:
        pass
    return None

def _call_model(messages, url, api_key, model_name, generate_config):
    """调用被测模型（OpenAI 兼容 /v1/chat/completions，壳内实现，不改原工程）。

    返回 (elapsed, content, prompt_tokens, completion_tokens, error)。
    失败或 content 为空时 error 非空；重试/超时等取自 generate_config，缺省沿用原工程口径。
    """
    temperature = generate_config.get('temperature', 0)
    timeout = int(generate_config.get('timeout', 180) or 180)
    max_retries = int(generate_config.get('max_retries', 3) or 3)
    retry_base = float(generate_config.get('retry_base_seconds', 2) or 2)
    payload = {'model': model_name, 'messages': messages, 'temperature': float(temperature)}
    if generate_config.get('max_tokens'):
        payload['max_tokens'] = int(generate_config['max_tokens'])
    if generate_config.get('top_p') is not None:
        payload['top_p'] = float(generate_config['top_p'])
    if generate_config.get('top_k') is not None:
        payload['top_k'] = int(generate_config['top_k'])
    payload['chat_template_kwargs'] = generate_config.get('chat_template_kwargs') or {'enable_thinking': False}
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    last_error = ''
    for attempt in range(1, max_retries + 1):
        start_time = time.time()
        try:
            response = requests.request('POST', url, json=payload, headers=headers, verify=True, timeout=timeout)
            elapsed = time.time() - start_time
            if not response.ok:
                last_error = f'HTTP {response.status_code}；{response.text[:500]}'
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    return (round(elapsed, 2), '', 0, 0, last_error)
            else:
                data = response.json()
                choices = data.get('choices') or []
                if not choices:
                    last_error = '响应中没有 choices'
                else:
                    message = choices[0].get('message') or {}
                    content = (message.get('content') or '').strip()
                    if not content:
                        last_error = '模型返回空 content'
                    else:
                        usage = data.get('usage') or {}
                        prompt_tokens = _to_int(usage.get('prompt_tokens'))
                        completion_tokens = _to_int(usage.get('completion_tokens'))
                        return (round(elapsed, 2), content, prompt_tokens, completion_tokens, '')
        except Exception as exc:
            elapsed = time.time() - start_time
            last_error = str(exc)
        if attempt < max_retries:
            time.sleep(retry_base * attempt)
    return (0.0, '', 0, 0, last_error)

def _process_row(index, row, generate_config):
    """处理单条数据：组装 messages → 调用被测模型 → 宽松/严格双重规则阅卷。

    返回 (index, detail_dict)，主线程按 index 写回 DataFrame。
    阅卷口径与 batch_rewrite_test_dual_rules_v2.py 完全一致
    （judge_response 宽松规则 + judge_strict_rule 严格规则）。
    """
    context = rewrite_biz.normalize_cell(row.get('上下文'))
    current_query = rewrite_biz.normalize_cell(row.get('当前语句'))
    keywords = rewrite_biz.split_terms(row.get('改写关键字'))
    blacklist = rewrite_biz.split_terms(row.get('改写黑名单'))
    review_result = rewrite_biz.normalize_cell(row.get('审核结果'))
    detail = {'messages_json': '', 'model_output': '', '宽松判定结果': '', '宽松判定原因': '', '严格判定结果': '', '严格判定原因': '', '模型改写文本': '', '严格匹配_当前输入': '', '严格匹配_模型输出': '', '要求关键字': '、'.join(keywords), '命中关键字': '', '缺失关键字': '', '黑名单词': '、'.join(blacklist), '命中黑名单': '', '接口错误': '', 'status': 'done', 'times': '', 'prompt_tokens': 0, 'completion_tokens': 0}
    if not current_query:
        detail['宽松判定结果'] = '失败'
        detail['宽松判定原因'] = '当前语句为空'
        detail['严格判定结果'] = '失败'
        detail['严格判定原因'] = '当前语句为空'
        detail['status'] = 'error'
        return (index, detail)
    try:
        messages = rewrite_biz.build_messages(context, current_query)
        detail['messages_json'] = rewrite_biz.messages_to_json(messages)
    except Exception as exc:
        error_message = f'上下文解析失败：{exc}'
        detail['宽松判定结果'] = '失败'
        detail['宽松判定原因'] = error_message
        detail['严格判定结果'] = '失败'
        detail['严格判定原因'] = error_message
        detail['接口错误'] = error_message
        detail['status'] = 'error'
        return (index, detail)
    elapsed, content, prompt_tokens, completion_tokens, api_error = _call_model(messages, url=rewrite_biz.LLM_BASE_URL, api_key=rewrite_biz.API_KEY, model_name=rewrite_biz.MODEL_NAME, generate_config=generate_config)
    detail['times'] = elapsed if elapsed else ''
    detail['model_output'] = content
    detail['prompt_tokens'] = prompt_tokens
    detail['completion_tokens'] = completion_tokens
    if api_error:
        detail['接口错误'] = api_error
        detail['宽松判定结果'] = '调用失败'
        detail['宽松判定原因'] = api_error
        detail['严格判定结果'] = '调用失败'
        detail['严格判定原因'] = api_error
        detail['status'] = 'error'
        return (index, detail)
    judge = rewrite_biz.judge_response(content, keywords, blacklist)
    detail['命中关键字'] = '、'.join(judge['matched_keywords'])
    detail['缺失关键字'] = '、'.join(judge['missing_keywords'])
    detail['命中黑名单'] = '、'.join(judge['hit_blacklist'])
    detail['宽松判定结果'] = '正确' if judge['is_correct'] else '失败'
    detail['宽松判定原因'] = judge['reason']
    strict_judge = rewrite_biz.judge_strict_rule(loose_is_correct=judge['is_correct'], loose_reason=judge['reason'], review_result=review_result, current_query=current_query, model_response=content)
    detail['严格判定结果'] = '正确' if strict_judge['is_correct'] else '失败'
    detail['严格判定原因'] = strict_judge['reason']
    detail['模型改写文本'] = strict_judge.get('rewrite_text', '')
    detail['严格匹配_当前输入'] = strict_judge.get('current_norm', '')
    detail['严格匹配_模型输出'] = strict_judge.get('model_norm', '')
    return (index, detail)

def _convert_to_review_jsonl(result_xlsx_path, jsonl_path, dataset_name=''):
    """把结果 excel 转换为前端使用的逐条 review jsonl。

    每行一条记录，choices[0].review 含 gold(ground_truth)/pred(model_output)/result(严格判定)，
    并额外携带宽松判定（loose_result）与两套判定原因。
    格式与 aisf_guiTican / aisf_coordinator 产出的 review jsonl 基本一致。
    """
    df = pd.read_excel(result_xlsx_path, dtype=str)
    review_lines = []
    for idx, (_, row) in enumerate(df.iterrows()):
        cur_query = _safe_text(row.get('当前语句'))
        ground_truth = _safe_text(row.get('改写结果'))
        model_output = _safe_text(row.get('model_output'))
        strict_result = _safe_text(row.get('严格判定结果'))
        strict_reason = _safe_text(row.get('严格判定原因'))
        loose_result = _safe_text(row.get('宽松判定结果'))
        loose_reason = _safe_text(row.get('宽松判定原因'))
        raw_response = _safe_text(row.get('model_output'))
        status = _safe_text(row.get('status')) or 'done'
        is_pass = strict_result == '正确'
        loose_pass = loose_result == '正确'
        if status and status != 'done':
            is_pass = False
            loose_pass = False
        prompt_tokens = _to_int(row.get('prompt_tokens'))
        completion_tokens = _to_int(row.get('completion_tokens'))
        response_time = _to_int(row.get('times'))
        excel_info = {'宽松判定结果': loose_result, '宽松判定原因': loose_reason, '严格判定结果': strict_result, '严格判定原因': strict_reason, '要求关键字': _safe_text(row.get('要求关键字')), '命中关键字': _safe_text(row.get('命中关键字')), '缺失关键字': _safe_text(row.get('缺失关键字')), '黑名单词': _safe_text(row.get('黑名单词')), '命中黑名单': _safe_text(row.get('命中黑名单')), '模型改写文本': _safe_text(row.get('模型改写文本')), '审核结果': _safe_text(row.get('审核结果'))}
        review_lines.append({'raw_input': {'Question': cur_query, 'expected': ground_truth, 'prompt': rewrite_biz.SYSTEM_PROMPT, 'context': _safe_text(row.get('上下文')), 'No': idx}, 'excel_info': excel_info, 'choices': [{'review': {'gold': ground_truth, 'pred': model_output, 'result': '1' if is_pass else '0', 'loose_result': '1' if loose_pass else '0', '判定结果': '通过' if is_pass else '不通过', '宽松判定结果': '通过' if loose_pass else '不通过', 'judge_result': strict_reason, 'loose_error_reason': loose_reason, 'raw_response': raw_response, 'status': status}, 'message': {'content': raw_response or model_output}}], 'index': idx, 'dialogue_round': str(idx), 'subset_name': dataset_name or '改写', 'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens, 'total_tokens': prompt_tokens + completion_tokens}, 'response_time': response_time})
    with open_state(jsonl_path, 'w', encoding='utf-8') as f:
        for line in review_lines:
            f.write(json.dumps(line, ensure_ascii=False) + '\n')

def _build_subsets(result_df):
    """按「维度」列分组统计各维度的通过率（空维度显示为（空标签）），供报告 json 的 subsets。

    每个维度同时给出严格通过率（score）与宽松通过率（loose_score），
    并保留兼容字段 strict_num / loose_num。
    """
    temp = result_df.copy()
    if '维度' in temp.columns:
        temp['维度'] = temp['维度'].fillna('').astype(str).str.strip().replace('', '（空标签）')
    else:
        temp['维度'] = '改写'
    subsets = []
    for label, group in temp.groupby('维度', sort=False):
        total = len(group)
        strict_pass = int((group.get('严格判定结果', pd.Series([])) == '正确').sum())
        loose_pass = int((group.get('宽松判定结果', pd.Series([])) == '正确').sum())
        strict_score = round(strict_pass / total, 4) if total else 0
        loose_score = round(loose_pass / total, 4) if total else 0
        subsets.append({'name': label, 'num': total, 'score': strict_score, 'correct_num': strict_pass, 'strict_num': strict_pass, 'loose_num': loose_pass, 'loose_score': loose_score, '严格通过数': strict_pass, '宽松通过数': loose_pass, '严格通过率': strict_score, '宽松通过率': loose_score})
    return subsets

def _write_report_json(report_dir, dataset_name, model_name, result_df):
    """生成总体结果 json（供前端 /v1/get_file_path / update_eval_res 读分）。

    统计维度：主 score/通过率基于「严格判定结果」，同时给出宽松通过率；subsets 按「维度」细分，
    与 batch_rewrite_test_dual_rules_v2.py 的 build_overall_stats / build_dimension_stats 口径一致。
    """
    os.makedirs(report_dir, exist_ok=True)
    total = len(result_df)
    strict_pass = int((result_df.get('严格判定结果', pd.Series([])) == '正确').sum()) if total else 0
    loose_pass = int((result_df.get('宽松判定结果', pd.Series([])) == '正确').sum()) if total else 0
    strict_acc = strict_pass / total if total else 0
    loose_acc = loose_pass / total if total else 0
    subsets = _build_subsets(result_df)
    report_map = {'name': f'{model_name}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_name, 'score': round(strict_acc, 4), 'loose_score': round(loose_acc, 4), '严格通过率': round(strict_acc, 4), '宽松通过率': round(loose_acc, 4), 'metrics': [{'categories': [{'macro_score': round(strict_acc, 4), 'name': ['改写'], 'num': total, 'score': round(strict_acc, 4), 'loose_score': round(loose_acc, 4), '严格通过率': round(strict_acc, 4), '宽松通过率': round(loose_acc, 4), 'subsets': subsets}], 'name': ['改写'], 'score': round(strict_acc, 4), 'loose_score': round(loose_acc, 4)}], 'summary': {'总用例数': int(total), '严格通过数': int(strict_pass), '严格通过率': round(strict_acc, 4), '宽松通过数': int(loose_pass), '宽松通过率': round(loose_acc, 4)}}
    report_file = os.path.join(report_dir, f'{dataset_name}.json')
    with open_state(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_map, f, ensure_ascii=False, indent=4)
    return report_file

def run_rewrite_proc(model_config, task_id, model_id, user_req, thread_id):
    model_name = model_config['info']['model_name']
    api_params = model_config['config']['api_params_available'][0]
    api_url = api_params['endpoint']
    api_key = api_params.get('api_key') or 'EMPTY'
    limit = get_limit(user_req.get('limit'))
    eval_batch_size = user_req.get('eval_batch_size')
    dataset_args = user_req['dataset_args']
    generate_config = extract_generation_config(user_req)
    rewrite_biz.LLM_BASE_URL = api_url
    rewrite_biz.API_KEY = api_key
    rewrite_biz.MODEL_NAME = model_name
    if generate_config.get('temperature') is not None:
        rewrite_biz.TEMPERATURE = float(generate_config['temperature'])
    if generate_config.get('max_retries') is not None:
        rewrite_biz.MAX_RETRIES = int(generate_config['max_retries'])
    if generate_config.get('timeout') is not None:
        rewrite_biz.REQUEST_TIMEOUT_SECONDS = int(generate_config['timeout'])
    if generate_config.get('empty_keyword_counts_as_pass') is not None:
        rewrite_biz.EMPTY_KEYWORD_COUNTS_AS_PASS = bool(generate_config['empty_keyword_counts_as_pass'])
    output_path = f'outputs/{model_id}/{task_id}'
    log_dir = os.path.join(output_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    def log(msg):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
    try:
        log(f'改写(aisf_rewrite) process 启动 (model={model_name}, task_id={task_id})')
        log(f'  被测模型 api_url: {api_url}')
        log(f'  eval_batch_size:  {eval_batch_size}')
        log(f'  limit:            {limit}')
        log(f'  generate_config:  {json.dumps(generate_config, ensure_ascii=False)}')
        try:
            test_workers = max(1, int(eval_batch_size)) if eval_batch_size is not None else 1
        except (ValueError, TypeError):
            test_workers = 1
        test_workers = max(1, int(generate_config.get('concurrency', test_workers) or test_workers))
        for arg in dataset_args:
            dataset_name = arg['dataset_name']
            excel_path = _locate_dataset_xlsx(dataset_name)
            if not excel_path:
                raise FileNotFoundError(f'在 {REWRITE_DATASET_PATH}/{dataset_name} 下未找到 xlsx 测试集文件')
            review_dir = os.path.join(output_path, 'reviews', model_id)
            report_dir = os.path.join(output_path, 'reports', model_id)
            os.makedirs(review_dir, exist_ok=True)
            os.makedirs(report_dir, exist_ok=True)
            result_xlsx = os.path.join(review_dir, f'{dataset_name}_{task_id}.xlsx')
            jsonl_path = os.path.join(review_dir, f'{dataset_name}.jsonl')
            df = pd.read_excel(excel_path, dtype=str)
            if limit is not None:
                df = df.head(limit).copy()
            df = df.reset_index(drop=True)
            if '维度' not in df.columns and '改写类型' in df.columns:
                df = df.rename(columns={'改写类型': '维度'})
            out_columns = ['messages_json', 'model_output', '宽松判定结果', '宽松判定原因', '严格判定结果', '严格判定原因', '模型改写文本', '严格匹配_当前输入', '严格匹配_模型输出', '要求关键字', '命中关键字', '缺失关键字', '黑名单词', '命中黑名单', '接口错误', 'status']
            for col in out_columns:
                if col not in df.columns:
                    df[col] = ''
            log(f'Test+Judge 阶段：共 {len(df)} 条，并行 {test_workers}')
            proc_start = time.time()
            completed = 0
            with ThreadPoolExecutor(max_workers=test_workers) as executor:
                futures = {executor.submit(_process_row, index, row, generate_config): index for index, row in df.iterrows()}
                for future in as_completed(futures):
                    index, detail = future.result()
                    for df_col, val in detail.items():
                        df.at[index, df_col] = _safe_text(val)
                    completed += 1
                    if completed % max(1, test_workers) == 0 or completed == len(df):
                        log(f'  进度: {completed}/{len(df)}')
            if len(df) and (df['status'] == 'error').all():
                raise RuntimeError('全部模型请求失败，请检查模型连接；未生成有效评测分数')
            log(f'Test+Judge 阶段完成，耗时 {time.time() - proc_start:.2f}s')
            rewrite_biz.save_result(df, result_xlsx)
            log(f'export: result excel={result_xlsx}')
            _convert_to_review_jsonl(result_xlsx, jsonl_path, dataset_name=dataset_name)
            log(f'export: jsonl(review)={jsonl_path}')
            report_file = _write_report_json(report_dir, dataset_name, model_name, df)
            log(f'export: report json={report_file}')
        finalize_task(task_id, model_name, model_id)
    except Exception as e:
        log(f'run_rewrite_proc error: {e}')
        traceback.print_exc()
        finalize_task(task_id, model_name, model_id, error=str(e))

if __name__ == '__main__':
    cfg = parse_config()
    run_rewrite_proc(model_config=cfg.get('model_config'), task_id=cfg.get('task_id'), model_id=cfg.get('model_id'), user_req=cfg.get('user_req'), thread_id=cfg.get('thread_id'))
