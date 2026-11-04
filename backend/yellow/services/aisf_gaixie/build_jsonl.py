# Private iCAP Yellow business implementation. Do not publish.
import json
import re
from pathlib import Path
import pandas as pd
INPUT_EXCEL = 'few-shot.xlsx'
SHEET_NAME = '708fewshots'
OUTPUT_JSONL = 'few_shot_examples_0708_with_prev_content.jsonl'
MAX_TURNS = 6

def clean_text(value) -> str:
    """清洗 Excel 单元格文本。"""
    if pd.isna(value):
        return ''
    return str(value).strip()

def split_labels(label_text: str):
    """
    标签支持：
    指代消解|属性追问
    指代消解｜属性追问
    """
    label_text = clean_text(label_text)
    if not label_text:
        return []
    label_text = label_text.replace('｜', '|')
    return [x.strip() for x in label_text.split('|') if x.strip()]

def parse_answer(answer_raw: str):
    """
    校验 answer 是否是合法 JSON。

    示例：
    {"思考":"补全:Redis","意图":"Redis支持哪些数据结构？"}
    """
    answer_raw = clean_text(answer_raw)
    if not answer_raw:
        raise ValueError('answer 为空')
    try:
        answer = json.loads(answer_raw)
    except json.JSONDecodeError as e:
        raise ValueError(f'answer 不是合法 JSON：{answer_raw}') from e
    if not isinstance(answer, dict):
        raise ValueError(f'answer 必须是 JSON 对象：{answer_raw}')
    if '思考' not in answer or '意图' not in answer:
        raise ValueError(f'answer 缺少字段「思考」或「意图」：{answer_raw}')
    return answer

def build_answer_no_thought(answer: dict):
    """
    从完整 answer 中生成无思考版本。
    """
    return {'意图': answer.get('意图', '')}

def find_turn_indexes(columns, max_turns=6):
    """自动寻找 queryN 列。"""
    indexes = set()
    for col in columns:
        col = str(col).strip()
        match = re.fullmatch('query(\\d+)', col)
        if match:
            idx = int(match.group(1))
            if 1 <= idx <= max_turns:
                indexes.add(idx)
    return sorted(indexes)

def get_cell(row, col_name: str) -> str:
    """安全读取某列。"""
    if col_name not in row:
        return ''
    return clean_text(row[col_name])

def get_thought_explanation_cell(row) -> str:
    """
    带思考版 prompt_example 使用：
    只读取 Excel 的「说明」列
    """
    return get_cell(row, '说明')

def get_no_think_explanation_cell(row) -> str:
    """
    无思考版 no_thought_example 使用：
    只读取 Excel 的「explanation」列
    """
    return get_cell(row, 'explanation')

def get_row_id(row, fallback_id: str) -> str:
    """
    优先读取 Excel 里的 id / ID。
    如果没有，就自动生成 FS000001 这种编号。
    """
    excel_id = get_cell(row, 'id') or get_cell(row, 'ID') or get_cell(row, '编号')
    return excel_id if excel_id else fallback_id

def build_history_and_current(row, turn_indexes):
    """
    规则：
    1. 最后一个非空 queryN 是当前用户输入
    2. 它之前的 query/assistant 是上下文
    3. 当前 query 对应的 assistant 不进入上下文
    """
    non_empty_query_indexes = []
    for i in turn_indexes:
        query = get_cell(row, f'query{i}')
        if query:
            non_empty_query_indexes.append(i)
    if not non_empty_query_indexes:
        raise ValueError('没有找到非空 query')
    current_idx = non_empty_query_indexes[-1]
    current_query = get_cell(row, f'query{current_idx}')
    history = []
    warnings = []
    for i in turn_indexes:
        query = get_cell(row, f'query{i}')
        assistant = get_cell(row, f'assistant{i}')
        if i < current_idx:
            if query:
                history.append({'role': 'user', 'content': query})
            if assistant:
                history.append({'role': 'assistant', 'content': assistant})
        elif i == current_idx:
            if assistant:
                warnings.append(f'当前输入 query{current_idx} 对应 assistant{current_idx} 非空，已忽略：{assistant}')
    return (history, current_query, current_idx, warnings)

def get_previous_user_query(history):
    """
    从 history 中取最后一条 user 消息，作为上一轮用户输入。

    如果没有上一轮用户输入，返回空字符串。
    """
    for msg in reversed(history):
        if msg.get('role') == 'user':
            return clean_text(msg.get('content', ''))
    return ''

def build_prev_current_query(history, current_query):
    """
    构造用于“上一轮用户输入 + 当前用户输入”的 embedding 检索文本。

    有上一轮用户输入时：
    上一轮用户输入：xxx
    当前用户输入：yyy

    没有上一轮用户输入时：
    直接返回当前用户输入
    """
    prev_query = get_previous_user_query(history)
    current_query = clean_text(current_query)
    if prev_query:
        return f'上一轮用户输入：{prev_query}\n当前用户输入：{current_query}'
    return current_query

def append_history_lines(lines, history):
    """
    按统一格式追加上下文。
    """
    if history:
        if len(history) == 1 and history[0]['role'] == 'user':
            lines.append(f"上下文：{history[0]['content']}")
        else:
            lines.append('上下文：')
            for msg in history:
                if msg['role'] == 'user':
                    lines.append(f"用户：{msg['content']}")
                elif msg['role'] == 'assistant':
                    lines.append(f"助手：{msg['content']}")
    else:
        lines.append('上下文：无')

