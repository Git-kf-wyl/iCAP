# Private iCAP Yellow business implementation. Do not publish.
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pandas as pd
import llm_client
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
RUN_SOURCES = ['自测']
RUN_MODELS = ['qwen3-8b']
PROMPT_VERSIONS = {'v1.0': '总结过滤_v1.0.txt', 'v2.0': '总结过滤_v2.0_若曦修改版.txt', 'v3.0': '总结过滤_v3.0_伪思考长思考.txt', 'v3.1': '总结过滤_v3.1_伪思考短思考.txt'}
RUN_VERSIONS = ['v1.0', 'v2.0', 'v3.0', 'v3.1']

def col_name(model: str, ver: str) -> str:
    return f'answer_{model}_{ver}'
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
        ref = df.at[idx, '参考答案']
        print(f'========== [{idx + 1}/{len(df)}] 来源={source} ==========')
        print(f'输入：{user_query}')
        if pd.notna(ref):
            print(f'参考：{ref}')
        for model in RUN_MODELS:
            for ver in RUN_VERSIONS:
                result = call_model(model, prompts[ver], user_query)
                col = col_name(model, ver)
                df.at[idx, col] = result
                print(f'[{model} | {ver}] -> {result}')
        print()
        df.to_excel(output_path, index=False, engine='openpyxl')
    print('全部处理完成！')
