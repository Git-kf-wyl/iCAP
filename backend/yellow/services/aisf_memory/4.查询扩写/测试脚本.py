# Private iCAP Yellow business implementation. Do not publish.
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import json
import numpy as np
import pandas as pd
from openai import OpenAI
import llm_client
input_path = '测试用例.xlsx'
output_path = '测试用例.xlsx'
FEW_SHOT_PATH = 'few_shot_library.json'
TOP_K = 5
RUN_SOURCES = ['badcase']
RUN_SOURCES = ['联通', '自测', '自生成', '茗威_不应该召回记忆', 'badcase']
RUN_MODELS = ['qwen3-8b']
PROMPT_VERSIONS = {'原版': ('查询扩写_原版.txt', False), 'fewshot': ('查询扩写_fewshot.txt', True)}
RUN_VERSIONS = ['原版', 'fewshot']

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
use_fewshot = {}
for ver, (path, is_fewshot) in PROMPT_VERSIONS.items():
    if ver not in RUN_VERSIONS:
        continue
    with open(path, 'r', encoding='utf-8') as f:
        prompts[ver] = f.read()
    use_fewshot[ver] = is_fewshot
FEW_SHOT_LIBRARY = None
_embed_index = None
_fs_queries = None
EMBED_MODEL = 'text-embedding-v3'
EMBED_DIM = 512
EMBED_BATCH = 10
EMBED_CACHE_PATH = 'few_shot_embeddings.npy'
_embed_client = OpenAI(api_key=llm_client._EXTERNAL_API_KEY, base_url='https://dashscope.aliyuncs.com/compatible-mode/v1')

def _get_embeddings(texts: list) -> np.ndarray:
    all_vecs = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        resp = _embed_client.embeddings.create(model=EMBED_MODEL, input=batch, dimensions=EMBED_DIM)
        vecs = [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]
        all_vecs.extend(vecs)
    mat = np.array(all_vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return mat / norms

def _init_fewshot():
    global FEW_SHOT_LIBRARY, _embed_index, _fs_queries
    if FEW_SHOT_LIBRARY is not None:
        return
    with open(FEW_SHOT_PATH, 'r', encoding='utf-8') as f:
        FEW_SHOT_LIBRARY = json.load(f)
    _fs_queries = [item['query_text'] for item in FEW_SHOT_LIBRARY]
    if os.path.exists(EMBED_CACHE_PATH):
        mat = np.load(EMBED_CACHE_PATH)
        if mat.shape[0] == len(FEW_SHOT_LIBRARY):
            print(f'已加载 embedding 缓存：{mat.shape}')
            _embed_index = mat
            return
        print('缓存条数与库不一致，重新生成...')
    print(f'生成 {len(FEW_SHOT_LIBRARY)} 条 few-shot embedding，请稍候...')
    mat = _get_embeddings(_fs_queries)
    np.save(EMBED_CACHE_PATH, mat)
    print(f'embedding 已缓存至 {EMBED_CACHE_PATH}')
    _embed_index = mat

def select_top_k(query: str, k: int=TOP_K) -> list:
    q_vec = _get_embeddings([query])[0]
    scores = _embed_index @ q_vec
    top_idx = np.argsort(scores)[::-1][:k]
    return [FEW_SHOT_LIBRARY[i] for i in top_idx]

def _format_examples(examples: list) -> str:
    lines = []
    for i, ex in enumerate(examples, 1):
        rq = json.dumps(ex['rewrite_queries'], ensure_ascii=False)
        lines.append(f'### 示例{i}')
        lines.append(f"输入：{ex['query_text']}")
        lines.append(f'输出：{rq}')
        lines.append('')
    return '\n'.join(lines).strip()

def build_system_prompt(ver: str, query: str) -> str:
    """根据版本构建 system prompt。原版直接返回，fewshot 版动态注入示例。"""
    template = prompts[ver]
    if not use_fewshot.get(ver, False):
        return template
    cut_marker = '// 下面是一些示例的格式'
    if cut_marker in template:
        template = template[:template.index(cut_marker)].rstrip()
    examples = select_top_k(query)
    examples_text = _format_examples(examples)
    return template.replace('{{few_shot}}', examples_text)
df = pd.read_excel(input_path, sheet_name='Sheet1')
for model in RUN_MODELS:
    for ver in RUN_VERSIONS:
        col = col_name(model, ver)
        if col not in df.columns:
            df[col] = None

def call_model(model: str, ver: str, user_query: str) -> str:
    system_prompt = build_system_prompt(ver, user_query)
    return llm_client.invoke_model(system_prompt, user_query, model)

def main():
    if any((use_fewshot.get(v, False) for v in RUN_VERSIONS)):
        _init_fewshot()
    target = df[df['用例来源'].isin(RUN_SOURCES)]
    print(f'运行来源：{RUN_SOURCES}，共 {len(target)} 条')
    print(f'运行模型：{RUN_MODELS}，版本：{RUN_VERSIONS}')
    print()
    for idx in target.index:
        user_query = df.at[idx, 'user_query']
        source = df.at[idx, '用例来源']
        print(f'========== [{idx + 1}/{len(df)}] 来源={source} ==========')
        print(f'输入：{user_query}')
        for model in RUN_MODELS:
            for ver in RUN_VERSIONS:
                result = call_model(model, ver, user_query)
                result = strip_json_wrapper(result)
                df.at[idx, col_name(model, ver)] = result
                print(f'[{model} | {ver}] -> {result}')
        print()
        df.to_excel(output_path, index=False, engine='openpyxl')
    print('全部处理完成！')
