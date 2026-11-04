# Private iCAP Yellow implementation. Do not publish.
import os
import requests
import json
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice, CompletionUsage
from non_openai_api.model_lib.qwen_lib import *

def common_vllm_call_func(url, system_prompt, prompt, model_name):
    headers = {'Content-Type': 'application/json'}
    payload = {'model': model_name, 'messages': [{'role': 'user', 'content': prompt[0]['content']}], 'stream': False}
    if system_prompt:
        payload['messages'].append({'role': 'system', 'content': system_prompt})
    r = requests.post(url=url, json=payload, headers=headers)
    if r.status_code == 200:
        return json.loads(r.text)['choices'][0]['message']['content']
    else:
        raise ConnectionError('Failed to connect to Local server')

def split_response(full_content):
    """
        从模型回答中提取并移除 <思考过程>...</思考过程> 和 <think>... 部分。

        参数:
            text (str): 模型输出的原始文本

        返回:
            tuple: (思考过程合并文本, 清理后文本)
        """
    thinking_process_str = ''
    if '<思考过程>' in full_content:
        thinking_process_str = full_content.split('<思考过程>')[0].strip()
        cleaned_text = full_content.split('<思考过程>')[-1].strip()
    elif '</think>' in full_content:
        thinking_process_str = full_content.split('</think>')[0].strip()
        cleaned_text = full_content.split('</think>')[-1].strip()
    elif '[unused17]' in full_content:
        thinking_process_str = full_content.split('[unused17]')[0].strip()
        cleaned_text = full_content.split('[unused17]')[-1].strip()
    else:
        cleaned_text = full_content.strip()
    return (thinking_process_str, cleaned_text)

def get_non_openai_response(url, model_name, querys):
    old_http_proxy = os.getenv('HTTP_PROXY')
    old_https_proxy = os.getenv('HTTPS_PROXY')
    os.environ['HTTP_PROXY'] = ''
    os.environ['HTTPS_PROXY'] = ''
    trans_model_name = model_name.strip()
    system_prompt = ''
    prompt = []
    for query in querys:
        if isinstance(query, ChatCompletionMessage):
            prompt.append({'role': query.role, 'content': query.content})
        elif query.get('role') == 'system':
            system_prompt = query['content']
        else:
            prompt.append(query)
    model_function = globals().get(model_name)
    if callable(model_function):
        try:
            full_content = model_function(url, system_prompt, prompt)
        except Exception as e:
            raise ValueError(f'model function exec err! {e}')
    else:
        try:
            full_content = common_vllm_call_func(url, system_prompt, prompt, trans_model_name)
        except Exception as e:
            raise ValueError(f'model function exec err! {e}')
        os.environ['HTTP_PROXY'] = old_http_proxy if old_http_proxy else ''
        os.environ['HTTPS_PROXY'] = old_https_proxy if old_https_proxy else ''
    reasoning_content, content = split_response(full_content)
    os.environ['HTTP_PROXY'] = old_http_proxy if old_http_proxy else ''
    os.environ['HTTPS_PROXY'] = old_https_proxy if old_https_proxy else ''
    return ChatCompletion(id='0', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content=content, refusal=None, role='assistant', annotations=None, audio=None, reasoning_content=reasoning_content, model_extra={'reasoning_content': reasoning_content}, function_call=None, tool_calls=None))], created=0, model=model_name, object='chat.completion', usage=CompletionUsage(completion_tokens=5, prompt_tokens=21, total_tokens=26, completion_tokens_details=None, prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=21))
