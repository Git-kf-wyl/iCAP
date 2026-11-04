# Private iCAP Yellow business implementation. Do not publish.
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
import pandas as pd
import llm_client
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
rule_table_path = '规则库表.xlsx'
RUN_MODELS = ['qwen3-8b', 'qwen3-32b']
PROMPT_VERSIONS = {'v1.0': '记忆删除意图识别.txt'}
RUN_VERSIONS = ['v1.0']

def col_name(model: str, ver: str) -> str:
    return f'answer_{model}_{ver}'

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

def load_keywords(path: str) -> list[str]:
    df = pd.read_excel(path, sheet_name='Sheet1')
    keywords = df[df['规则类型'] == '可疑关键词']['匹配模式'].tolist()
    print(f'规则库加载完成：可疑关键词 {len(keywords)} 个')
    return keywords
prompts = {}
for ver in RUN_VERSIONS:
    with open(PROMPT_VERSIONS[ver], 'r', encoding='utf-8') as f:
        prompts[ver] = f.read()
SUSPICIOUS_KEYWORDS = load_keywords(rule_table_path)
df = pd.read_excel(input_path, sheet_name='Sheet1')
for model in RUN_MODELS:
    for ver in RUN_VERSIONS:
        col = col_name(model, ver)
        if col not in df.columns:
            df[col] = None
if '判断路径' not in df.columns:
    df['判断路径'] = None

def has_suspicious_keyword(query: str) -> bool:
    return any((kw in query for kw in SUSPICIOUS_KEYWORDS))

def parse_llm_output(response: str) -> int:
    response = strip_json_wrapper(response)
    for char in response.strip():
        if char in ('0', '1', '2'):
            return int(char)
    return 0

def hybrid_detect(model: str, ver: str, query: str) -> tuple[int, str]:
    """返回 (预测结果 0/1/2, 判断路径)"""
    if not has_suspicious_keyword(query):
        return (0, '关键词过滤')
    raw = llm_client.invoke_model(prompts[ver], query, model)
    return (parse_llm_output(raw), 'LLM')

def main():
    print(f'运行模型：{RUN_MODELS}，版本：{RUN_VERSIONS}')
    print(f'共 {len(df)} 条用例\n')
    for model in RUN_MODELS:
        for ver in RUN_VERSIONS:
            col = col_name(model, ver)
            labels, predictions = ([], [])
            llm_count, kw_count = (0, 0)
            print(f"\n{'=' * 55}")
            print(f'开始运行模型：{model} | {ver}')
            print(f"{'=' * 55}")
            for idx, row in df.iterrows():
                query = str(row['用户query'])
                label = int(row['标准答案'])
                pred, path = hybrid_detect(model, ver, query)
                df.at[idx, col] = pred
                if ver == RUN_VERSIONS[0]:
                    df.at[idx, '判断路径'] = path
                labels.append(label)
                predictions.append(pred)
                if path == 'LLM':
                    llm_count += 1
                else:
                    kw_count += 1
                status = '✓' if pred == label else '✗'
                print(f"[{status}][{path}][{row['用例维度']}] {query}  →  预测:{pred} 真实:{label}")
            df.to_excel(output_path, index=False, engine='openpyxl')
            correct = sum((p == l for p, l in zip(predictions, labels)))
            acc = correct / len(labels) if labels else 0
            print(f'\n准确率：{correct}/{len(labels)} = {acc:.1%}')
            print(f'关键词过滤: {kw_count} 条  LLM判断: {llm_count} 条')
    print('\n全部处理完成！评测请运行 评测脚本.py')
