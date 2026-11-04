# Private iCAP Yellow business implementation. Do not publish.
"""本地结果上传 —— 基于 tag 与已评测 Excel 生成 reports json 与 reviews jsonl。

前端上传 "已评测带结果列" 的 Excel（即 ELD 伴学产物，见
「伴学0820/2025-Qwen3.8-27B-0612 产品评测集+0612自研模型prompt_统计结果.xlsx」列结构），
本模块按 tag 类型读取其中的结果列，重建出与在线评测产物一致的：
  - reviews/{model_id}/{dataset_name}_default.jsonl
  - reports/{model_id}/{dataset_name}.json

当前仅实现 tag 为「儿童伴读」「记忆」，其余 tag 预留分发结构，暂抛 NotImplementedError。
"""
import json
import os
import pandas as pd
from services import logger
from services.multi_ruler2.children_study.children_study import parse_model_response, calculate_score, gen_review_jsonl, gen_report_json
from services.multi_ruler2.children_study.result_statistics import ATTENTION_SMALL_CATEGORIES, POSTURE_SMALL_CATEGORIES
COL_CASE_ID = '用例编号'
COL_IMG_PATH = '当前帧t路径'
COL_ATT_STATUS = '注意力大类-单次结果'
COL_ATT_CATEGORY = '注意力小类-单次结果'
COL_POSTURE_STATUS = '坐姿大类'
COL_POSTURE_CATEGORY = '坐姿小类'
COL_IMG_SOURCE = '图片来源'
COL_RESOLUTION = '分辨率'
COL_ATT_DIFFICULTY = '难易程度-注意力'
COL_POSTURE_DIFFICULTY = '难易程度-坐姿'
COL_RAW_MULTI = 'model_raw_output_multi'
COL_RAW_SINGLE = 'model_raw_output_single'
COL_TOKENS_MULTI = ('completion_tokens_multi', 'prompt_tokens_multi', 'total_tokens_multi')
COL_TOKENS_SINGLE = ('completion_tokens_single', 'prompt_tokens_single', 'total_tokens_single')
COL_COST_MULTI = 'cost_time_multi'
COL_COST_SINGLE = 'cost_time_single'

def _cell_str(cell, default=''):
    """安全地读取单元格：NaN/None -> default"""
    if cell is None:
        return default
    if isinstance(cell, float) and pd.isna(cell):
        return default
    return str(cell).strip()

def _to_float(cell, default=0.0):
    try:
        if cell is None:
            return default
        if isinstance(cell, float) and pd.isna(cell):
            return default
        return float(cell)
    except (ValueError, TypeError):
        return default

def _merge_parsed(multi_raw, single_raw):
    """合并多帧/单帧的模型原始输出为统一的解析答案。

    ELD 语义（与 run_excel_eval 双图逻辑一致）：
      - attention 类字段优先取多帧(multi) 的结果，缺失则回退到单帧(single)；
      - 坐姿类字段优先取单帧(single) 的结果，缺失则回退到多帧(multi)。
    """
    m = parse_model_response(multi_raw) if multi_raw else {}
    s = parse_model_response(single_raw) if single_raw else {}
    merged = {'attention_status': m.get('attention_status') or s.get('attention_status') or '未知', 'attention_category': m.get('attention_category') or s.get('attention_category') or '未知', 'sitting_posture_status': s.get('sitting_posture_status') or m.get('sitting_posture_status') or '未知', 'sitting_posture_category': s.get('sitting_posture_category') or m.get('sitting_posture_category') or '未知'}
    return merged

def _sum_tokens(row, multi_cols, single_cols):
    """多帧与单帧的 token 统计相加（与 run_excel_eval 双图 token 合并一致）"""
    return {'completion_tokens': _to_float(row.get(multi_cols[0])) + _to_float(row.get(single_cols[0])), 'prompt_tokens': _to_float(row.get(multi_cols[1])) + _to_float(row.get(single_cols[1])), 'total_tokens': _to_float(row.get(multi_cols[2])) + _to_float(row.get(single_cols[2]))}

