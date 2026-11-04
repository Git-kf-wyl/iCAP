# Private iCAP Yellow business implementation. Do not publish.
"""本地结果上传 —— Coordinator 基于已评测结果 Excel 生成 reports json 与 reviews jsonl。

复用 run_coordinator_proc 的解析/汇总/报告函数（不动原业务逻辑），只做"壳封装"：
  - _convert_to_review_jsonl : 结果 Excel -> 逐条 review jsonl
  - _build_summary           : 结果 Excel -> (total, pass_num)
  - _write_report_json       : 写 reports json（可带 result_df 生成单/两/三意图 subsets）

前端上传的"已评测结果 Excel"即在线 run_coordinator_proc 产出的最终结果 excel
（含 user_input / ground_truth / model_output / result / reason / status /
 memory_location_time / assistant_skill_select / tool1..5 / query1..answer5 等列）。
"""
import os
import pandas as pd
from services.aisf_coordinator.run_coordinator_proc import _convert_to_review_jsonl, _build_summary, _write_report_json

def build_coordinator_result_from_uploaded_excel(tag, model_id, uploaded_excel_path, report_dir, review_dir):
    """官方入口：Coordinator 已评测 Excel -> reports json + reviews jsonl。

    Returns:
        (report_path, jsonl_path, score)
    """
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    df = pd.read_excel(uploaded_excel_path, dtype=str)
    if 'result' not in df.columns and 'judge_result' not in df.columns:
        raise ValueError('Excel 中未找到有效的结果列（result/judge_result），无法生成结果文件')
    dataset_name = tag
    jsonl_path = os.path.join(review_dir, f'{dataset_name}.jsonl')
    _convert_to_review_jsonl(uploaded_excel_path, jsonl_path, dataset_name=dataset_name)
    total, pass_num = _build_summary(uploaded_excel_path)
    score = pass_num / total if total else 0.0
    report_path = _write_report_json(report_dir, dataset_name, model_id, total, pass_num, result_df=df)
    return (report_path, jsonl_path, score)
