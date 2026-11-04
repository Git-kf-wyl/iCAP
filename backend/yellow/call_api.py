"""Backend-only DeepSeek gateway used by the original Yellow evaluators."""
import json
import os
from pathlib import Path
from openai import OpenAI
import httpx

EVAL_JUDGE_MODEL_NAME = os.getenv('YELLOW_JUDGE_MODEL', 'deepseek-chat')
EVAL_JUDGE_MODEL_URL = 'http://127.0.0.1:'+os.environ.get('YELLOW_WORKER_PORT','1')+'/_model/v1'

def _client(model=None):
    rows=json.loads(Path('backend/config/model_cfg.json').read_text('utf-8'))
    row=next((r for r in rows if model in (r['model_id'],r['info']['model_name'])),None)
    if row is None:
        row=next((r for r in rows if r['model_id']==EVAL_JUDGE_MODEL_NAME),None)
    if not row:
        row=rows[0] if rows else None
    if not row:raise RuntimeError('没有可用的 DeepSeek 模型，请先配置模型连接')
    endpoint=row['config']['api_params_available'][0]
    url=endpoint['endpoint'].removesuffix('/chat/completions')
    return OpenAI(base_url=url,api_key=endpoint['api_key'] or 'EMPTY',timeout=180,http_client=httpx.Client(trust_env=False)),row['model_id']

def get_response_chat(model_name=None, messages=None, query=None, **kwargs):
    if isinstance(model_name,dict):model_name=model_name.get('model_id')
    if isinstance(query,dict):kwargs={**query,**kwargs};query=None
    client,model=_client(model_name or kwargs.get('model'))
    messages=messages or [{'role':'user','content':query or kwargs.get('prompt','')}]
    options={k:v for k,v in kwargs.items() if k in ('temperature','top_p','max_tokens')}
    response=client.chat.completions.create(model=model,messages=messages,**options)
    return response.choices[0].message.content or ''

def call_judge_model(model_name=None, prompt=None, summary_type=None, system_prompt='', **kwargs):
    if prompt is None:prompt=model_name
    messages=kwargs.pop('messages',None) or ([{'role':'system','content':system_prompt}] if system_prompt else [])+[{'role':'user','content':prompt or kwargs.pop('query','')}]
    return get_response_chat(EVAL_JUDGE_MODEL_NAME,messages=messages,**kwargs)
