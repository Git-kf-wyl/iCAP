# Private iCAP Yellow business implementation. Do not publish.
"""Coordinator —— 独立子进程入口（壳封装）。

由 run_test_server.py 以 subprocess 方式启动（见 CUSTOM_RULER2_PROC_DISPATCH['Coordinator']），
使该测评任务的存活不依赖 flask 服务进程（与 aisf_guiTican / aisf_banxue 等业务一致）。

设计原则：不改动原工程业务逻辑（Coordinator_script.py 仅把写死的 url/model_name/judge 配置
提为模块级全局变量），本文件只做"壳封装"：
  1. 将项目根目录与业务源码目录加入 sys.path；
  2. 解析 --config 传入的运行参数（model_config / task_id / user_req 等）；
  3. 把被测模型 endpoint 与并行数注入 Coordinator_script 的模块级配置；
  4. Test 阶段：壳内并发编排 Coordinator_script.process_row，调用被测模型产出 model_output；
  5. Judge 阶段：调用 Coordinator_script.evaluate_dataframe，用本地规则/相似度判定；
  6. 产出四份文件：logs/eval_log.log（由 spawn_eval_proc 重定向写入）+ 结果 excel
     + review jsonl + 总体结果 json；
  7. 由本文件兜底 finalize_task 收尾任务状态。
"""
from state_storage import open_state, state_exists, state_isfile
import os
import sys
import json
import math
import time
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

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
from utils.consts import COORDINATOR_DATASET_PATH
from utils.eval_utils import get_limit
from services.custom_proc_common import parse_config, finalize_task, extract_generation_config
from services.aisf_coordinator import Coordinator_script as coord_biz

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

def _safe_text(value):
    """Excel 单元格安全转字符串（与 Coordinator_script.safe_text 一致）。"""
    if pd.isna(value):
        return ''
    return str(value)

def _build_coordinator_subsets(result_df):
    """按测试集 excel 的 S1场景 列统计各意图类别（单意图/两意图/三意图）的通过率。

    参考 aisf_yitu 的 gen_report_json：按场景分组成 subsets。
    """
    scene_labels = ('单意图', '两意图', '三意图')
    subsets = []
    for label in scene_labels:
        subset_df = result_df[result_df['S1场景'] == label] if 'S1场景' in result_df.columns else result_df.iloc[0:0]
        subset_total = len(subset_df)
        if subset_total > 0:
            subset_pass = int((subset_df.get('result') == '1').sum())
            subset_score = subset_pass / subset_total
        else:
            subset_pass = 0
            subset_score = 0
        subsets.append({'name': label, 'num': subset_total, 'score': round(subset_score, 4), 'correct_num': subset_pass})
    return subsets

