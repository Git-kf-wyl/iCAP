# Private iCAP Yellow business implementation. Do not publish.
"""本地结果上传 —— 伴学提参 基于各子任务的已评测结果 Excel 生成报告 jsonl 与 reports json。

与「记忆」业务一致：伴学提参有 提醒 / 总结 / 提参 三个子任务，
前端分别上传每个子任务的"已评测结果 Excel"（字段 file_提醒 / file_总结 / file_提参）。

复用 run_banxue_proc 的解析/汇总/报告函数（不动原业务逻辑），只做"壳封装"：
  - _convert_to_review_jsonl   : 子任务结果 Excel -> 逐条 review jsonl
  - _build_subset_summary      : 子任务结果 Excel -> (total, pass_num)
  - _write_report_json         : 汇总各子任务 subsets -> reports json

前端上传的每个子任务"已评测结果 Excel"即在线 run_banxue_proc 产出的该子任务最终结果 excel
（含 input / ground_truth / model_output / result|judge_result / reason / status 等列）。
"""
import os
import pandas as pd
from services.aisf_banxue.run_banxue_proc import _convert_to_review_jsonl, _build_subset_summary, _write_report_json
BANXUE_SUBTASKS = ('提醒', '总结', '提参')

def build_banxue_result_from_uploaded_excel(tag, model_id, report_dir, review_dir, uploaded_files):
    """官方入口：伴学提参 多个子任务已评测 Excel -> reports json + 多个 reviews jsonl。

    Args:
        tag: 数据集名（= tag）
        model_id: 模型名（reports/reviews 下的 model_id 目录名）
        report_dir: outputs/{model_id}/{task_id}/reports/{model_id}
        review_dir:  outputs/{model_id}/{task_id}/reviews/{model_id}
        uploaded_files: {子任务名('提醒'/'总结'/'提参'): 已评测 Excel 路径}
    Returns:
        dict:
            report_json: reports json 路径
            review_jsonls: {子任务名: jsonl 路径}
            score: 各子任务加权准确率(小数)
            subsets: [{name, num, score, correct_num}]
    Raises:
        ValueError: 未识别到任何有效子任务结果
    """
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    subsets = []
    review_jsonls = {}
    for subtask in BANXUE_SUBTASKS:
        excel_path = uploaded_files.get(subtask)
        if not excel_path or not os.path.exists(excel_path):
            continue
        try:
            df = pd.read_excel(excel_path, dtype=str)
            if 'result' not in df.columns and 'judge_result' not in df.columns:
                raise ValueError(f'子任务「{subtask}」Excel 未找到结果列（result/judge_result），已跳过')
        except ValueError:
            continue
        jsonl_path = os.path.join(review_dir, f'{tag}_{subtask}.jsonl')
        _convert_to_review_jsonl(excel_path, jsonl_path, dataset_name=tag, subtask_name=subtask)
        review_jsonls[subtask] = jsonl_path
        total, pass_num = _build_subset_summary(excel_path)
        subsets.append({'name': subtask, 'num': total, 'score': pass_num / total if total else 0.0, 'correct_num': pass_num})
    if not subsets:
        raise ValueError('未从上传结果中解析出任何有效子任务（提醒/总结/提参），无法生成结果文件')
    total_all = sum((s['num'] for s in subsets))
    correct_all = sum((s['correct_num'] for s in subsets))
    score_all = correct_all / total_all if total_all else 0.0
    report_path = _write_report_json(report_dir, tag, model_id, subsets)
    return {'report_json': report_path, 'review_jsonls': review_jsonls, 'subsets': subsets, 'score': score_all}
