# Private iCAP Yellow business implementation. Do not publish.
"""
查询扩写评测脚本
使用 LLM-as-judge 评估模型输出是否正确

评测维度：
  - 是否正确判断了需要召回 / 无需召回
  - 召回短语是否精准对应信息缺口
  - 是否误召回（用户已提供全部信息时不应召回）
  - 输出格式是否符合 JSON 数组要求

统计维度：用例来源 × 模型 × 版本
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pandas as pd
import llm_client
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
JUDGE_MODEL = 'qwen3.7-plus'
EVAL_COLUMNS = ['answer_qwen3-8b_原版', 'answer_qwen3-8b_fewshot']
RUN_SOURCES = None

def strip_json_wrapper(text):
    """剥离模型输出的 ```json ... ``` 包裹"""
    if text is None:
        return text
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()
EVAL_SYSTEM_PROMPT = '你是查询扩写（记忆召回）的评测专家。你的任务是检查模型输出是否违反以下**原则性规则**。\n\n## 背景\n查询扩写模块根据用户 query 判断是否需要召回用户专属信息。输出格式为 JSON 字符串数组：\n- `["短语1", ...]`：需要召回\n- `[]`：无需召回\n- `["all"]`：召回全部记忆\n\n## 重要：ground_truth 仅供参考\nground_truth 是一个正确示例，但**不是唯一标准答案**。对于纯陈述类 query（如"我喜欢吃草莓"），召回或不召回都有道理；召回短语措辞不同但方向一致也算对。只要模型不违反以下原则性规则，即判对。\n\n## 原则性错误（任一命中即判错）\n\n1. **不该召回却召回**：query 明显是纯外部信息查询（天气、新闻、股票、通用知识）、实时系统状态（现在几点）、通用寒暄/闲聊（你好、讲个笑话），不需要任何个性化信息，模型却输出召回短语。\n2. **该召回却不召回**：query 明显需要用户个性化信息才能回答（如"帮我推荐电影""我的手机号是什么""我的生日""我明天有什么安排"），模型却输出 []。\n3. **`["all"]` 严重误用**：query 明确请求所有记忆（如"帮我做个自我介绍""你都记住了什么""你了解我吗"）→ 应输出 `["all"]` 却输出其他；或 query 明显只需要特定信息 → 应输出具体短语却输出 `["all"]`。\n4. **召回方向完全错误**：模型输出的召回短语与 query 的信息缺口方向毫无关系。如 query 问"推荐餐厅"却召回"用户的运动偏好"。\n5. **输出格式不合法**：输出不是合法的 JSON 数组。\n\n## 不算错误的情况（判对）\n- 纯陈述类 query（如"我喜欢吃草莓""我每天喝咖啡"）：召回或不召回都可 → 判对\n- 召回短语措辞不同但方向正确（如"用户的电影偏好" vs "用户喜欢看的电影类型"）→ 判对\n- 多召回/少召回了一条（边界模糊的情况）→ 判对\n\n## 输出格式\n{"原因": "如果错误，指出具体违反了哪条原则；如果正确，简要说明", "正确": true/false}'

def call_judge(user_input: str, model_output: str, ground_truth: str) -> dict:
    """调用裁判模型"""
    output_text = strip_json_wrapper(str(model_output)) if model_output else ''
    gt_text = strip_json_wrapper(str(ground_truth)) if ground_truth else ''
    user_msg = '用户query:\n' + str(user_input) + '\n\n'
    user_msg += '模型输出:\n' + output_text + '\n\n'
    user_msg += 'ground_truth（仅供参考，非唯一标准答案）:\n' + gt_text + '\n\n'
    user_msg += '请检查模型输出是否违反原则性规则。'
    result = llm_client.invoke_model(EVAL_SYSTEM_PROMPT, user_msg, JUDGE_MODEL)
    try:
        result = result.strip()
        if result.startswith('```'):
            result = result.split('\n', 1)[1].rsplit('```', 1)[0]
        return json.loads(result)
    except (json.JSONDecodeError, ValueError, AttributeError):
        return {'正确': False, '原因': f'评测解析失败: {str(result)[:200]}'}

def main():
    df = pd.read_excel(input_path, sheet_name='Sheet1')
    if RUN_SOURCES is not None:
        df = df[df['用例来源'].isin(RUN_SOURCES)]
    print(f'评测样本数：{len(df)}')
    print(f"用例来源：{list(df['用例来源'].unique())}")
    print(f'评测列：{EVAL_COLUMNS}')
    print(f'裁判模型：{JUDGE_MODEL}')
    print()
    all_summaries = []
    for ans_col in EVAL_COLUMNS:
        if ans_col not in df.columns:
            print(f'[跳过] 列 {ans_col} 不存在')
            continue
        eval_col = 'eval_' + ans_col
        if eval_col not in df.columns:
            df[eval_col] = None
        print(f"{'=' * 60}")
        print(f'=== {ans_col} ===')
        print(f"{'=' * 60}")
        correct = 0
        total = 0
        skipped = 0
        source_stats = {}
        for idx in df.index:
            raw = df.at[idx, ans_col]
            if pd.isna(raw):
                continue
            ground_truth = df.at[idx, 'ground_truth']
            if pd.isna(ground_truth) or str(ground_truth).strip() == '':
                skipped += 1
                print(f'[{idx}] 跳过：ground_truth 为空')
                continue
            user_query = df.at[idx, 'user_query']
            source = df.at[idx, '用例来源']
            result = call_judge(user_query, raw, str(ground_truth))
            is_correct = result.get('正确', False)
            reason = result.get('原因', '')
            df.at[idx, eval_col] = json.dumps(result, ensure_ascii=False)
            total += 1
            if is_correct:
                correct += 1
            if source not in source_stats:
                source_stats[source] = {'correct': 0, 'total': 0}
            source_stats[source]['total'] += 1
            if is_correct:
                source_stats[source]['correct'] += 1
            status = '✓' if is_correct else '✗'
            print(f'[{idx}] {source} {status} {reason[:80]}')
        if skipped > 0:
            print(f'\n⚠ 跳过 {skipped} 行（ground_truth 为空）')
        acc = correct / total if total > 0 else 0
        print(f'\n准确率：{correct}/{total} = {acc:.1%}')
        print('\n--- 按用例来源 ---')
        for src in sorted(source_stats.keys()):
            s = source_stats[src]
            sa = s['correct'] / s['total'] if s['total'] > 0 else 0
            print(f"  {src}: {s['correct']}/{s['total']} = {sa:.1%}")
        all_summaries.append({'列名': ans_col, '样本数': total, '正确数': correct, '准确率': acc})
        print()
        df.to_excel(output_path, index=False, engine='openpyxl')
    if len(all_summaries) > 1:
        print(f"{'=' * 60}")
        print('======= 多版本对比 =======')
        print(f"{'=' * 60}")
        cmp = pd.DataFrame(all_summaries)
        cmp['准确率'] = cmp['准确率'].apply(lambda x: f'{x:.1%}')
        print(cmp.to_string(index=False))
    print(f'\n评测结果已写回：{output_path}')
