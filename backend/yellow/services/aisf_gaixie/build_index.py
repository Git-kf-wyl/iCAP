# Private iCAP Yellow business implementation. Do not publish.
import json
from pathlib import Path
import faiss
import numpy as np
import requests
from tqdm import tqdm
JSONL_PATH = 'few_shot_examples_0708_with_prev_content.jsonl'
INDEX_DIR = 'index'
EMBEDDING_URL = 'http://127.0.0.1:1/unconfigured'
EMBEDDING_MODEL = 'bge-small-zh'
BATCH_SIZE = 32

def load_jsonl(path):
    items = []
    with open(path, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f'JSONL 第 {line_no} 行不是合法 JSON') from e
            if item.get('enabled', True) is False:
                continue
            items.append(item)
    return items

def request_embeddings(texts):
    """
    调用 embedding 服务。

    默认按 OpenAI compatible 格式：
    POST /v1/embeddings
    {
      "model": "...",
      "input": ["文本1", "文本2"]
    }

    返回：
    {
      "data": [
        {"embedding": [...]},
        {"embedding": [...]}
      ]
    }

    接口格式不同的话，只改这个函数。
    """
    payload = {'model': EMBEDDING_MODEL, 'input': texts}
    resp = requests.post(EMBEDDING_URL, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if 'data' in data:
        return [x['embedding'] for x in data['data']]
    if 'embeddings' in data:
        return data['embeddings']
    if 'vectors' in data:
        return data['vectors']
    raise ValueError(f'无法识别 embedding 接口返回格式：{data}')

def embed_texts(texts, batch_size=32):
    all_vectors = []
    for i in tqdm(range(0, len(texts), batch_size), desc='Embedding'):
        batch = texts[i:i + batch_size]
        vectors = request_embeddings(batch)
        all_vectors.extend(vectors)
    vectors = np.array(all_vectors, dtype='float32')
    faiss.normalize_L2(vectors)
    return vectors

def build_faiss_index(vectors):
    dim = vectors.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(vectors)
    return index

def save_jsonl(items, path):
    with open(path, 'w', encoding='utf-8') as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False, separators=(',', ':')))
            f.write('\n')

def main():
    jsonl_path = Path(JSONL_PATH)
    index_dir = Path(INDEX_DIR)
    index_dir.mkdir(parents=True, exist_ok=True)
    items = load_jsonl(jsonl_path)
    if not items:
        raise ValueError('JSONL 里没有可用样本')
    print(f'读取样本数：{len(items)}')
    cur_texts = []
    prev_cur_texts = []
    metadata = []
    for idx, item in enumerate(items):
        item_id = item.get('id', f'ROW_{idx}')
        cur_text = item.get('embedding_text_cur', '')
        prev_cur_text = item.get('embedding_text_prev_cur', '')
        if not cur_text:
            raise ValueError(f'样本 {item_id} 缺少 embedding_text_cur')
        if not prev_cur_text:
            prev_cur_text = cur_text
        cur_texts.append(cur_text)
        prev_cur_texts.append(prev_cur_text)
        metadata.append({'_index': idx, 'id': item_id, 'rule_type': item.get('rule_type', ''), 'labels': item.get('labels', []), 'history': item.get('history', []), 'current_query': item.get('current_query', ''), 'embedding_text_cur': cur_text, 'embedding_text_prev_cur': prev_cur_text, 'answer': item.get('answer', {}), 'answer_no_thought': item.get('answer_no_thought', {}), 'prompt_example': item.get('prompt_example', ''), 'no_thought_example': item.get('no_thought_example', '')})
    print('\n开始构建 cur 索引...')
    cur_vectors = embed_texts(cur_texts, BATCH_SIZE)
    cur_index = build_faiss_index(cur_vectors)
    print('\n开始构建 prev_cur 索引...')
    prev_cur_vectors = embed_texts(prev_cur_texts, BATCH_SIZE)
    prev_cur_index = build_faiss_index(prev_cur_vectors)
    cur_index_path = index_dir / 'cur.faiss'
    prev_cur_index_path = index_dir / 'prev_cur.faiss'
    metadata_path = index_dir / 'metadata.jsonl'
    faiss.write_index(cur_index, str(cur_index_path))
    faiss.write_index(prev_cur_index, str(prev_cur_index_path))
    save_jsonl(metadata, metadata_path)
    print('\n索引构建完成：')
    print(f'cur 索引：{cur_index_path.resolve()}')
    print(f'prev_cur 索引：{prev_cur_index_path.resolve()}')
    print(f'metadata：{metadata_path.resolve()}')
    print(f'向量维度：{cur_vectors.shape[1]}')
    print(f'样本数量：{len(metadata)}')
