# Private iCAP Yellow business implementation. Do not publish.
import json
import platform
from pathlib import Path
import faiss
import numpy as np
import requests

def _to_ascii_path(path):
    """Windows 下将含中文的路径转为短路径（8.3 格式），
    避免 FAISS C++ 层 fopen 无法处理 UTF-8 路径。"""
    if platform.system() != 'Windows':
        return str(path)
    import ctypes
    from ctypes import wintypes
    buf = ctypes.create_unicode_buffer(260)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, len(buf))
    if n == 0 or n > len(buf):
        return str(path)
    return buf.value

def clean_text(value):
    if value is None:
        return ''
    return str(value).strip()

def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default

def load_jsonl(path):
    path = _to_ascii_path(path)
    items = []
    with open(path, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f'JSONL 第 {line_no} 行不是合法 JSON') from e
    return items

def format_fewshot_blocks(items, example_field):
    blocks = []
    for idx, item in enumerate(items, start=1):
        body = clean_text(item.get(example_field, ''))
        if body:
            blocks.append(f'示例{idx}：\n{body}')
    return '\n\n---\n\n'.join(blocks)

class LocalFewShotRetriever:
    """
    本地 FAISS few-shot 召回器。

    支持两种单索引模式：
    - query：使用 cur.faiss，只按当前用户输入召回
    - prev_current：使用 prev_cur.faiss，按上一轮用户输入 + 当前用户输入召回

    分数规则：
    - 使用 L2 距离
    - score 越小越相似
    """

    def __init__(self, index_dir, embedding_url, embedding_model='', retrieval_mode='prev_current', example_field='no_thought_example', normalize_query_vector=True, request_timeout=300, verify_ssl=False):
        self.index_dir = Path(index_dir)
        self.embedding_url = embedding_url
        self.embedding_model = embedding_model
        self.retrieval_mode = self.normalize_retrieval_mode(retrieval_mode)
        self.example_field = example_field
        self.normalize_query_vector = normalize_query_vector
        self.request_timeout = request_timeout
        self.verify_ssl = verify_ssl
        self.index_path = self.get_index_path()
        self.metadata_path = self.index_dir / 'metadata.jsonl'
        self.index = self.load_index()
        self.metadata = self.load_metadata()
        if self.index.ntotal != len(self.metadata):
            raise ValueError(f'FAISS 索引数量和 metadata 数量不一致：index.ntotal={self.index.ntotal}, metadata={len(self.metadata)}')

    @staticmethod
    def normalize_retrieval_mode(mode):
        mode = clean_text(mode).lower()
        if mode in ['query', 'cur', 'current', 'current_query', 'embedding_text_cur']:
            return 'query'
        if mode in ['prev_current', 'prev_cur', 'previous_current', 'prev_current_query', 'embedding_text_prev_cur']:
            return 'prev_current'
        return 'prev_current'

    def get_index_path(self):
        if self.retrieval_mode == 'query':
            return self.index_dir / 'cur.faiss'
        if self.retrieval_mode == 'prev_current':
            return self.index_dir / 'prev_cur.faiss'
        raise ValueError(f'不支持的 retrieval_mode：{self.retrieval_mode}')

    def load_index(self):
        index_path_ascii = _to_ascii_path(self.index_path)
        if not Path(index_path_ascii).exists():
            raise FileNotFoundError(f'找不到 FAISS 索引：{self.index_path.resolve()}')
        return faiss.read_index(index_path_ascii)

    def load_metadata(self):
        meta_path_ascii = _to_ascii_path(self.metadata_path)
        if not Path(meta_path_ascii).exists():
            raise FileNotFoundError(f'找不到 metadata.jsonl：{self.metadata_path.resolve()}')
        return load_jsonl(meta_path_ascii)

    def request_embedding(self, text):
        text = clean_text(text)
        if not text:
            raise ValueError('embedding query text 不能为空')
        payload = {'input': [text]}
        if clean_text(self.embedding_model):
            payload['model'] = self.embedding_model
        resp = requests.post(self.embedding_url, json=payload, timeout=self.request_timeout, verify=self.verify_ssl)
        resp.raise_for_status()
        data = resp.json()
        if 'data' in data:
            return data['data'][0]['embedding']
        if 'embeddings' in data:
            return data['embeddings'][0]
        if 'vectors' in data:
            return data['vectors'][0]
        raise ValueError(f'无法识别 embedding 接口返回格式：{data}')

    def embed_query(self, query_text):
        embedding = self.request_embedding(query_text)
        vector = np.array([embedding], dtype='float32')
        if self.normalize_query_vector:
            faiss.normalize_L2(vector)
        return vector

    def build_query_text(self, query_value, prev_current_query_value=''):
        query_value = clean_text(query_value)
        prev_current_query_value = clean_text(prev_current_query_value)
        if self.retrieval_mode == 'query':
            return query_value
        if self.retrieval_mode == 'prev_current':
            return prev_current_query_value or query_value
        return query_value

    def build_output_item(self, meta, score):
        current_query = meta.get('current_query', '') or meta.get('embedding_text_cur', '')
        prev_current_query = meta.get('prev_current_query', '') or meta.get('embedding_text_prev_cur', '')
        item = {'id': meta.get('id', ''), 'score': float(score), 'hit_source': self.retrieval_mode, 'route_scores': {self.retrieval_mode: float(score)}, 'rule_type': meta.get('rule_type', ''), 'labels': meta.get('labels', []), 'current_query': current_query, 'prev_current_query': prev_current_query, 'prompt_example': meta.get('prompt_example', ''), 'no_thought_example': meta.get('no_thought_example', ''), 'answer': meta.get('answer', {}), 'answer_no_thought': meta.get('answer_no_thought', {})}
        item['example_text'] = clean_text(item.get(self.example_field, ''))
        return item

    def search(self, query_value, prev_current_query_value='', top_k=5):
        query_value = clean_text(query_value)
        if not query_value:
            return ('', 'query_value 为空，跳过召回', False, [])
        actual_query_text = self.build_query_text(query_value=query_value, prev_current_query_value=prev_current_query_value)
        query_vector = self.embed_query(actual_query_text)
        if query_vector.shape[1] != self.index.d:
            raise ValueError(f'查询向量维度和索引维度不一致：query_dim={query_vector.shape[1]}, index_dim={self.index.d}')
        scores, indexes = self.index.search(query_vector, top_k)
        ordered_items = []
        for score, idx in zip(scores[0], indexes[0]):
            if idx < 0:
                continue
            meta = self.metadata[int(idx)]
            item = self.build_output_item(meta, float(score))
            ordered_items.append(item)
        ordered_items = sorted(ordered_items, key=lambda x: safe_float(x.get('score', 0.0)))
        raw_fewshot_text = format_fewshot_blocks(ordered_items, example_field=self.example_field)
        has_fewshot = any((clean_text(item.get(self.example_field, '')) for item in ordered_items))
        debug_payload = {'retriever': 'local_faiss', 'retrieval_mode': self.retrieval_mode, 'score_type': 'l2_distance', 'score_direction': 'smaller_is_better', 'index_path': str(self.index_path), 'metadata_path': str(self.metadata_path), 'top_k': top_k, 'example_field': self.example_field, 'query_value': query_value, 'prev_current_query_value': prev_current_query_value, 'actual_query_text': actual_query_text, 'scores_asc': [safe_float(item.get('score', 0.0)) for item in ordered_items], 'items_preview': [{'score': item.get('score'), 'id': item.get('id'), 'hit_source': item.get('hit_source'), 'rule_type': item.get('rule_type'), 'labels': item.get('labels'), 'current_query': item.get('current_query'), 'prev_current_query': item.get('prev_current_query'), 'example_empty': not bool(clean_text(item.get(self.example_field, ''))), 'example_preview': clean_text(item.get(self.example_field, ''))[:120]} for item in ordered_items[:5]]}
        debug_text = '\n'.join(['====== Local FAISS Few-shot Debug ======', json.dumps(debug_payload, ensure_ascii=False, indent=2)])
        return (raw_fewshot_text, debug_text, has_fewshot, ordered_items)
_RETRIEVER_CACHE = {}

def search_fewshot(query_value, prev_current_query_value='', top_k=5, index_dir='0528/index', embedding_url='http://127.0.0.1:8000/v1/embeddings', embedding_model='', retrieval_mode='prev_current', example_field='no_thought_example', normalize_query_vector=True):
    """
    给批量脚本调用的入口函数。

    返回：
    - raw_fewshot_text
    - debug_text
    - has_fewshot
    - ordered_items
    """
    cache_key = json.dumps({'index_dir': index_dir, 'embedding_url': embedding_url, 'embedding_model': embedding_model, 'retrieval_mode': retrieval_mode, 'example_field': example_field, 'normalize_query_vector': normalize_query_vector}, ensure_ascii=False, sort_keys=True)
    if cache_key not in _RETRIEVER_CACHE:
        _RETRIEVER_CACHE[cache_key] = LocalFewShotRetriever(index_dir=index_dir, embedding_url=embedding_url, embedding_model=embedding_model, retrieval_mode=retrieval_mode, example_field=example_field, normalize_query_vector=normalize_query_vector)
    retriever = _RETRIEVER_CACHE[cache_key]
    return retriever.search(query_value=query_value, prev_current_query_value=prev_current_query_value, top_k=top_k)
