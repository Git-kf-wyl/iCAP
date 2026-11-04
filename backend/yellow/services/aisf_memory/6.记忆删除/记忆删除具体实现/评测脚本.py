# Private iCAP Yellow business implementation. Do not publish.
"""
记忆删除具体实现评测脚本
使用 LLM-as-judge 评估模型输出，可传入参考答案辅助判定

评测维度：
  - 操作类型（delete/update/[]）是否正确
  - 删除目标 id 是否正确
  - update 后的 detail 是否正确移除了删除目标
  - 是否误删无关记忆
  - 是否扩大删除范围

统计维度：用例来源 × 模型 × 版本
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
import pandas as pd
import llm_client
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
JUDGE_MODEL = 'qwen3.7-plus'
EVAL_COLUMNS = ['answer_qwen3-32b_v1.0', 'answer_qwen-max_v1.0']
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
EVAL_SYSTEM_PROMPT = '你是记忆删除具体实现的评测专家。你的任务是判断模型对删除指令的处理是否正确。\n\n## 背景\n输入包含用户的删除指令（query）和相关记忆列表。模型需要判断每条记忆是否包含删除目标，输出 delete（完全匹配整条删除）、update（部分匹配保留剩余信息）或 []（无匹配不操作）。\n\n## 评测标准\n\n**对照参考答案逐项检查：**\n\n1. 操作数量一致：模型输出的操作数量应与参考答案一致\n2. 操作 id 一致：每条操作对应的记忆 id 应与参考答案匹配\n3. 操作类型一致：delete/update 类型应与参考答案一致\n4. update 的 detail 正确：移除删除目标后的保留内容应语义正确、不遗漏有效信息、不保留已删除信息\n5. 不扩大删除：不应删除参考答案中没有的 id\n6. 不漏删：不应遗漏参考答案中标记的 id\n\n**判定原则：**\n- 参考答案是人工标注的正确结果，以参考答案为准\n- 模型输出与参考答案语义等价即判正确（措辞可以不完全一致，但核心操作要一致）\n- 如果模型输出 [] 且参考答案也是 []，判正确\n- 如果模型漏了某条该处理的记忆（参考答案有对应操作但模型没输出），判错误\n\n## 输出格式\n{"正确": true/false, "原因": "一句话说明判定依据"}'

def call_judge(user_input: str, model_output: str, reference: str) -> dict:
    """调用裁判模型"""
    output_text = strip_json_wrapper(str(model_output)) if model_output else ''
    user_msg = '输入:\n' + str(user_input)[:2000] + '\n\n'
    user_msg += '模型输出:\n' + output_text[:1500] + '\n\n'
    user_msg += '参考答案:\n' + str(reference)[:1500] + '\n\n'
    user_msg += '请评测以上模型输出是否正确。'
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
            reference = df.at[idx, '参考答案']
            source = df.at[idx, '用例来源']
            result = call_judge(user_query, raw, str(reference) if pd.notna(reference) else '')
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
        df.to_excel(output_path, index=False, engine='openpyxl')
        print()
    if len(all_summaries) > 1:
        print(f"{'=' * 60}")
        print('======= 多版本对比 =======')
        print(f"{'=' * 60}")
        cmp = pd.DataFrame(all_summaries)
        cmp['准确率'] = cmp['准确率'].apply(lambda x: f'{x:.1%}')
        print(cmp.to_string(index=False))
