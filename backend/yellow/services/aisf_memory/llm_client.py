# Private iCAP Yellow business implementation. Do not publish.
import os
import requests
from openai import OpenAI
_EXTERNAL_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
_EXTERNAL_API_KEY = ''
_INTERNAL_MODEL_URLS = {'Qwen3-8B': 'http://9.15.87.199:8083/v1/chat/completions', 'Qwen3-32B': 'http://9.15.87.148:8084/v1/chat/completions'}
_INTERNAL_MODEL_NAMES = {}
_INTERNAL_MODEL_OPTIONS = {}

def invoke_model(system_prompt: str, user_prompt: str, model_name: str='qwen-max', source: str='external') -> str:
    if source == 'external':
        return _call_external(system_prompt, user_prompt, model_name)
    elif source == 'internal':
        return _call_internal(system_prompt, user_prompt, model_name)
    else:
        raise ValueError(f"未知 source: {source}，可选值为 'external' 或 'internal'")

def _call_external(system_prompt: str, user_prompt: str, model_name: str) -> str:
    try:
        client = OpenAI(api_key=_EXTERNAL_API_KEY, base_url=_EXTERNAL_BASE_URL)
        response = client.chat.completions.create(model=model_name, messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], extra_body={'enable_thinking': False}, temperature=0)
        return response.choices[0].message.content
    except Exception as e:
        print(f'外部模型调用失败: {e}')
        return None

def _call_internal(system_prompt: str, user_prompt: str, model_name: str) -> str:
    if model_name not in _INTERNAL_MODEL_URLS:
        raise ValueError(f'未知内部模型: {model_name}，可选值为 {list(_INTERNAL_MODEL_URLS.keys())}')
    url = _INTERNAL_MODEL_URLS[model_name]
    opts = _INTERNAL_MODEL_OPTIONS.get(model_name, {})
    payload = {'model': _INTERNAL_MODEL_NAMES.get(model_name, model_name), 'messages': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}], 'temperature': 0}
    thinking_format = opts.get('thinking_format', 'chat_template_kwargs')
    enable_thinking = opts.get('enable_thinking', False)
    if thinking_format == 'thinking_dict':
        payload['thinking'] = {'type': 'enabled' if enable_thinking else 'disabled'}
    else:
        payload['chat_template_kwargs'] = {'enable_thinking': enable_thinking}
    headers = {'Content-Type': 'application/json'}
    token = opts.get('auth_token') or ''
    if not token:
        auth_env = opts.get('auth_token_env')
        if auth_env:
            token = os.environ.get(auth_env, '')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        r = requests.post(url=url, json=payload, headers=headers, timeout=120, verify=opts.get('verify_ssl', True))
        choice = r.json()['choices'][0]
        content = choice['message'].get('content')
        if content is None:
            content = choice['message'].get('reasoning_content', '') or ''
        if opts.get('strip_thinking_tags', True):
            content = content.split('</think>')[-1].strip()
        return content
    except Exception as e:
        print(f'内部模型调用失败: {e}')
        return None
