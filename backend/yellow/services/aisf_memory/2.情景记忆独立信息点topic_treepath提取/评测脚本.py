# Private iCAP Yellow business implementation. Do not publish.
"""
情景记忆提取评测脚本
使用 LLM-as-judge 评估模型输出是否正确

评测维度：
  - 是否误提问句/指令
  - 是否误提画像级长期信息（应为情景记忆）
  - 是否误提单次音乐/观影行为
  - 是否误提物品静态信息
  - topic 是否合理、detail 是否包含时间/地点/对象等要素

统计维度：用例来源 × 模型 × 版本
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pandas as pd
import llm_client
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
JUDGE_MODEL = 'qwen3.7-plus'
EVAL_COLUMNS = ['answer_qwen3-32b_v1.0', 'answer_qwen3-32b_v2.0']
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
EVAL_SYSTEM_PROMPT = '你是情景记忆提取的评测专家。你的任务是判断模型从用户对话中提取的情景记忆是否正确。\n\n## 评测标准\n情景记忆是与用户绑定的具体事件、经历、活动、计划、阶段性进展或行为结果，需要有时间/场景关联。\n\n**错误类型（任一命中即判错）：**\n\n1. 误提问句：把用户的查询问句当作事件提取。如"我上次去哪旅游了？"→ 不能包装成情景记忆。输出中出现"用户询问/想知道/不确定"等即判错。\n2. 误提指令：提取了任务请求、工具调用、推荐、搜索、播放、导航、提醒等即时需求。\n3. 误提单次音乐/观影/搜索：提取了单次播放音乐、单次观影、单次搜索行为。但阶段性、重复性的文化娱乐活动可以提取。\n4. 误提画像信息：提取了脱离具体事件的长期偏好、身份属性、稳定关系、重要日期、物品静态位置等画像级信息。如"我喜欢科幻片""妈妈生日是12月15日""车钥匙放在鞋柜上"。\n5. 误提无行为抽象状态：如"我最近很忙""我有点饿""我想出去玩"等无具体行为的状态描述。\n6. 误提通用知识/语义记忆：提取了算法定义、公开事实、概念解释等。\n7. 输出格式错误：输出不是合法的 JSON 数组，或数组中元素缺少 topic/detail 字段。\n8. 凭空捏造：detail 中包含用户输入中未出现的信息。\n\n**正确示例的特征：**\n- 提取的内容有明确行为主体 + 具体行为 + 时间/地点/对象/结果中的至少两项\n- 问句、指令、单次音乐/观影正确跳过\n- 画像级长期信息正确跳过\n- topic 简短概括事件类型，detail 是完整的第三人称陈述句\n\n## 输出格式\n{"正确": true/false, "原因": "一句话说明判定依据，指出具体哪条记忆有问题"}\n\n注意：如果输出是空数组 []，且输入确实只有问句/指令/画像信息/单次观影音乐，则判定为正确。'

def call_judge(user_input: str, model_output: str) -> dict:
    """调用裁判模型"""
    output_text = strip_json_wrapper(str(model_output)) if model_output else ''
    user_msg = f'用户输入：\n{str(user_input)[:3000]}\n\n模型输出：\n{output_text[:3000]}\n\n请评测以上模型输出是否正确。'
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
        source_stats = {}
        for idx in df.index:
            raw = df.at[idx, ans_col]
            if pd.isna(raw):
                continue
            user_query = df.at[idx, 'user_query']
            source = df.at[idx, '用例来源']
            result = call_judge(user_query, raw)
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
