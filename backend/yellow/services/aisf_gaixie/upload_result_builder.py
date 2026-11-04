# Private iCAP Yellow business implementation. Do not publish.
"""本地结果上传 —— 改写 基于「对比结果 Excel」生成 reports json 与 reviews jsonl。

改写有两个子业务：外挂fewshot库 / 不外挂fewshot库（各自独立任务的产物）。
前端上传的"已评测文件"为在线 run_gaixie_proc 产出的「对比结果_{dataset}.xlsx」
（含对比详情 sheet，其中 最终结果 列已本地判定为 正确/错误），
与在线生成 review jsonl / 报告判分的口径一致（compare 产物的最终结果）。

注意：本模块不做"改写字业务名是否含外挂"的猜测，子业务名由上传字段 key 提供
（前端 _file_外挂fewshot库 / _file_不外挂fewshot库），后端据此命名 jsonl 与 evaluationResult。
"""
import json
import os
import pandas as pd
DETAIL_SHEET = '对比详情'
COL_QUERY = '当前用户输入'
COL_PRED = '测试结果(原始)'
COL_GOLD = '标准答案(原始)'
COL_FINAL = '最终结果'
GAIXIE_SUBTASKS = ('外挂fewshot库', '不外挂fewshot库')

def _cell_str(value):
    if value is None:
        return ''
    if isinstance(value, float) and pd.isna(value):
        return ''
    return str(value).strip()

def _to_int(value):
    try:
        return max(0, int(float(value)))
    except (ValueError, TypeError):
        return 0

def build_gaixie_result_from_uploaded_excel(tag, model_id, report_dir, review_dir, uploaded_files):
    """官方入口：改写 两个子业务对比结果 Excel -> reports json + 多个 reviews jsonl。

    Args:
        tag: 数据集名（= tag）
        model_id: 模型名（reports/reviews 下的 model_id 目录名）
        report_dir: outputs/{model_id}/{task_id}/reports/{model_id}
        review_dir:  outputs/{model_id}/{task_id}/reviews/{model_id}
        uploaded_files: {子业务名('外挂fewshot库'/'不外挂fewshot库'): 对比结果 Excel 路径}
    Returns:
        dict:
            report_json: reports json 路径
            review_jsonls: {子业务名: jsonl 路径}
            subsets: [{name, num, score, correct_num}]
            score: 全部子业务加权正确率(小数)
    Raises:
        ValueError: 未识别到任何有效子业务结果
    """
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    subsets = []
    review_jsonls = {}
    for subtask in GAIXIE_SUBTASKS:
        excel_path = uploaded_files.get(subtask)
        if not excel_path or not os.path.exists(excel_path):
            continue
        try:
            df = pd.read_excel(excel_path, sheet_name=DETAIL_SHEET, dtype=str)
        except Exception:
            raise ValueError(f'子业务「{subtask}」文件缺少「{DETAIL_SHEET}」sheet，无法解析')
        if COL_FINAL not in df.columns:
            raise ValueError(f'子业务「{subtask}」文件未找到判定列「{COL_FINAL}」，无法解析')
        total = len(df)
        correct = int((df[COL_FINAL] == '正确').sum())
        jsonl_path = os.path.join(review_dir, f'{tag}_{subtask}.jsonl')
        review_lines = []
        for idx, (_, row) in enumerate(df.iterrows()):
            query = _cell_str(row.get(COL_QUERY))
            gold = _cell_str(row.get(COL_GOLD))
            pred = _cell_str(row.get(COL_PRED))
            is_correct = _cell_str(row.get(COL_FINAL)) == '正确'
            review_lines.append({'raw_input': {'Question': query, 'expected': gold, 'prompt': '', 'context': '', 'No': idx}, 'choices': [{'review': {'gold': gold, 'pred': pred, 'result': '1' if is_correct else '0', '判定结果': '通过' if is_correct else '不通过'}, 'message': {'content': pred}}], 'index': idx, 'dialogue_round': str(idx), 'subset_name': subtask, 'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}, 'response_time': 0})
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for line in review_lines:
                f.write(json.dumps(line, ensure_ascii=False) + '\n')
        review_jsonls[subtask] = jsonl_path
        subsets.append({'name': subtask, 'num': total, 'score': correct / total if total else 0.0, 'correct_num': correct})
    if not subsets:
        raise ValueError('未从上传结果中解析出任何有效子业务（外挂fewshot库/不外挂fewshot库），无法生成结果文件')
    total_all = sum((s['num'] for s in subsets))
    correct_all = sum((s['correct_num'] for s in subsets))
    score_all = correct_all / total_all if total_all else 0.0
    report_map = {'name': f'{model_id}_{tag}', 'dataset_name': tag, 'model_name': model_id, 'score': round(score_all, 4), 'metrics': [{'categories': [{'macro_score': round(score_all, 4), 'name': ['改写'], 'num': total_all, 'score': round(score_all, 4), 'subsets': [{'name': s['name'], 'num': int(s['num']), 'score': round(s['score'], 4), 'correct_num': int(s['correct_num'])} for s in subsets]}], 'macro_score': round(score_all, 4), 'name': '改写', 'num': total_all, 'score': round(score_all, 4)}], 'summary': {'总用例数': int(total_all), '严格通过数': int(correct_all), '严格通过率': round(score_all, 4), '子任务': subsets}}
    report_path = os.path.join(report_dir, f'{tag}.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_map, f, ensure_ascii=False, indent=4)
    return {'report_json': report_path, 'review_jsonls': review_jsonls, 'subsets': subsets, 'score': score_all}
