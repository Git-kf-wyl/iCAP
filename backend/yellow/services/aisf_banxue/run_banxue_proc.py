# Private iCAP Yellow business implementation. Do not publish.
"""伴学提参 —— 独立子进程入口（壳封装）。

由 run_test_server.py 以 subprocess 方式启动（见 CUSTOM_RULER2_PROC_DISPATCH['伴学提参']），
使该测评任务的存活不依赖 flask 服务进程（与 aisf_skillTiCan / aisf_guiTican 等业务一致）。

该业务下有三个独立子任务：提醒 / 总结 / 提参。
  - 提醒、总结：LLM judge（调用外部 judge 模型返回 {"result":"0/1","reason":...}）；
  - 提参：本地规则 judge（ast 解析字典，比对 studyDuration/breakCount 等参数）。

设计原则：不改动原工程业务逻辑（test_banxue_script_{ds,summary,tican}.py 仅把写死的
url/model_name/judge 配置提为模块级全局变量），本文件只做"壳封装"：
  1. 将项目根目录与业务源码目录加入 sys.path；
  2. 解析 --config 传入的运行参数（model_config / task_id / model_id / user_req 等）；
  3. 读取前端子任务参数 banxueBusinessParams（缺省用 generate_config.banxue_business_params），
     过滤 selected==True 的子任务；
  4. 逐子任务把被测模型 endpoint/model_name 与 judge 配置注入对应业务模块的模块级全局变量；
  5. 逐子任务执行 Test（壳内并发编排 process_row 调用被测模型）+ Judge（LLM 或规则）;
  6. 每个子任务产出 明细excel + 逐条jsonl，最后汇总生成 报告json；
  7. 由本文件兜底 finalize_task 收尾任务状态。
"""
import os
import sys
import json
import time
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

def _find_project_root():
    """向上查找项目根目录（run_test_server.py + services 所在），供 import 项目模块。"""
    d = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isfile(os.path.join(d, 'run_test_server.py')) and os.path.isdir(os.path.join(d, 'services')):
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
from utils.consts import BANXUE_DATASET_PATH
from utils.eval_utils import get_limit
from services.custom_proc_common import parse_config, finalize_task
from services.aisf_banxue import test_banxue_script_ds as biz_ds
from services.aisf_banxue import test_banxue_script_summary as biz_summary
from services.aisf_banxue import test_banxue_script_tican as biz_tican
_SUBTASK_BIZ = {'提醒': {'biz': biz_ds, 'eval_type': 'llm_judge'}, '总结': {'biz': biz_summary, 'eval_type': 'llm_judge'}, '提参': {'biz': biz_tican, 'eval_type': 'rule'}}

def _find_dataset_xlsx(dataset_dir):
    """在数据集目录下寻找第一个 .xlsx 测试集文件。"""
    if not os.path.isdir(dataset_dir):
        return None
    for fname in os.listdir(dataset_dir):
        fpath = os.path.join(dataset_dir, fname)
        if os.path.isfile(fpath) and os.path.splitext(fname)[1].lower() == '.xlsx':
            return fpath
    return None

def _safe_text(value):
    """Excel 单元格安全转字符串（与业务脚本 safe_text 一致）。"""
    if pd.isna(value):
        return ''
    return str(value)