def _build_eld_result_data(df):
    """基于已评测 Excel 的源列 + 结果列，重建与在线 process_single_image 同构的 result_data。

    每行对应一条用例，跳过 multi/single 原始输出均为空的行。
    """
    result_data = []
    for _, row in df.iterrows():
        multi_raw = _cell_str(row.get(COL_RAW_MULTI))
        single_raw = _cell_str(row.get(COL_RAW_SINGLE))
        if not multi_raw and (not single_raw):
            continue
        golden_answers = {'attention_status': _cell_str(row.get(COL_ATT_STATUS)), 'attention_category': _cell_str(row.get(COL_ATT_CATEGORY)), 'sitting_posture_status': _cell_str(row.get(COL_POSTURE_STATUS)), 'sitting_posture_category': _cell_str(row.get(COL_POSTURE_CATEGORY))}
        parsed_model_answer = _merge_parsed(multi_raw, single_raw)
        item_score = calculate_score(golden_answers, parsed_model_answer)
        img_path_rel = _cell_str(row.get(COL_IMG_PATH))
        img_path_rel = img_path_rel.replace('\\', '/')
        result_data.append({'用例编号': _cell_str(row.get(COL_CASE_ID)), '图片路径': img_path_rel, '系统Prompt': '', '问题': '', '标准答案': golden_answers, '模型原始答案': multi_raw, '模型解析答案': parsed_model_answer, '单项得分': item_score, '是否正确': '是' if item_score == 1.0 else '否', 'token统计': _sum_tokens(row, COL_TOKENS_MULTI, COL_TOKENS_SINGLE), '处理时间': _to_float(row.get(COL_COST_MULTI)) + _to_float(row.get(COL_COST_SINGLE)), 'image_info': {'source': _cell_str(row.get(COL_IMG_SOURCE)), 'resolution': _cell_str(row.get(COL_RESOLUTION))}, 'difficulty_level': {'attention_difficulty': _cell_str(row.get(COL_ATT_DIFFICULTY)), 'sitting_posture_difficulty': _cell_str(row.get(COL_POSTURE_DIFFICULTY))}})
    return result_data
COL_ATT_ACC = 'attention_category_acc'
COL_POSTURE_ACC = 'sitting_posture_category_acc'
_BUSINESS_COLS = {'注意力检测': (COL_ATT_ACC, COL_ATT_CATEGORY, ATTENTION_SMALL_CATEGORIES), '坐姿检测': (COL_POSTURE_ACC, COL_POSTURE_CATEGORY, POSTURE_SMALL_CATEGORIES)}

def _build_eld_accuracy_dict(df):
    """基于上传 Excel 自带 acc 列，按业务维度统计总分与各小类正确率。

    返回与 gen_report_json 期望一致的 accuracy_dict：
        {业务名: {'num': int, 'score': 'xx.x%', 'subsets': [{name, score}, ...]}}
    - score 为整个业务 category_acc 列的正确率字符串 'xx.x%'（gen_report_json 会转小数）；
    - subsets 按标准小类列表统计：某小类的正确率 = gold 列含该小类的行中 acc=1 的比例，
      仅保留数据中实际出现的小类；一行 gold 可为逗号分隔的多标签（任一含该小类即计入）。
    """
    accuracy_dict = {}
    for business, (acc_col, gold_col, cat_list) in _BUSINESS_COLS.items():
        if acc_col not in df.columns:
            accuracy_dict[business] = {'num': 0, 'score': '0.0%', 'subsets': []}
            continue
        acc = pd.to_numeric(df[acc_col], errors='coerce').fillna(0).astype(float)
        total = int(acc.size)
        correct = int(acc.sum())
        score = f'{correct / total * 100:.1f}%' if total else '0.0%'
        subsets = []
        if gold_col in df.columns:
            gold = df[gold_col].astype(str).str.strip()
            for cat in cat_list:
                mask = gold.str.contains(cat, regex=False, na=False)
                n = int(mask.sum())
                if n == 0:
                    continue
                c = int(acc[mask].sum())
                subsets.append({'name': cat, 'score': round(c / n, 4)})
        accuracy_dict[business] = {'num': total, 'score': score, 'subsets': subsets}
    return accuracy_dict

