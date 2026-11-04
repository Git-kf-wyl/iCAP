# Private iCAP Yellow business implementation. Do not publish.
"""记忆 —— 独立子进程入口。

由 run_test_server.py 以 subprocess 方式启动，取代原先在服务进程内运行的
run_memory 线程，使得该测评任务的存活不再依赖 flask 服务进程。
"""
from state_storage import open_state, state_exists, state_isfile
import json
import os
import sys
import time
import traceback
from datetime import datetime
import jsonlines as jsonl
import pandas as pd

def _find_project_root():
    """向上查找项目根目录，使其下的 backend 包可被 import（backend.xxx 前缀导入）。"""
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
from services.custom_proc_common import parse_config, update_task, finalize_task, extract_generation_config
from utils.consts import MEMORY_DATASET_PATH
from utils.eval_utils import get_generate_config, get_limit
from services.aisf_memory.runMemoryServer import _call_model_direct, _call_judge_model, _memory_init_fewshot, _memory_build_fewshot_prompt, _memory_parse_id_list, _strip_json_wrapper, _MEMORY_EVAL_PROMPTS

def run_memory_proc(model_config, task_id, model_id, user_req, thread_id):
    """原 run_test_server.run_memory 的独立进程版本。"""
    all_start_time = time.time()
    print(f'开始记忆测评')
    model_name = model_config['info']['model_name']
    output_path = f'outputs/{model_id}/{task_id}'
    log_dir = os.path.join(output_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'eval_log.log')
    log_file = open_state(log_path, 'w', encoding='utf-8')
    log_file.write(f'[{datetime.now()}] run_memory_proc 启动 | model={model_id} | task_id={task_id}\n\n')

    def log(msg):
        log_file.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        log_file.flush()
    api_url = model_config['config']['api_params_available'][0]['endpoint']
    api_key = model_config['config']['api_params_available'][0]['api_key'] or 'EMPTY'
    temperature = user_req.get('temperature')
    limit = get_limit(user_req.get('limit'))
    dataset_args = user_req['dataset_args']
    dataset_names = [arg.get('dataset_name', '') for arg in dataset_args]
    retry_content_none = user_req.get('retry_content_none')
    use_cache = user_req.get('use_cache')
    retry_enabled = retry_content_none is not None and bool(use_cache)
    log(f'model_id:      {model_id}')
    log(f'model_name:    {model_name}')
    log(f'task_id:       {task_id}')
    log(f'api_url:       {api_url}')
    log(f'api_key:       {api_key[:8]}...')
    log(f'temperature:   {temperature}')
    log(f'limit:         {limit}')
    log(f'datasets:      {dataset_names}')
    log('')
    try:
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(os.path.join(output_path, 'reviews', model_id), exist_ok=True)
        public_conf = [{'api_url': param['endpoint'], 'api_key': param['api_key'] if param['api_key'] else 'EMPTY', 'model': model_name} for param in model_config['config']['api_params_available']]
        api_conf = public_conf[0]
        dataset_arg = user_req['dataset_args'][0]
        generation_config = extract_generation_config(user_req)
        if not generation_config:
            try:
                generation_config = get_generate_config(model_config['config']['params'], model_name)
            except Exception:
                generation_config = {}
        update_task(task_id, progress=0.0)
        memory_params_list = [item for item in dataset_arg.get('memoryBusinessParams', []) if item.get('selected') == True]
        if not memory_params_list:
            log('[run_memory_proc] memoryBusinessParams is empty, nothing to do.')
            finalize_task(task_id, model_name, model_id)
            log_file.close()
            return
        total_tasks = len(memory_params_list)
        overall_results = {}
        _memory_report_subsets = []
        for task_idx, bp in enumerate(memory_params_list):
            task_name = bp['name']
            prompt_version = bp.get('prompt_version', 'v1.0')
            eval_type = bp.get('eval_type', 'llm_judge')
            use_fewshot = bp.get('use_fewshot', False)
            selected_prompt_file = bp.get('selectedPromptFile', '')
            selected_test_file = bp.get('selectedTestFile', '')
            dataset_name = dataset_arg.get('dataset_name', '')
            task_dir = os.path.join(MEMORY_DATASET_PATH, dataset_name, task_name)
            if not state_exists(task_dir):
                log(f'[skip] 任务目录不存在: {task_dir}')
                continue
            xlsx_filename = os.path.basename(selected_test_file) if selected_test_file else '测试用例.xlsx'
            xlsx_path = os.path.join(task_dir, xlsx_filename)
            if not state_exists(xlsx_path):
                log(f'[skip] 测试集文件不存在: {xlsx_path}')
                continue
            df = pd.read_excel(xlsx_path, sheet_name='Sheet1')
            answer_col = f'answer_{model_id}_{prompt_version}'
            output_xlsx_path = os.path.join(output_path, 'reviews', model_id, f"{dataset_arg['dataset_name']}_{task_name}_{task_id}.xlsx")
            if not selected_prompt_file:
                log(f'[skip] {task_name} 未选择 prompt 文件')
                continue
            prompt_filename = os.path.basename(selected_prompt_file)
            prompt_path = os.path.join(task_dir, prompt_filename)
            if not state_exists(prompt_path):
                log(f'[skip] prompt 文件不存在: {prompt_path}')
                continue
            with open_state(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            if answer_col not in df.columns:
                df[answer_col] = None
            reuse_map = {}
            if retry_enabled and state_exists(output_xlsx_path):
                try:
                    prev_df = pd.read_excel(output_xlsx_path, sheet_name='Sheet1')
                    for prev_idx, prow in prev_df.iterrows():
                        if prev_idx >= len(df):
                            continue
                        raw = prow.get(answer_col)
                        if pd.isna(raw):
                            continue
                        raw_str = str(raw).strip()
                        if not raw_str:
                            continue
                        if retry_content_none:
                            if raw_str.startswith('[ERROR]') or raw_str.startswith('[TIMEOUT]') or '[TIMEOUT]' in raw_str or ('[ERROR]' in raw_str):
                                continue
                        df.at[prev_idx, answer_col] = raw_str
                        reuse_map[prev_idx] = prow
                    log(f"续测({('内容续测' if retry_content_none else '索引续测')})：复用旧结果 {len(reuse_map)} 行")
                except Exception as e:
                    log(f'续测：读取旧结果Excel失败({output_xlsx_path})，将全量重跑：{e}')
                    reuse_map = {}
            fewshot_data = None
            if use_fewshot:
                fewshot_data = _memory_init_fewshot(task_dir)
            log(f"\n{'#' * 60}")
            log(f'# Phase 1 - 测试: {task_name} ({prompt_version})({prompt_filename})')
            log(f'本任务系统prompt：{prompt_template}')
            log(f"{'#' * 60}")
            raw_limit = user_req.get('limit')
            limit = get_limit(raw_limit)
            if limit is None or limit <= 0:
                limit = len(df)
            for idx in df.index[:limit]:
                if idx in reuse_map:
                    continue
                user_query = df.at[idx, 'user_query']
                if pd.isna(user_query):
                    continue
                source_info = df.at[idx, '用例来源'] if '用例来源' in df.columns else ''
                log(f'  [{idx}] source={source_info} | {str(user_query)[:60]}...')
                if use_fewshot and fewshot_data:
                    system_prompt = _memory_build_fewshot_prompt(prompt_template, str(user_query), fewshot_data)
                else:
                    system_prompt = prompt_template
                result = _call_model_direct(api_conf['api_url'], api_conf['api_key'], api_conf['model'], system_prompt, str(user_query), generation_config, api_conf.get('non_openai_format', False))
                if isinstance(result, dict):
                    model_output = result.get('content')
                    status = result.get('status', 'error')
                    if status == 'success':
                        model_output = _strip_json_wrapper(model_output)
                        df.at[idx, answer_col] = model_output if model_output is not None else ''
                    else:
                        error_output = f"[{status.upper()}] {result.get('message', '')}"
                        df.at[idx, answer_col] = error_output
                    log(f'    -> status={status} | {str(df.at[idx, answer_col])[:120]}')
                else:
                    if result is not None:
                        df.at[idx, answer_col] = _strip_json_wrapper(result)
                    else:
                        df.at[idx, answer_col] = '[ERROR] 模型调用失败（未知原因）'
                    log(f'    -> {str(result)[:120]}')
                df.to_excel(output_xlsx_path, index=False, engine='openpyxl')
            log(f'  测试完成：{task_name}')
            log(f"\n{'#' * 60}")
            log(f'# Phase 2 - 评测: {task_name} ({prompt_version})')
            log(f"{'#' * 60}")
            eval_prompt_text = None
            if eval_type == 'llm_judge':
                judge_prompt = bp.get('judge_prompt', '')
                if judge_prompt and isinstance(judge_prompt, str) and judge_prompt.strip():
                    eval_prompt_text = judge_prompt.strip()
                    log(f'  使用前端传入的临时裁判 prompt:{eval_prompt_text}')
                else:
                    eval_prompt_text = _MEMORY_EVAL_PROMPTS.get(task_name)
                    if eval_prompt_text is None:
                        log(f'  [skip] {task_name} 没有默认评测 prompt 配置，且未传入临时 prompt')
                        continue
                    log(f'  使用默认裁判 prompt:{eval_prompt_text}')
            else:
                log(f'  {task_name} 为 {eval_type} 评测，跳过 LLM 裁判 prompt 配置')
            eval_col = 'eval_' + answer_col
            if eval_col not in df.columns:
                df[eval_col] = None
            correct = 0
            total_eval = 0
            review_records = []
            for idx in df.index[:limit]:
                raw = df.at[idx, answer_col]
                if pd.isna(raw):
                    continue
                user_query = df.at[idx, 'user_query']
                source_info = df.at[idx, '用例来源'] if '用例来源' in df.columns else ''
                ref_answer = df.at[idx, '参考答案'] if '参考答案' in df.columns else df.at[idx, 'ground_truth'] if 'ground_truth' in df.columns else ''
                if retry_enabled and idx in reuse_map:
                    prev_eval = reuse_map[idx].get(eval_col) if eval_col in reuse_map[idx] else None
                    if pd.isna(prev_eval) or not prev_eval:
                        prev_eval = ''
                    try:
                        judge_result = json.loads(str(prev_eval))
                        is_correct = bool(judge_result.get('正确', False))
                        reason = str(judge_result.get('原因', ''))
                    except (ValueError, TypeError):
                        judge_result = {'正确': False, '原因': '旧评测结果缺失'}
                        is_correct = False
                        reason = '旧评测结果缺失'
                    total_eval += 1
                    if is_correct:
                        correct += 1
                    status = '✓' if is_correct else '✗'
                    log(f'  [{idx}] {source_info} {status}(续测复用) {reason[:80]}')
                    review_records.append({'raw_input': {'Question': str(user_query), 'No': idx}, 'choices': [{'review': {'gold': str(ref_answer), 'pred': str(raw), 'eval_type': eval_type, 'judge_result': judge_result, 'reason': reason, 'result': is_correct}, 'message': {'content': str(raw)}}], 'index': idx, 'subset_name': task_name})
                    continue
                total_eval += 1
                if eval_type == 'llm_judge':
                    if eval_prompt_text is None:
                        log(f'  [skip] {task_name} 没有评测 prompt 配置')
                        continue
                    judge_result = _call_judge_model(eval_prompt_text, str(user_query), raw, str(ref_answer))
                    is_correct = judge_result.get('正确', False)
                    reason = judge_result.get('原因', '')
                    df.at[idx, eval_col] = json.dumps(judge_result, ensure_ascii=False)
                elif eval_type == 'parse_based':
                    pred_ids, is_valid = _memory_parse_id_list(raw)
                    ref_raw = df.at[idx, '参考答案'] if '参考答案' in df.columns else df.at[idx, 'ground_truth'] if 'ground_truth' in df.columns else ''
                    ref_ids, _ = _memory_parse_id_list(str(ref_raw)) if pd.notna(ref_raw) else ([], True)
                    if is_valid and pred_ids is not None:
                        pred_set = set(pred_ids)
                        ref_set = set(ref_ids)
                        fn = len(ref_set - pred_set)
                        fp = len(pred_set - ref_set)
                        if fn > 0:
                            missing = sorted(ref_set - pred_set)
                            is_correct = False
                            reason = f'漏提(严重): 缺失 {missing}, pred={sorted(pred_set)}, ref={sorted(ref_set)}'
                        elif fp > 0:
                            extra = sorted(pred_set - ref_set)
                            is_correct = True
                            reason = f'多提但提全: 多带 {extra}, pred={sorted(pred_set)}, ref={sorted(ref_set)}'
                        else:
                            is_correct = True
                            reason = '完全匹配' if pred_set else '完全匹配(空)'
                    else:
                        is_correct = False
                        reason = '格式错误' if pd.notna(raw) else '未运行'
                    judge_result = {'正确': is_correct, '原因': reason}
                    df.at[idx, eval_col] = json.dumps(judge_result, ensure_ascii=False)
                    eval_prompt_text = None
                else:
                    log(f'  [skip] 未知 eval_type: {eval_type}')
                    continue
                if is_correct:
                    correct += 1
                status = '✓' if is_correct else '✗'
                log(f'  [{idx}] {source_info} {status} {reason[:80]}')
                review_records.append({'raw_input': {'Question': str(user_query), 'No': idx}, 'choices': [{'review': {'gold': str(ref_answer), 'pred': str(raw) if pd.notna(raw) else '', 'eval_type': eval_type, 'judge_result': judge_result, 'reason': reason, 'result': is_correct}, 'message': {'content': str(raw) if pd.notna(raw) else ''}}], 'index': idx, 'subset_name': task_name})
            acc = correct / total_eval if total_eval > 0 else 0
            log(f'\n  --- {task_name} ({prompt_version}) ---')
            log(f'  准确率：{correct}/{total_eval} = {acc:.1%}')
            overall_results[task_name] = {'total': total_eval, 'correct': correct, 'accuracy': acc}
            df.to_excel(output_xlsx_path, index=False, engine='openpyxl')
            review_dir = os.path.join(output_path, 'reviews', model_id)
            os.makedirs(review_dir, exist_ok=True)
            jsonl_path = os.path.join(review_dir, f"{dataset_arg['dataset_name']}_{task_name}.jsonl")
            with jsonl.open(jsonl_path, mode='w') as writer:
                for rec in review_records:
                    writer.write(rec)
            log(f'  jsonl 评审文件已生成: {jsonl_path}')
            _memory_report_subsets.append({'name': task_name, 'num': total_eval, 'score': acc, 'correct_num': correct})
            update_task(task_id, progress=(task_idx + 1) / total_tasks)
        log(f"\n{'#' * 60}")
        log(f'# Phase 3 - 汇总')
        log(f"{'#' * 60}")
        if overall_results:
            rows = []
            for tname, tres in overall_results.items():
                rows.append({'任务': tname, '样本数': tres['total'], '正确数': tres['correct'], '准确率': f"{tres['accuracy']:.1%}"})
            summary_df = pd.DataFrame(rows)
            summary_path = os.path.join(output_path, f'{model_id}_记忆评测汇总_{task_id}.xlsx')
            summary_df.to_excel(summary_path, index=False, engine='openpyxl')
            log(f'  汇总表已保存至: {summary_path}')
            log(f"\n  {'任务':<30} {'样本数':<8} {'正确数':<8} {'准确率':<8}")
            log(f"  {'-' * 54}")
            for _, row in summary_df.iterrows():
                log(f"  {row['任务']:<30} {row['样本数']:<8} {row['正确数']:<8} {row['准确率']:<8}")
            if _memory_report_subsets:
                total_all = sum((s['num'] for s in _memory_report_subsets))
                correct_all = sum((s['correct_num'] for s in _memory_report_subsets))
                score_all = correct_all / total_all if total_all > 0 else 0
                report_map = {'name': f"{model_name}_{dataset_arg['dataset_name']}", 'dataset_name': dataset_arg['dataset_name'], 'model_name': model_name, 'score': score_all, 'metrics': [{'name': '记忆测评', 'macro_score': score_all, 'num': total_all, 'score': score_all, 'categories': [{'name': ['记忆子业务'], 'macro_score': score_all, 'num': total_all, 'score': score_all, 'subsets': _memory_report_subsets}]}]}
                report_dir = os.path.join(output_path, 'reports', model_id)
                os.makedirs(report_dir, exist_ok=True)
                report_json_path = os.path.join(report_dir, f"{dataset_arg['dataset_name']}.json")
                with open_state(report_json_path, 'w', encoding='utf-8') as f:
                    json.dump(report_map, f, ensure_ascii=False, indent=4)
                log(f'  report json 已生成: {report_json_path}')
        log('\n[run_memory_proc] 记忆类测试评测全部完成')
        finalize_task(task_id, model_name, model_id)
    except Exception as e:
        log(f'[run_memory_proc error] {e}')
        traceback.print_exc()
        finalize_task(task_id, model_name, model_id, error=str(e))
    all_end_time = time.time()
    update_task(task_id, runningTime=all_end_time - all_start_time)
    log_file.close()

if __name__ == '__main__':
    cfg = parse_config()
    run_memory_proc(model_config=cfg.get('model_config'), task_id=cfg.get('task_id'), model_id=cfg.get('model_id'), user_req=cfg.get('user_req'), thread_id=cfg.get('thread_id'))