def _write_report_json(report_dir, dataset_name, model_name, subsets):
    """生成总体结果 json（供前端 /v1/get_file_path / update_eval_res 读分）。

    subsets: 每个子任务一条 {name, num, score, correct_num}，统计各子任务准确率。
    总体 score 为全部子任务加权平均（total 加权）。
    """
    os.makedirs(report_dir, exist_ok=True)
    total_all = sum((s['num'] for s in subsets))
    correct_all = sum((s['correct_num'] for s in subsets))
    score_all = correct_all / total_all if total_all else 0
    report_map = {'name': f'{model_name}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_name, 'score': round(score_all, 4), 'metrics': [{'categories': [{'macro_score': round(score_all, 4), 'name': ['伴学提参'], 'num': total_all, 'score': round(score_all, 4), 'subsets': [{'name': s['name'], 'num': int(s['num']), 'score': round(s['score'], 4), 'correct_num': int(s['correct_num'])} for s in subsets]}], 'macro_score': round(score_all, 4), 'name': '伴学提参', 'num': total_all, 'score': round(score_all, 4)}], 'summary': {'总用例数': int(total_all), '严格通过数': int(correct_all), '严格通过率': round(score_all, 4), '子任务': subsets}}
    report_file = os.path.join(report_dir, f'{dataset_name}.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_map, f, ensure_ascii=False, indent=4)
    return report_file

def _build_subset_summary(result_xlsx_path):
    """从结果 excel 统计该子任务 total/pass（兼容 result 与 judge_result 两种判定列）。"""
    try:
        df = pd.read_excel(result_xlsx_path, dtype=str)
    except Exception:
        return (0, 0)
    total = len(df)
    if total == 0:
        return (0, 0)
    if 'result' in df.columns:
        pass_num = int((df.get('result') == '1').sum())
    elif 'judge_result' in df.columns:
        pass_num = int((df.get('judge_result') == '1').sum())
    else:
        pass_num = 0
    return (total, pass_num)

def _convert_to_review_jsonl(result_xlsx_path, jsonl_path, dataset_name='', subtask_name=''):
    """把子任务结果 excel 转换为前端使用的逐条 review jsonl。

    每行一条记录，choices[0].review 含 gold(ground_truth)/pred(model_output)/result(判定)。
    兼容 LLM judge（result/reason/raw_response/status 列）与规则 judge（judge_result/judge_reason 列）。
    格式与 aisf_skillTiCan / aisf_guiTican 产出的 review jsonl 基本一致。
    """
    df = pd.read_excel(result_xlsx_path, dtype=str)
    review_lines = []
    for idx, (_, row) in enumerate(df.iterrows()):
        cur_query = _safe_text(row.get('input') or row.get('cur_query'))
        ground_truth = _safe_text(row.get('ground_truth'))
        model_output = _safe_text(row.get('model_output'))
        if 'result' in df.columns:
            judge_result = _safe_text(row.get('result'))
            reason = _safe_text(row.get('reason'))
            status = _safe_text(row.get('status'))
            raw_response = _safe_text(row.get('raw_response'))
            is_pass = judge_result == '1'
            if status and status != 'done':
                is_pass = False
        else:
            judge_result = _safe_text(row.get('judge_result'))
            reason = _safe_text(row.get('judge_reason'))
            status = 'done'
            raw_response = model_output
            is_pass = judge_result == '1'

        def _to_int(v):
            try:
                return max(0, int(float(v)))
            except (ValueError, TypeError):
                return 0
        prompt_tokens = _to_int(row.get('prompt_tokens'))
        completion_tokens = _to_int(row.get('completion_tokens'))
        response_time = _to_int(row.get('times'))
        review_lines.append({'raw_input': {'Question': cur_query, 'expected': ground_truth, 'prompt': _safe_text(row.get('system_prompt')), 'context': _safe_text(row.get('context')), 'No': idx}, 'choices': [{'review': {'gold': ground_truth, 'pred': model_output, 'result': '1' if is_pass else '0', '判定结果': '通过' if is_pass else '不通过', 'judge_result': reason, 'raw_response': raw_response, 'status': status}, 'message': {'content': raw_response or model_output}}], 'index': idx, 'dialogue_round': str(idx), 'subset_name': subtask_name or dataset_name, 'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens, 'total_tokens': prompt_tokens + completion_tokens}, 'response_time': response_time})
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for line in review_lines:
            f.write(json.dumps(line, ensure_ascii=False) + '\n')

def _run_test(biz, df, workers, log):
    """壳内并发编排业务 process_row，调用被测模型填充 model_output/times/token 消耗。"""
    df = df.reset_index(drop=True)
    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(biz.process_row, index, row): index for index, row in df.iterrows()}
        for future in as_completed(futures):
            res = future.result()
            index = res['index']
            df.at[index, 'times'] = _safe_text(res.get('times'))
            df.at[index, 'model_output'] = _safe_text(res.get('model_output'))
            df.at[index, 'prompt_tokens'] = _safe_text(res.get('prompt_tokens') or 0)
            df.at[index, 'completion_tokens'] = _safe_text(res.get('completion_tokens') or 0)
            df.at[index, 'error'] = _safe_text(res.get('error'))
            completed += 1
            if completed % max(1, workers) == 0 or completed == len(df):
                log(f'    Test 进度: {completed}/{len(df)}')
    return df

def run_banxue_proc(model_config, task_id, model_id, user_req, thread_id):
    platform_model_name = model_config['info']['model_name']
    api_params = model_config['config']['api_params_available'][0]
    platform_api_url = api_params['endpoint']
    limit = get_limit(user_req.get('limit'))
    eval_batch_size = user_req.get('eval_batch_size')
    dataset_args = user_req['dataset_args']
    raw_generate_config = dataset_args[0].get('generate_config') if dataset_args else None
    if isinstance(raw_generate_config, str):
        try:
            raw_generate_config = json.loads(raw_generate_config)
        except Exception:
            raw_generate_config = {}
    generate_config = raw_generate_config or {}
    output_path = f'outputs/{model_id}/{task_id}'
    log_dir = os.path.join(output_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    def log(msg):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
    try:
        log(f'伴学提参 process 启动 (platform_model={platform_model_name}, task_id={task_id})')
        log(f'  平台被测模型 api_url: {platform_api_url}')
        log(f'  eval_batch_size: {eval_batch_size}')
        log(f'  limit:           {limit}')
        log(f"  平台被测模型 api_key: {str(api_params.get('api_key'))[:8]}...")
        dataset_name = dataset_args[0]['dataset_name'] if dataset_args else '伴学提参'
        dataset_dir = os.path.join(BANXUE_DATASET_PATH, dataset_name)
        excel_path = _find_dataset_xlsx(dataset_dir)
        if not excel_path:
            raise FileNotFoundError(f'在数据集目录 {dataset_dir} 下未找到 xlsx 测试集文件')
        review_dir = os.path.join(output_path, 'reviews', model_id)
        report_dir = os.path.join(output_path, 'reports', model_id)
        os.makedirs(review_dir, exist_ok=True)
        os.makedirs(report_dir, exist_ok=True)
        subset_list = dataset_args[0].get('subset_list', []) if dataset_args else []
        if not subset_list:
            raw_bps = dataset_args[0].get('banxueBusinessParams', []) if dataset_args else []
            if isinstance(raw_bps, list):
                subset_list = [bp.get('name') for bp in raw_bps if isinstance(bp, dict) and bp.get('selected') == True]
        log(f'子任务列表: {subset_list}')
        if not subset_list:
            log('[run_banxue_proc] subset_list 为空（未指定任何子任务），直接收尾。')
            finalize_task(task_id, platform_model_name, model_id)
            return
        model_url = generate_config.get('model_url') or platform_api_url
        model_name = generate_config.get('model_name') or platform_model_name
        try:
            max_workers_default = max(1, int(eval_batch_size)) if eval_batch_size is not None else 1
        except (ValueError, TypeError):
            max_workers_default = 1
        workers = max(1, int(generate_config.get('max_workers') or max_workers_default))
        judge_url = generate_config.get('judge_url')
        judge_token = generate_config.get('judge_api_token') or generate_config.get('api_token')
        judge_model = generate_config.get('judge_model_name')
        judge_concurrency = int(generate_config.get('judge_concurrency') or workers)
        judge_temperature = float(generate_config.get('judge_temperature', 0.0))
        judge_max_retries = int(generate_config.get('judge_max_retries', 3))
        judge_timeout = int(generate_config.get('judge_timeout', 120))
        judge_overload_stop = int(generate_config.get('judge_overload_stop_threshold', 5))
        subsets = []
        for subtask_name in subset_list:
            meta = _SUBTASK_BIZ.get(subtask_name)
            if meta is None:
                log(f'  [skip] 未知子任务: {subtask_name}')
                continue
            biz = meta['biz']
            eval_type = meta['eval_type']
            sheet_name = subtask_name
            biz.url = model_url
            biz.model_name = model_name
            log(f"\n{'#' * 60}")
            log(f'# 子任务: {subtask_name} | sheet={sheet_name} | eval_type={eval_type}')
            log(f'#   被测模型: {model_name} @ {model_url} | 并行={workers}')
            log(f"{'#' * 60}")
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            if 'context' not in df.columns and hasattr(biz, 'build_history'):
                df['context'] = df.apply(biz.build_history, axis=1)
            if limit is not None and limit > 0:
                df = df.head(limit).copy()
            for col in ['result', 'reason', 'raw_response', 'status']:
                if col not in df.columns:
                    df[col] = ''
            test_xlsx = os.path.join(review_dir, f'{dataset_name}_{subtask_name}_test.xlsx')
            result_xlsx = os.path.join(review_dir, f'{dataset_name}_{subtask_name}_{task_id}.xlsx')
            jsonl_path = os.path.join(review_dir, f'{dataset_name}_{subtask_name}.jsonl')
            log(f'  Test 阶段：共 {len(df)} 条，并行 {workers}')
            test_start = time.time()
            df = _run_test(biz, df, workers, log)
            biz.atomic_save_excel(df, test_xlsx)
            log(f'  Test 完成，耗时 {time.time() - test_start:.2f}s，中间产物: {test_xlsx}')
            if eval_type == 'llm_judge':
                j_url = judge_url or biz.judge_url
                j_token = judge_token or biz.api_token
                j_model = judge_model or biz.judge_model_name
                j_concurrency = judge_concurrency
                j_temperature = judge_temperature if 'judge_temperature' in generate_config else getattr(biz, 'judge_temperature', 0.0)
                j_max_retries = judge_max_retries if 'judge_max_retries' in generate_config else getattr(biz, 'judge_max_retries', 3)
                j_timeout = judge_timeout if 'judge_timeout' in generate_config else getattr(biz, 'judge_timeout', 120)
                j_overload_stop = judge_overload_stop if 'judge_overload_stop_threshold' in generate_config else getattr(biz, 'judge_overload_stop_threshold', 5)
                log(f'  Judge 阶段：url={j_url}, model={j_model}, 并发={j_concurrency}')
                judge_start = time.time()
                biz.evaluate_dataframe(df=df, judge_url=j_url, api_token=j_token, judge_model_name=j_model, output_excel_path=result_xlsx, concurrency=j_concurrency, temperature=j_temperature, max_retries=j_max_retries, timeout=j_timeout, overload_stop_threshold=j_overload_stop)
                log(f'  Judge 完成，耗时 {time.time() - judge_start:.2f}s，最终产物: {result_xlsx}')
            elif eval_type == 'rule':
                log(f'  Judge 阶段：本地规则判定')
                for idx in df.index:
                    gt = df.at[idx, 'ground_truth']
                    mo = df.at[idx, 'model_output']
                    judge_dict = biz.judge(_safe_text(gt), _safe_text(mo))
                    df.at[idx, 'result'] = judge_dict.get('result', '0')
                    df.at[idx, 'reason'] = judge_dict.get('reason', '')
                    df.at[idx, 'raw_response'] = df.at[idx, 'model_output']
                    df.at[idx, 'status'] = 'done'
                biz.atomic_save_excel(df, result_xlsx)
                log(f'  规则判定完成，最终产物: {result_xlsx}')
            else:
                log(f'  [skip] 未知 eval_type: {eval_type}')
                continue
            _convert_to_review_jsonl(result_xlsx, jsonl_path, dataset_name=dataset_name, subtask_name=subtask_name)
            log(f'  export: jsonl(review)={jsonl_path}')
            total, pass_num = _build_subset_summary(result_xlsx)
            acc = pass_num / total if total else 0
            subsets.append({'name': subtask_name, 'num': total, 'score': acc, 'correct_num': pass_num})
            log(f'  summary: total={total}, pass={pass_num}, acc={acc:.4f}')
        report_file = _write_report_json(report_dir, dataset_name, platform_model_name, subsets)
        log(f'export: report json={report_file}')
        finalize_task(task_id, platform_model_name, model_id)
    except Exception as e:
        log(f'run_banxue_proc error: {e}')
        traceback.print_exc()
        finalize_task(task_id, platform_model_name, model_id, error=str(e))

if __name__ == '__main__':
    cfg = parse_config()
    run_banxue_proc(model_config=cfg.get('model_config'), task_id=cfg.get('task_id'), model_id=cfg.get('model_id'), user_req=cfg.get('user_req'), thread_id=cfg.get('thread_id'))