def _build_eld_report(uploaded_excel_path, report_dir, review_dir, model_id, dataset_name):
    """儿童伴读：从已评测 Excel 生成 reviews jsonl 与 reports json。

    返回 (json_path, jsonl_path, accuracy_dict)，其中 accuracy_dict 供写 evaluationResult 使用。
    """
    df = pd.read_excel(uploaded_excel_path)
    result_data = _build_eld_result_data(df)
    if not result_data:
        raise ValueError('Excel 中未找到有效的结果列（model_raw_output_multi/single），无法生成结果文件')
    gen_review_jsonl(result_data, review_dir, dataset_name)
    jsonl_path = os.path.join(review_dir, f'{dataset_name}_default.jsonl')
    accuracy_dict = _build_eld_accuracy_dict(df)
    total_count = len(result_data)
    scores = [item['单项得分'] for item in result_data]
    avg_score = sum(scores) / len(scores) if scores else 0.0
    gen_report_json(model_id, report_dir, avg_score, accuracy_dict, total_count, dataset_name)
    json_path = os.path.join(report_dir, f'{dataset_name}.json')
    return (json_path, jsonl_path, accuracy_dict)

def build_result_from_uploaded_excel(tag, model_id, uploaded_excel_path, report_dir, review_dir):
    """入口：按 tag 分发，将已评测 Excel 转成 reports/reviews 下的 json 与 jsonl。

    Args:
        tag: CUSTOM_RULER2_PROC_DISPATCH 中的键（当前仅「儿童伴读」）
        model_id: 模型名（用于 reports/reviews 下的 model_id 目录名）
        uploaded_excel_path: 前端上传的已评测 Excel 路径
        report_dir: outputs/{model_id}/{task_id}/reports/{model_id}
        review_dir:  outputs/{model_id}/{task_id}/reviews/{model_id}
    Returns:
        (json_path, jsonl_path, accuracy_dict)
        accuracy_dict: {业务名: {num, score:'xx.x%', subsets:[{name,score},...]}}，
                       供写 evaluationResult（按业务拆分）使用。
    """
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    if not hasattr(logger, 'global_logger'):
        logger.global_logger = logger.Logger('eval_log')
    if tag == '儿童伴读':
        return _build_eld_report(uploaded_excel_path, report_dir, review_dir, model_id, tag)
    raise NotImplementedError(f'tag={tag} 的本地结果上传暂未实现')
MEMORY_BUSINESS_MAP = {'画像记忆topic_subtopic提取': '记忆萃取-信息点提取', '画像记忆更新': '记忆萃取-更新', '查询扩写': '记忆召回-查询扩写', '总结过滤': '记忆召回-总结过滤'}
MEMORY_EVAL_TYPES = {'画像记忆topic_subtopic提取': 'llm_judge', '画像记忆更新': 'llm_judge', '查询扩写': 'llm_judge', '总结过滤': 'parse_based'}

def _pick_rightmost_eval_pair(df):
    """选取已评测 Excel 中最右侧（最后）一对 answer_* / eval_answer_* 列。

    上传的汇总 Excel 常含多个模型、多个 prompt 版本的 `answer_<model>_<version>` 与
    `eval_answer_<model>_<version>` 列。按约定取最右侧一对：
      - eval_col:  最右侧的 `eval_answer_*` 列（存裁判结果 JSON {"正确","原因"}）
      - ans_col:   eval_col 去掉 `eval_` 前缀对应的 `answer_*` 列（存模型原始输出）
    返回 (ans_col, eval_col)，均不存在则返回 (None, None)。
    """
    eval_cols = [c for c in df.columns if str(c).startswith('eval_answer_')]
    if not eval_cols:
        return (None, None)
    eval_col = eval_cols[-1]
    ans_col = eval_col[len('eval_'):]
    if ans_col not in df.columns:
        ans_col = None
    return (ans_col, eval_col)

