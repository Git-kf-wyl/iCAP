# Private iCAP Yellow business implementation. Do not publish.
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pandas as pd
import llm_client
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
RUN_SOURCES = ['自测', 'mingwei']
RUN_MODELS = ['qwen3-32b']
PROMPT_VERSIONS = {'v1.0': '画像记忆更新.txt'}
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
prompts = {}
for ver in RUN_VERSIONS:
    with open(PROMPT_VERSIONS[ver], 'r', encoding='utf-8') as f:
        prompts[ver] = f.read()
df = pd.read_excel(input_path, sheet_name='Sheet1')
for model in RUN_MODELS:
    for ver in RUN_VERSIONS:
        col = col_name(model, ver)
        if col not in df.columns:
            df[col] = None

def call_model(model: str, system_prompt: str, user_query: str) -> str:
    return llm_client.invoke_model(system_prompt, user_query, model)

def main():
    target = df[df['用例来源'].isin(RUN_SOURCES)]
    print(f'运行来源：{RUN_SOURCES}，共 {len(target)} 条')
    print(f'运行模型：{RUN_MODELS}，版本：{RUN_VERSIONS}')
    print()
    for idx in target.index:
        user_query = df.at[idx, 'user_query']
        source = df.at[idx, '用例来源']
        scene = df.at[idx, '场景说明'] if '场景说明' in df.columns else ''
        print(f'========== [{idx + 1}/{len(df)}] 来源={source} {scene} ==========')
        print(f'输入：{user_query}')
        for m in RUN_MODELS:
            for v in RUN_VERSIONS:
                result = call_model(m, prompts[v], user_query)
                result = strip_json_wrapper(result)
                df.at[idx, col_name(m, v)] = result
                print(f'[{m} | {v}] -> {result}')
        print()
        df.to_excel(output_path, index=False, engine='openpyxl')
    print('全部处理完成！')
