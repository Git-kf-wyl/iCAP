# Private iCAP Yellow business implementation. Do not publish.
"""本地结果上传 —— skill提参 基于已评测结果 Excel 生成 reports json 与 reviews jsonl。

前端上传的"已评测结果 Excel"即在线 run_skilltican_proc 产出的最终结果 excel，
其「明细结果」sheet 含全部按用例原始字段（messages / model_output / 是否通过 /
是否宽松通过 / input_tokens / output_tokens / total_tokens / model_elapsed_time /
query1..5 / assistant1..5 / 当前用户输入 / 记忆信息 / 当前位置 / 当前日期 /
skill选择结果 / 上游查询结果 / case_id / row_index 等）。

本模块复用 run_skilltican_proc 的解析/汇总/报告函数（不动原业务逻辑），只做"壳封装"：
  1. 把「明细结果」sheet 每行构造成与业务原始 jsonl 等价的记录（row 全字段 dict）；
  2. 写入原始记录 jsonl -> 原位调用 _convert_to_review_jsonl 转成 review jsonl；
  3. _build_summary 依据 jsonl 统计严格/宽松通过率 -> 写 reports json。

注意：skill提参的 _convert_to_review_jsonl 期望输入为"原始记录 jsonl"
（含 messages / 是否通过 / 是否宽松通过 / query1..5 等行字段），与本模块构造的记录一致。
"""
import json
import os
import pandas as pd
from services.aisf_skillTiCan.run_skilltican_proc import _convert_to_review_jsonl, _build_summary, _write_report_json

def _sanitize(value):
    """递归清理 NaN/inf/None，保证能安全 json 序列化（与 run_skilltican_proc 口径一致）。"""
    if value is None:
        return ''
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            return ''
        return value
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    return value

def build_skill_result_from_uploaded_excel(tag, model_id, uploaded_excel_path, report_dir, review_dir):
    """官方入口：skill提参 已评测结果 Excel -> reports json + reviews jsonl。

    Returns:
        (report_path, jsonl_path, score)
        其中 score 取 summary 的「宽松通过率」（与 skill 榜单读数口径一致）。
    """
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    DATASET_SHEET = '明细结果'
    df = pd.read_excel(uploaded_excel_path, sheet_name=DATASET_SHEET, dtype=str)
    if len(df) == 0:
        raise ValueError(f'Excel 的「{DATASET_SHEET}」sheet 无数据，无法生成结果文件')
    _BOOL_COLS = ('是否通过', '是否宽松通过')
    dataset_name = tag
    jsonl_path = os.path.join(review_dir, f'{dataset_name}.jsonl')
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for idx, (_, row) in enumerate(df.iterrows()):
            record = {str(col): row[col] for col in df.columns}
            for bcol in _BOOL_COLS:
                raw = record.get(bcol)
                if isinstance(raw, str):
                    record[bcol] = raw.strip().lower() == 'true'
            record['row_index'] = idx
            record['case_id'] = str(row.get('case_id') or f'row_{idx}')
            record = _sanitize(record)
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    _convert_to_review_jsonl(jsonl_path, dataset_name=dataset_name)
    summary = _build_summary(None, jsonl_path)
    total = int(summary.get('总用例数', 0))
    if total == 0:
        raise ValueError('未从上传结果中解析出有效用例，无法生成结果文件')
    score = float(summary.get('宽松通过率', 0) or 0)
    report_path = _write_report_json(report_dir, dataset_name, model_id, summary, None)
    return (report_path, jsonl_path, score)