def _build_memory_subtask(model_id, dataset_name, internal_name, display_name, excel_path, review_dir):
    """单个记忆子任务：从已评测 Excel 生成 reviews jsonl。

    复用在线 run_memory_proc 的 jsonl 记录结构（raw_input/choices/index/subset_name），
    直接在数据中命中 `eval_answer_*` 的裁判结果，不重新调用模型与裁判。
    返回 (num, correct, jsonl_path) 或 (0, 0, None)。
    """
    df = pd.read_excel(excel_path)
    ans_col, eval_col = _pick_rightmost_eval_pair(df)
    if eval_col is None:
        return (0, 0, None)
    eval_type = MEMORY_EVAL_TYPES.get(internal_name, 'llm_judge')
    jsonl_path = os.path.join(review_dir, f'{dataset_name}_{internal_name}.jsonl')
    correct = 0
    total = 0
    records = []
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for idx, row in df.iterrows():
            eval_raw = str(row.get(eval_col))
            if not _cell_str(eval_raw):
                continue
            try:
                judge_result = json.loads(eval_raw)
                if not isinstance(judge_result, dict):
                    raise ValueError('非对象')
                is_correct = bool(judge_result.get('正确', False))
                reason = str(judge_result.get('原因', ''))
            except (ValueError, TypeError):
                judge_result = {'正确': False, '原因': f'裁判结果解析失败: {eval_raw[:80]}'}
                is_correct = False
                reason = judge_result['原因']
            user_query = _cell_str(row.get('user_query'))
            ref_answer = _cell_str(row.get('参考答案')) if '参考答案' in df.columns else _cell_str(row.get('ground_truth')) if 'ground_truth' in df.columns else ''
            pred = _cell_str(row.get(ans_col)) if ans_col else ''
            total += 1
            if is_correct:
                correct += 1
            records.append({'raw_input': {'Question': user_query, 'No': idx}, 'choices': [{'review': {'gold': str(ref_answer), 'pred': pred, 'eval_type': eval_type, 'judge_result': judge_result, 'reason': reason, 'result': is_correct}, 'message': {'content': pred}}], 'index': idx, 'subset_name': internal_name})
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False))
            f.write('\n')
    return (total, correct, jsonl_path)

def build_memory_result_from_uploaded_excel(model_id, report_dir, review_dir, dataset_name, uploaded_files):
    """记忆本地结果上传：为每个上传的子任务 Excel 生成 reviews jsonl 与汇总 reports json。

    Args:
        model_id: 模型名（用于 reports/reviews 下的 model_id 目录名）
        report_dir: outputs/{model_id}/{task_id}/reports/{model_id}
        review_dir:  outputs/{model_id}/{task_id}/reviews/{model_id}
        dataset_name: 数据集名（tag=记忆）
        uploaded_files: {显示名: 已评测 Excel 路径}，显示名对应 MEMORY_BUSINESS_MAP 的值
    Returns:
        dict:
            report_json: reports json 路径
            review_jsonls: {显示名: jsonl 路径}
            subsets: [{internal_name, display_name, num, correct_num, score(小数)}]
            score: 整体准确率(小数)
    Raises:
        ValueError: 未识别到任何有效子任务
    """
    os.makedirs(report_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)
    display_to_internal = {v: k for k, v in MEMORY_BUSINESS_MAP.items()}
    subsets = []
    review_jsonls = {}
    for display_name, excel_path in uploaded_files.items():
        if not excel_path or not os.path.exists(excel_path):
            continue
        internal_name = display_to_internal.get(display_name)
        if not internal_name:
            continue
        num, correct, jsonl_path = _build_memory_subtask(model_id, dataset_name, internal_name, display_name, excel_path, review_dir)
        if jsonl_path:
            review_jsonls[display_name] = jsonl_path
        if num > 0:
            subsets.append({'internal_name': internal_name, 'display_name': display_name, 'num': num, 'correct_num': correct, 'score': correct / num})
    if not subsets:
        raise ValueError('未从上传结果中解析出有效的记忆子任务结果')
    total_all = sum((s['num'] for s in subsets))
    correct_all = sum((s['correct_num'] for s in subsets))
    score_all = correct_all / total_all if total_all > 0 else 0
    report_map = {'name': f'{model_id}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_id, 'score': score_all, 'metrics': [{'name': '记忆测评', 'macro_score': score_all, 'num': total_all, 'score': score_all, 'categories': [{'name': ['记忆子业务'], 'macro_score': score_all, 'num': total_all, 'score': score_all, 'subsets': [{'name': s['internal_name'], 'num': s['num'], 'score': s['score'], 'correct_num': s['correct_num']} for s in subsets]}]}]}
    report_json = os.path.join(report_dir, f'{dataset_name}.json')
    with open(report_json, 'w', encoding='utf-8') as f:
        json.dump(report_map, f, ensure_ascii=False, indent=4)
    return {'report_json': report_json, 'review_jsonls': review_jsonls, 'subsets': subsets, 'score': score_all}