def _write_report_json(report_dir, dataset_name, model_name, total, pass_num, result_df=None):
    """生成总体结果 json（供前端 /v1/get_file_path / update_eval_res 读分）。

    统计维度：总通过率（result 为 1 的占比），与 Coordinator 原始工程口径一致。
    若传入 result_df（含 S1场景 列），则将 subsets 细分为单意图/两意图/三意图三个分数，
    参考 aisf_yitu 的 gen_report_json 分组格式。
    """
    os.makedirs(report_dir, exist_ok=True)
    acc = pass_num / total if total else 0
    if result_df is not None and 'S1场景' in result_df.columns:
        subsets = _build_coordinator_subsets(result_df)
    else:
        subsets = [{'name': 'Coordinator', 'num': total, 'score': round(acc, 4), 'correct_num': int(pass_num)}]
    report_map = {'name': f'{model_name}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_name, 'score': round(acc, 4), 'metrics': [{'categories': [{'macro_score': round(acc, 4), 'name': ['Coordinator'], 'num': total, 'score': round(acc, 4), 'subsets': subsets}], 'macro_score': round(acc, 4), 'name': 'Coordinator', 'num': total, 'score': round(acc, 4)}], 'summary': {'总用例数': int(total), '严格通过数': int(pass_num), '严格通过率': round(acc, 4)}}
    report_file = os.path.join(report_dir, f'{dataset_name}.json')
    with open_state(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_map, f, ensure_ascii=False, indent=4)
    return report_file

def _safe_json_str(value):
    """安全返回单元格的原始 JSON 字符串（非空才返回），nan/空则返回 None。"""
    if value is None:
        return None
    if isinstance(value, float):
        try:
            if math.isnan(value):
                return None
        except TypeError:
            pass
    s = str(value).strip()
    if not s or s.lower() == 'nan':
        return None
    return s

def _build_context_from_history(row):
    """由 query1~answer5 重建多轮对话上下文（与 gaixie context 展示格式一致）。

    Returns:
        str: "[user]: xxx
[assistant]: xxx
..." 形式的多行文本。
    """
    lines = []
    for i in range(1, 100):
        q_val = row.get(f'query{i}') if hasattr(row, 'get') else None
        if pd.notna(q_val) and str(q_val).strip() and (str(q_val).strip().lower() != 'nan'):
            lines.append(f'[user]: {str(q_val)}')
        a_val = row.get(f'answer{i}') if hasattr(row, 'get') else None
        if pd.notna(a_val) and str(a_val).strip() and (str(a_val).strip().lower() != 'nan'):
            lines.append(f'[assistant]: {str(a_val)}')
    return '\n'.join(lines)

def _build_tools_json_array(row):
    """合并 tool1~tool5 各列的 JSON 字符串为一个 JSON 数组字符串（跳过空值）。

    各 tool 列本身是 JSON 字符串（如 {"role":"tool", ...}），此处拼成
    "[ {...}, {...} ]" 形式，前端 JSON.parse 后即可美化展示。
    """
    items = []
    for i in range(1, 6):
        v = row.get(f'tool{i}') if hasattr(row, 'get') else None
        s = _safe_json_str(v)
        if s is not None:
            items.append(s)
    if not items:
        return None
    return '[\n' + ',\n'.join(items) + '\n]'

def _convert_to_review_jsonl(result_xlsx_path, jsonl_path, dataset_name=''):
    """把结果 excel 转换为前端使用的逐条 review jsonl。

    每行一条记录，choices[0].review 含 gold(ground_truth)/pred(model_output)/result(judge 判定)。
    格式与 aisf_guiTican / aisf_banxue 产出的 review jsonl 基本一致。

    新增：
      - raw_input.context：由 query1~answer5 重建的多轮对话上下文（[user]:/[assistant]: 文本）。
      - 顶层 excel_info：memory_location_time / user_input / assistant_skill_select / tools 四个属性，
        前端各自一个框、以 JSON 美化展示。
    """
    df = pd.read_excel(result_xlsx_path, dtype=str)
    review_lines = []
    for idx, (_, row) in enumerate(df.iterrows()):
        cur_query = _safe_text(row.get('user_input') or row.get('cur_query'))
        ground_truth = _safe_text(row.get('ground_truth'))
        model_output = _safe_text(row.get('model_output'))
        judge_result = _safe_text(row.get('result'))
        reason = _safe_text(row.get('reason'))
        raw_response = _safe_text(row.get('raw_response'))
        status = _safe_text(row.get('status'))
        is_pass = judge_result == '1'
        if status and status != 'done':
            is_pass = False
        history_context = _build_context_from_history(row)
        excel_info = {'memory_location_time': _safe_json_str(row.get('memory_location_time')), 'user_input': _safe_json_str(row.get('user_input')), 'assistant_skill_select': _safe_json_str(row.get('assistant_skill_select')), 'tools': _build_tools_json_array(row)}

        def _to_int(v):
            try:
                return max(0, int(float(v)))
            except (ValueError, TypeError):
                return 0
        prompt_tokens = _to_int(row.get('prompt_tokens'))
        completion_tokens = _to_int(row.get('completion_tokens'))
        response_time = _to_int(row.get('times'))
        review_lines.append({'raw_input': {'Question': cur_query, 'expected': ground_truth, 'prompt': _safe_text(row.get('system_prompt')), 'context': history_context, 'No': idx}, 'excel_info': excel_info, 'choices': [{'review': {'gold': ground_truth, 'pred': model_output, 'result': '1' if is_pass else '0', '判定结果': '通过' if is_pass else '不通过', 'judge_result': reason, 'raw_response': raw_response, 'status': status}, 'message': {'content': raw_response or model_output}}], 'index': idx, 'dialogue_round': str(idx), 'subset_name': dataset_name or 'Coordinator', 'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens, 'total_tokens': prompt_tokens + completion_tokens}, 'response_time': response_time})
    with open_state(jsonl_path, 'w', encoding='utf-8') as f:
        for line in review_lines:
            f.write(json.dumps(line, ensure_ascii=False) + '\n')

def _build_summary(result_xlsx_path):
    """从结果 excel 统计总通过率（仅 result=='1' 的占比，口径与 Coordinator 原始工程一致）。"""
    try:
        df = pd.read_excel(result_xlsx_path, dtype=str)
    except Exception:
        return (0, 0)
    total = len(df)
    if total == 0:
        return (0, 0)
    pass_num = int((df.get('result', pd.Series([])) == '1').sum())
    return (total, pass_num)

def run_coordinator_proc(model_config, task_id, model_id, user_req, thread_id):
    model_name = model_config['info']['model_name']
    api_params = model_config['config']['api_params_available'][0]
    api_url = api_params['endpoint']
    limit = get_limit(user_req.get('limit'))
    eval_batch_size = user_req.get('eval_batch_size')
    dataset_args = user_req['dataset_args']
    generate_config = extract_generation_config(user_req)
    output_path = f'outputs/{model_id}/{task_id}'
    log_dir = os.path.join(output_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    def log(msg):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
    try:
        log(f'Coordinator process 启动 (model={model_name}, task_id={task_id})')
        log(f'  被测模型 api_url: {api_url}')
        log(f'  eval_batch_size:  {eval_batch_size}')
        log(f'  limit:            {limit}')
        try:
            test_workers = max(1, int(eval_batch_size)) if eval_batch_size is not None else 1
        except (ValueError, TypeError):
            test_workers = 1
        for arg in dataset_args:
            dataset_name = arg['dataset_name']
            dataset_dir = os.path.join(COORDINATOR_DATASET_PATH, dataset_name)
            excel_path = _find_dataset_xlsx(dataset_dir)
            if not excel_path:
                raise FileNotFoundError(f'在数据集目录 {dataset_dir} 下未找到 xlsx 测试集文件')
            review_dir = os.path.join(output_path, 'reviews', model_id)
            report_dir = os.path.join(output_path, 'reports', model_id)
            os.makedirs(review_dir, exist_ok=True)
            os.makedirs(report_dir, exist_ok=True)
            test_xlsx = os.path.join(review_dir, f'{dataset_name}_test.xlsx')
            result_xlsx = os.path.join(review_dir, f'{dataset_name}_{task_id}.xlsx')
            jsonl_path = os.path.join(review_dir, f'{dataset_name}.jsonl')
            coord_biz.url = api_url
            coord_biz.model_name = model_name
            coord_biz.COORDINATOR_MODEL_URL = api_url
            coord_biz.COORDINATOR_MODEL_NAME = model_name
            df = pd.read_excel(excel_path, dtype=str)
            if limit is not None:
                df = df.head(limit).copy()
            if 'context' not in df.columns:
                df['context'] = df.apply(coord_biz.build_history, axis=1)
            df = df.reset_index(drop=True)
            log(f'Test 阶段：共 {len(df)} 条，并行 {test_workers}')
            test_start = time.time()
            completed = 0
            with ThreadPoolExecutor(max_workers=test_workers) as executor:
                futures = {executor.submit(coord_biz.process_row, index, row): index for index, row in df.iterrows()}
                for future in as_completed(futures):
                    res = future.result()
                    index = res['index']
                    df.at[index, 'times'] = _safe_text(res.get('times'))
                    df.at[index, 'model_output'] = _safe_text(res.get('model_output'))
                    df.at[index, 'prompt_tokens'] = _safe_text(res.get('prompt_tokens') or 0)
                    df.at[index, 'completion_tokens'] = _safe_text(res.get('completion_tokens') or 0)
                    df.at[index, 'error'] = _safe_text(res.get('error'))
                    completed += 1
                    if completed % max(1, test_workers) == 0 or completed == len(df):
                        log(f'  Test 进度: {completed}/{len(df)}')
            coord_biz.atomic_save_excel(df, test_xlsx)
            log(f'Test 阶段完成，耗时 {time.time() - test_start:.2f}s，中间产物: {test_xlsx}')
            judge_concurrency = generate_config.get('concurrency', test_workers if eval_batch_size is not None else coord_biz.COORDINATOR_JUDGE_CONCURRENCY)
            judge_temperature = generate_config.get('temperature', coord_biz.COORDINATOR_JUDGE_TEMPERATURE)
            judge_max_retries = generate_config.get('max_retries', coord_biz.COORDINATOR_JUDGE_MAX_RETRIES)
            judge_timeout = generate_config.get('timeout', coord_biz.COORDINATOR_JUDGE_TIMEOUT)
            judge_overload_stop = generate_config.get('overload_stop_threshold', coord_biz.COORDINATOR_JUDGE_OVERLOAD_STOP_THRESHOLD)
            log(f'Judge 阶段：本地规则/相似度判定，并发={judge_concurrency}')
            judge_start = time.time()
            judge_url = generate_config.get('judge_url', coord_biz.COORDINATOR_JUDGE_URL)
            api_token = generate_config.get('api_token', coord_biz.COORDINATOR_JUDGE_API_TOKEN)
            judge_model_name = generate_config.get('judge_model_name', coord_biz.COORDINATOR_JUDGE_MODEL_NAME)
            result_df = coord_biz.evaluate_dataframe(df=df, judge_url=judge_url, api_token=api_token, judge_model_name=judge_model_name, output_excel_path=result_xlsx, concurrency=int(judge_concurrency), temperature=float(judge_temperature), max_retries=int(judge_max_retries), timeout=int(judge_timeout), overload_stop_threshold=int(judge_overload_stop))
            log(f'Judge 阶段完成，耗时 {time.time() - judge_start:.2f}s，最终产物: {result_xlsx}')
            _convert_to_review_jsonl(result_xlsx, jsonl_path, dataset_name=dataset_name)
            log(f'export: jsonl(review)={jsonl_path}')
            total, pass_num = _build_summary(result_xlsx)
            log(f'summary: total={total}, pass={pass_num}, acc={(pass_num / total if total else 0):.4f}')
            report_file = _write_report_json(report_dir, dataset_name, model_name, total, pass_num, result_df=result_df)
            log(f'export: report json={report_file}')
        finalize_task(task_id, model_name, model_id)
    except Exception as e:
        log(f'run_coordinator_proc error: {e}')
        traceback.print_exc()
        finalize_task(task_id, model_name, model_id, error=str(e))

if __name__ == '__main__':
    cfg = parse_config()
    run_coordinator_proc(model_config=cfg.get('model_config'), task_id=cfg.get('task_id'), model_id=cfg.get('model_id'), user_req=cfg.get('user_req'), thread_id=cfg.get('thread_id'))
