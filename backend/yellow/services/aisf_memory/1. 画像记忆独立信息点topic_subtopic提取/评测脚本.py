# Private iCAP Yellow business implementation. Do not publish.
"""
画像记忆提取评测脚本
使用 LLM-as-judge 评估模型输出是否正确

评测维度：
  - 是否误提问句/指令
  - 是否误提一次性事件/临时行为
  - topic 是否合理、detail 是否准确
  - 是否违反禁止规则（关系人信息归为用户本人等）
  - 输出格式是否符合要求

统计维度：用例来源 × 模型 × 版本
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pandas as pd
import llm_client
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
JUDGE_MODEL = 'qwen3.7-plus'
EVAL_COLUMNS = ['answer_qwen3-32b_v1.0', 'answer_qwen3-32b_v2.0', 'answer_qwen3-32b_v3.0', 'answer_qwen3-32b_v4.0']
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
EVAL_SYSTEM_PROMPT = '你是画像记忆提取的评测专家。你的任务是检查模型输出是否违反以下**原则性规则**。\n\n## 重要：ground_truth 仅供参考\nground_truth 是一个正确示例，但**不是唯一标准答案**。只要模型输出不违反原则性规则，即使与 ground_truth 不完全一致（条目数不同、topic措辞不同等），也应判对。\n\n## 原则性错误（任一命中即判错）\n\n1. **问句反推**：将用户的查询问句当作事实提取。如用户问"我喜欢什么运动？"→ 输出包含"用户喜欢XX运动"即判错。输出中出现"用户不知道/不确定/询问/需要确认"等也判错。\n2. **凭空捏造**：detail 中包含用户输入中未出现的信息。\n3. **关系人错归**：detail 中描述关系人属性的信息，其主语被错误写成"用户"。**判断标准是 detail 的主语归属**：如果 topic 和 detail 的主语指向同一主体（如 topic="母亲"、detail 主语是"用户母亲"）则不是错归。只有当 topic 指向关系人，但 detail 主语却写成"用户"时（如 topic="母亲"但 detail="用户的手机号是..."），才是错归。\n4. **提取任务指令**：提取了任务请求、工具调用、推荐请求、定时提醒等即时需求。\n5. **提取一次性事件**：提取了普通日常事件而非长期画像。如"昨天买了衣服""今天跑了5公里"。但人生里程碑（毕业、入职、结婚等）可以提取。\n6. **输出格式不合法**：输出不是合法的 JSON 数组，或元素缺少 topic/detail 字段。\n\n## 不算错误的情况（判对）\n- 模型多提取/少提取了一条，但提取的内容本身不违反上述原则 → 判对\n- topic 措辞不完全相同但语义合理（如"饮食偏好" vs "食物偏好"）→ 判对\n- detail 措辞不同但核心事实一致 → 判对\n- ground_truth 是 [] 但模型输出了一些看起来合理的条目，只要不违反原则 → 判对（反之亦然）\n\n## 输出格式\n{"原因": "如果错误，指出具体违反了哪条原则及哪条记忆有问题；如果正确，简要说明", "正确": true/false}'

def call_judge(user_input: str, model_output: str, ground_truth: str) -> dict:
    """调用裁判模型"""
    output_text = strip_json_wrapper(str(model_output)) if model_output else ''
    gt_text = strip_json_wrapper(str(ground_truth)) if ground_truth else ''
    user_msg = f'用户输入：\n{str(user_input)}\n\n模型输出：\n{output_text}\n\nground_truth（仅供参考，非唯一标准答案）：\n{gt_text}\n\n请检查模型输出是否违反原则性规则。'
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