def build_prompt_example(history, current_query, answer, explanation=''):
    """
    生成带思考版本 few-shot 示例。

    使用 Excel 的「说明」列。

    格式：
    上下文：xxx
    当前用户输入：xxx
    输出：{"思考":"...","意图":"..."}
    说明：xxx
    """
    answer_text = json.dumps(answer, ensure_ascii=False, separators=(',', ':'))
    explanation = clean_text(explanation)
    lines = []
    append_history_lines(lines, history)
    lines.append(f'当前用户输入：{current_query}')
    lines.append(f'输出：{answer_text}')
    if explanation:
        lines.append(f'说明：{explanation}')
    return '\n'.join(lines)

def build_no_think_example(history, current_query, answer_no_thought, explanation=''):
    """
    生成无思考版本 few-shot 示例。

    使用 Excel 的「explanation」列。

    格式：
    上下文：xxx
    当前用户输入：xxx
    输出：{"意图":"..."}
    说明：xxx
    """
    answer_text = json.dumps(answer_no_thought, ensure_ascii=False, separators=(',', ':'))
    explanation = clean_text(explanation)
    lines = []
    append_history_lines(lines, history)
    lines.append(f'当前用户输入：{current_query}')
    lines.append(f'输出：{answer_text}')
    if explanation:
        lines.append(f'说明：{explanation}')
    return '\n'.join(lines)

def read_excel_safely(input_excel, sheet_name):
    """读取 Excel，如果指定 sheet 不存在，则读取第一个 sheet。"""
    input_path = Path(input_excel)
    if not input_path.exists():
        raise FileNotFoundError(f'找不到 Excel 文件：{input_path.resolve()}')
    excel_file = pd.ExcelFile(input_path)
    sheet_names = excel_file.sheet_names
    if sheet_name in sheet_names:
        real_sheet = sheet_name
    else:
        real_sheet = sheet_names[0]
        print(f'⚠️ 找不到 sheet：{sheet_name}')
        print(f'⚠️ 自动读取第一个 sheet：{real_sheet}')
    df = pd.read_excel(input_path, sheet_name=real_sheet)
    df.columns = [str(c).strip() for c in df.columns]
    return (df, real_sheet)

def write_jsonl(items, output_path):
    """
    JSONL 格式：
    每一行都是一个完整 JSON 对象。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False, separators=(',', ':')))
            f.write('\n')

def convert_excel_to_jsonl():
    df, real_sheet = read_excel_safely(INPUT_EXCEL, SHEET_NAME)
    print(f'📘 读取文件：{INPUT_EXCEL}')
    print(f'📄 读取 sheet：{real_sheet}')
    turn_indexes = find_turn_indexes(df.columns, max_turns=MAX_TURNS)
    if not turn_indexes:
        raise ValueError('没有找到 queryN 列，例如 query1、query2、query3')
    if 'answer' not in df.columns:
        raise ValueError('缺少 answer 列')
    print(f'🔍 检测到轮次列：{turn_indexes}')
    results = []
    error_rows = []
    for row_idx, row in df.iterrows():
        excel_row_no = row_idx + 2
        try:
            rule_type = get_cell(row, '规则类型') or get_cell(row, 'rule_type')
            label_text = get_cell(row, '标签') or get_cell(row, 'labels')
            labels = split_labels(label_text)
            thought_explanation = get_thought_explanation_cell(row)
            no_think_explanation = get_no_think_explanation_cell(row)
            answer_raw = get_cell(row, 'answer')
            answer = parse_answer(answer_raw)
            answer_no_thought = build_answer_no_thought(answer)
            history, current_query, current_idx, warnings = build_history_and_current(row=row, turn_indexes=turn_indexes)
            prev_current_query = build_prev_current_query(history=history, current_query=current_query)
            fallback_id = f'FS{len(results) + 1:06d}'
            item_id = get_row_id(row, fallback_id)
            prompt_example = build_prompt_example(history=history, current_query=current_query, answer=answer, explanation=thought_explanation)
            no_think = build_no_think_example(history=history, current_query=current_query, answer_no_thought=answer_no_thought, explanation=no_think_explanation)
            item = {'id': item_id, 'rule_type': rule_type, 'labels': labels, 'history': history, 'current_query': current_query, 'embedding_text_cur': current_query, 'embedding_text_prev_cur': prev_current_query, 'prev_current_query': prev_current_query, 'answer': answer, 'answer_no_thought': answer_no_thought, 'prompt_example': prompt_example, 'no_thought_example': no_think, 'enabled': True}
            if thought_explanation:
                item['thought_explanation'] = thought_explanation
            if no_think_explanation:
                item['no_think_explanation'] = no_think_explanation
            if warnings:
                item['warnings'] = warnings
            results.append(item)
        except Exception as e:
            error_rows.append({'excel_row': excel_row_no, 'error': str(e)})
    output_path = Path(OUTPUT_JSONL)
    write_jsonl(results, output_path)
    print(f'\n✅ JSONL 已生成：{output_path.resolve()}')
    print(f'✅ 成功样本数：{len(results)}')
    if error_rows:
        error_path = output_path.with_suffix('.errors.json')
        with error_path.open('w', encoding='utf-8') as f:
            json.dump(error_rows, f, ensure_ascii=False, indent=2)
        print(f'⚠️ 失败行数：{len(error_rows)}')
        print(f'⚠️ 错误详情：{error_path.resolve()}')
    if results:
        print('\n====== 样本预览 ======')
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
    return results

def main():
    convert_excel_to_jsonl()
