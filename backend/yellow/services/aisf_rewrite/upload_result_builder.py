# Private iCAP Yellow business implementation. Do not publish.
"""本地结果上传 —— 改写 基于「结果 Excel」生成 reports json 与 reviews jsonl。

新版改写（aisf_rewrite 工程）在线 run_rewrite_proc 产出的结果是单数据集的结果
Excel，含「测试明细」「总体统计」「维度统计」三个 sheet；其中「测试明细」sheet
已包含宽松/严格双重规则判定结果（宽松判定结果 / 严格判定结果）与「维度」列，
无需重新调用模型或裁判。

本模块复用 run_rewrite_proc 的解析/汇总/报告函数（不动原业务逻辑），只做"壳封装"：
  - _convert_to_review_jsonl : 结果 Excel -> 逐条 review jsonl
  - _build_subsets           : 结果 Excel -> 按维度统计的 subsets（含严格/宽松两套）
  - _write_report_json       : 写 reports json（score=严格通过率，loose_score=宽松通过率）
"""
import os
import pandas as pd
from services.aisf_rewrite.run_rewrite_proc import _convert_to_review_jsonl, _build_subsets, _write_report_json

def build_rewrite_result_from_uploaded_excel(tag, model_id, uploaded_excel_path, report_dir, review_dir):
    """官方入口：改写 已评测结果 Excel -> reports json + reviews jsonl。

    Args:
        tag: 数据集名（= tag）
        model_id: 模型名（reports/reviews 下的 model_id 目录名）
        uploaded_excel_path: 前端上传的已评测结果 Excel（含「测试明细」sheet）
        report_dir: outputs/{model_id}/{task_id}/reports/{model_id}
        review_dir:  outputs/{model_id}/{task_id}/reviews/{model_id}
    Returns:
        dict:
            report_json: reports json 路径
            review_jsonls: {数据集名: jsonl 路径}
            subsets: 按维度统计的 subsets（含严格/宽松两套通过数/通过率）
            score: 严格通过率(小数)
            loose_score: 宽松通过率(小数)
    Raises:
        ValueError: 未识别到「测试明细」sheet 或缺少判定列
    """
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    try:
        df = pd.read_excel(uploaded_excel_path, sheet_name='测试明细', dtype=str)
    except ValueError as e:
        raise ValueError('上传的结果 Excel 缺少「测试明细」sheet，无法解析') from e
    if len(df) == 0:
        raise ValueError('上传的结果 Excel 无数据，无法生成结果文件')
    if '严格判定结果' not in df.columns or '宽松判定结果' not in df.columns:
        raise ValueError('上传的结果 Excel 未找到判定列（严格判定结果 / 宽松判定结果），无法解析')
    if '维度' not in df.columns:
        raise ValueError('上传的结果 Excel 未找到「维度」列，无法解析')
    dataset_name = tag
    jsonl_path = os.path.join(review_dir, f'{dataset_name}.jsonl')
    _convert_to_review_jsonl(uploaded_excel_path, jsonl_path, dataset_name=dataset_name)
    report_path = _write_report_json(report_dir, dataset_name, model_id, df)
    subsets = _build_subsets(df)
    total = len(df)
    strict_pass = int((df.get('严格判定结果', pd.Series([])) == '正确').sum())
    loose_pass = int((df.get('宽松判定结果', pd.Series([])) == '正确').sum())
    score = round(strict_pass / total, 4) if total else 0.0
    loose_score = round(loose_pass / total, 4) if total else 0.0
    return {'report_json': report_path, 'review_jsonls': {dataset_name: jsonl_path}, 'subsets': subsets, 'score': score, 'loose_score': loose_score}
