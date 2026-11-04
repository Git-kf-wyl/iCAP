# Private iCAP Yellow business implementation. Do not publish.
"""本地结果上传 —— 意图 基于已评测结果 Excel 生成 reports json 与 reviews jsonl。

前端上传的"已评测结果 Excel"即在线 run_yitu_proc 产出的最终结果 excel
（含 cur_query / expected_output_A,B / tunnel_A|B_result / tunnel_A|B_clean_result /
tunnel_A|B_is_right / tunnel_A|B_prompt|completion|total_tokens /
tunnel_A|B_cost_time / intent_count 等列）。

本模块复用 aisf_yitu_test 的 gen_review_jsonl / gen_report_json（不动原业务逻辑），
只做"壳封装"：逐行把结果 excel 重建为与 run_pipeline 一致的 combined_data，
再据此生成逐条 review jsonl 与报告 json。

意图判定列已在 excel 内（tunnel_A_is_right / tunnel_B_is_right / intent_count），
无需重新调用模型或裁判。
"""
import os
import pandas as pd
from services import logger
from services.multi_ruler2.aisf_yitu.aisf_yitu_test import gen_review_jsonl, gen_report_json

def build_yitu_result_from_uploaded_excel(tag, model_id, uploaded_excel_path, report_dir, review_dir):
    """官方入口：意图 已评测结果 Excel -> reports json + reviews jsonl。

    Args:
        tag: 数据集名（= tag）
        model_id: 模型名（reports/reviews 下的 model_id 目录名）
        uploaded_excel_path: 前端上传的已评测结果 Excel（本地已判定）
        report_dir: outputs/{model_id}/{task_id}/reports/{model_id}
        review_dir:  outputs/{model_id}/{task_id}/reviews/{model_id}
    Returns:
        (report_path, jsonl_path, score, subsets)
        score 为双通道均正确率(小数)；subsets 为单/两/三意图三档。
    """
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    if not hasattr(logger, 'global_logger'):
        logger.global_logger = logger.Logger('eval_log')
    df = pd.read_excel(uploaded_excel_path, dtype=str)
    if len(df) == 0:
        raise ValueError('Excel 无数据，无法生成结果文件')
    if 'tunnel_A_is_right' not in df.columns or 'tunnel_B_is_right' not in df.columns:
        raise ValueError('Excel 中未找到有效的判定列（tunnel_A_is_right / tunnel_B_is_right），无法生成结果文件')
    if 'intent_count' in df.columns:
        df['intent_count'] = pd.to_numeric(df['intent_count'], errors='coerce').fillna(0).astype(int)
    dataset_name = tag

    def _to_int(v):
        try:
            return int(float(v or 0))
        except (ValueError, TypeError):
            return 0

    def _to_float(v):
        try:
            return float(v or 0)
        except (ValueError, TypeError):
            return 0.0
    combined_data = []
    suc_A = suc_B = suc_both = 0
    total = len(df)
    for _, row in df.iterrows():
        is_right_A = _to_int(row.get('tunnel_A_is_right'))
        is_right_B = _to_int(row.get('tunnel_B_is_right'))
        is_right_A_str = '1' if is_right_A == 1 else '0'
        is_right_B_str = '1' if is_right_B == 1 else '0'
        token_total = {'prompt_tokens': _to_int(row.get('tunnel_A_prompt_tokens')) + _to_int(row.get('tunnel_B_prompt_tokens')), 'completion_tokens': _to_int(row.get('tunnel_A_completion_tokens')) + _to_int(row.get('tunnel_B_completion_tokens')), 'total_tokens': _to_int(row.get('tunnel_A_total_tokens')) + _to_int(row.get('tunnel_B_total_tokens'))}
        cost_time_total = _to_float(row.get('tunnel_A_cost_time')) + _to_float(row.get('tunnel_B_cost_time'))
        combined_data.append({'query': str(row.get('cur_query') or ''), 'expected_A': str(row.get('expected_output_A') or ''), 'expected_B': str(row.get('expected_output_B') or ''), 'model_answer_raw_A': str(row.get('tunnel_A_result') or ''), 'model_answer_raw_B': str(row.get('tunnel_B_result') or ''), 'clean_result_A': str(row.get('tunnel_A_clean_result') or ''), 'clean_result_B': str(row.get('tunnel_B_clean_result') or ''), 'is_right_A': is_right_A_str, 'is_right_B': is_right_B_str, 'token统计': token_total, '处理时间': cost_time_total})
        if is_right_A == 1:
            suc_A += 1
        if is_right_B == 1:
            suc_B += 1
        if is_right_A == 1 and is_right_B == 1:
            suc_both += 1
    acc_A = suc_A / total if total else 0.0
    acc_B = suc_B / total if total else 0.0
    acc_both = suc_both / total if total else 0.0
    gen_review_jsonl(combined_data, review_dir, dataset_name=dataset_name, subset_name='default', logger=logger.global_logger if hasattr(logger, 'global_logger') else None)
    jsonl_path = os.path.join(review_dir, f'{dataset_name}_default.jsonl')
    gen_report_json(model_id, dataset_name, report_dir, acc_A, acc_B, acc_both, total, df=df, logger=logger.global_logger if hasattr(logger, 'global_logger') else None)
    report_path = os.path.join(report_dir, f'{dataset_name}.json')
    subsets = _extract_subsets(df)
    return (report_path, jsonl_path, acc_both, subsets)

def _extract_subsets(df):
    """按 intent_count 分组统计双通道均正确的 subsets（与 gen_report_json 口径一致）。"""
    subsets = []
    if 'intent_count' not in df.columns:
        return subsets
    intent_labels = {1: '单意图', 2: '两意图', 3: '三意图'}
    for intent_val in [1, 2, 3]:
        subset_df = df[df['intent_count'] == intent_val]
        subset_total = len(subset_df)
        if subset_total > 0:
            subset_suc_both = sum((1 for _, r in subset_df.iterrows() if str(r.get('tunnel_A_is_right', '0')) == '1' and str(r.get('tunnel_B_is_right', '0')) == '1'))
            subset_score = subset_suc_both / subset_total
        else:
            subset_suc_both = 0
            subset_score = 0
        subsets.append({'name': intent_labels.get(intent_val, str(intent_val)), 'num': subset_total, 'score': subset_score, 'correct_num': subset_suc_both})
    return subsets
