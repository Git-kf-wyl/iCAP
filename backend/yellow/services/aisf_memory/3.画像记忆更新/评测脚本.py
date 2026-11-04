# Private iCAP Yellow business implementation. Do not publish.
"""
画像记忆更新评测脚本
使用 LLM-as-judge 评估模型输出是否正确

评测维度：
  - 操作类型（update/insert/[]）是否正确
  - 合并后的 detail 是否信息完整、逻辑通顺
  - 是否违反"有 update 就不能有 insert"规则
  - 唯一属性冲突处理是否正确
  - 去重是否正确（完全相同 → []）

统计维度：用例来源 × 模型 × 版本
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pandas as pd
import llm_client
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
JUDGE_MODEL = 'qwen3.7-plus'
EVAL_COLUMNS = ['answer_qwen3-32b_v1.0']
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
EVAL_SYSTEM_PROMPT = '你是画像记忆更新的评测专家。你的任务是检查模型输出是否违反以下**原则性规则**。\n\n## 背景\n输入包含"新提取的记忆"和"相似记忆"（已有记忆库）。模型需要判断关系，输出 update、insert 或 []。\n\n## 重要：ground_truth 仅供参考\nground_truth 是一个正确示例，但**不是唯一标准答案**。insert 和 update 的选择存在主观空间——同一个case，insert 合理，update 也可能合理。只要模型不违反以下原则性规则，即使与 ground_truth 的 opType 不同或操作数量不同，也应判对。\n\n## 原则性错误（任一命中即判错）\n\n1. **同时输出 update 和 insert**：核心规则禁止。只要模型输出中同时出现 opType="update" 和 opType="insert"，即判错。\n2. **完全重复未识别**：新记忆与某条已有记忆的 topic、subtopic、detail 核心语义完全等同，模型应输出 [] 却做了 update/insert。\n3. **唯一属性合并错误**：生日、手机号、年龄等唯一属性，新旧值不同时应用新值替换，不应把两个不同值合并（如"生日是1990.1.1和1995.5.5"）。\n4. **排除性词语未识别**：旧记忆有"只""从不""只喜欢"等排除词，且新记忆落入被排除范围，此时应用新值完全替换旧记忆，而非合并。\n5. **detail 有明显逻辑矛盾**：合并/替换后的 detail 出现自相矛盾（如"用户已婚又未婚""用户喜欢猫又不喜欢猫"）。\n6. **输出格式不合法**：输出不是合法的 JSON 数组，或元素缺少 id/opType/topic/subtopic/detail 字段。\n7. **同一新信息分散到多条已有记忆**：新记忆的核心信息只应合并到最匹配的一条已有记忆（做一次 update），或做一次 insert。如果模型输出了多条 update，且不同的 update 的 detail 中都融入了同一新记忆的核心内容（如新记忆"喜欢草莓"同时出现在了 update id:1 和 update id:3 的 detail 中），属于冗余/重复操作，判错。\n\n## 不算错误的情况（判对）\n- insert vs update 选择不同：模型选 insert，ground_truth 是 update（或反之），只要操作本身不违反上述原则 → 判对\n- 操作数量不同：模型只 update 了1条，ground_truth update 了2条，只要不违反原则 → 判对\n- detail 措辞不同但核心信息一致 → 判对\n- 模型输出 [] 但 ground_truth 有操作（或反之），只要不违反完全重复/原则性错误 → 判对\n\n## 输出格式\n{"原因": "如果错误，指出具体违反了哪条原则；如果正确，简要说明", "正确": true/false}'

def call_judge(user_input: str, model_output: str, ground_truth: str) -> dict:
    """调用裁判模型"""
    output_text = strip_json_wrapper(str(model_output)) if model_output else ''
    gt_text = strip_json_wrapper(str(ground_truth)) if ground_truth else ''
    user_msg = f'输入：\n{str(user_input)}\n\n模型输出：\n{output_text}\n\nground_truth（仅供参考，非唯一标准答案）：\n{gt_text}\n\n请检查模型输出是否违反原则性规则。'
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
