# Private iCAP Yellow implementation. Do not publish.
import time
import base64
import requests
import os
import json
import re

def qwen_qwq_32b(system_prompt, query):
    r = requests.post(url='http://127.0.0.1:1/unconfigured', json={'query': [{'role': 'system', 'content': [{'type': 'text', 'text': system_prompt}]}, {'role': 'user', 'content': [{'type': 'text', 'text': query}]}]}, headers={'Content-Type': 'application/json'})
    if r.status_code == 200:
        return r.text
    else:
        raise ConnectionError('Failed to connect to Local QWQ server')

def qwq_32b(url, system_prompt, query):
    r = requests.post(url=url, json={'query': [{'role': 'system', 'content': [{'type': 'text', 'text': system_prompt}]}, {'role': 'user', 'content': [{'type': 'text', 'text': query}]}]}, headers={'Content-Type': 'application/json'})
    if r.status_code == 200:
        return r.text
    else:
        raise ConnectionError('Failed to connect to Local QWQ server')

def qwen3_30b_a3b(system_prompt, query):
    url = 'http://127.0.0.1:1/unconfigured'
    model_name = 'Qwen3-30B-A3B'
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': query}]
    payload = {'model': model_name, 'messages': messages}
    headers = {'Content-Type': 'application/json'}
    response = requests.request('POST', url, json=payload, headers=headers, verify=True)
    result = response.json()
    return result['choices'][0]['message']['content']

def qwen3_32b_zs(system_prompt, query):
    r = requests.post(url='http://127.0.0.1:1/unconfigured', json={'query': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': query}]}, headers={'Content-Type': 'application/json'})
    return r.text

def qwen3_30b_a3b_zs(system_prompt, query):
    r = requests.post(url='http://127.0.0.1:1/unconfigured', json={'query': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': query}]}, headers={'Content-Type': 'application/json'})
    return r.text

def qwen3_8b_zs(system_prompt, query):
    r = requests.post(url='http://127.0.0.1:1/unconfigured', json={'query': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': query}]}, headers={'Content-Type': 'application/json'})
    return r.text

def qwen34b(system_prompt, query):
    model_id = 'Qwen3-4B'
    thinking = True
    history = None
    model = {'Qwen3-4B': 'http://100.100.48.102:11004/v1/chat/completions'}
    start_time = time.time()
    if history is None:
        history = []
    '\n    if type(query) != str:\n        query = " "\n    '
    while 1:
        url = f'{model[model_id]}'
        headers = {'Content-Type': 'application/json'}
        if 'api' in model[model_id]:
            headers['Authorization'] = f"Bearer {model[model_id]['api']}"
        if not thinking:
            query = query + ' /no_think'
        massage = [{'role': 'system', 'content': system_prompt}] + history + [{'role': 'user', 'content': query}]
        data = {'model': model_id, 'messages': massage, 'max_output_length': 400, 'temperature': 0.7, 'TopP': 0.8, 'TopK': 20, 'MinP': 0}
        if model_id == 'Qwen3-30B':
            data['presence_penalty'] = 2
        if thinking:
            data['thinking'] = 'true'
        else:
            data['thinking'] = 'false'
        proxies = {}
        try:
            requests.packages.urllib3.disable_warnings()
            response = requests.request('POST', url, headers=headers, json=data, proxies=proxies, verify=True, timeout=100)
            if response.status_code == 200:
                if 'raw' in model[model_id]:
                    result = response.text
                else:
                    if 'sub' in model[model_id]:
                        data = response.content.decode('utf-8')
                        data = re.sub(model[model_id]['sub'], '', data)
                        data = eval(data)
                        result = data['result']
                    else:
                        result = response.json()
                    result = result['choices'][0]['message']['content']
                end_time = time.time()
                return result
            else:
                print('请求失败:', model_id, response.status_code)
        except requests.exceptions.RequestException as e:
            raise ConnectionError('Failed to connect to Local qwen3-4b server')

def pangu_7b(url, system_prompt, querys):
    system_template = '[unused9]系统：{system_prompt}[unused10]'
    query_template = '[unused9]用户：{query}[unused10][unused9]助手：'
    messages = ''
    if len(querys) == 1:
        messages = system_template.format(system_prompt=system_prompt) + query_template.format(query=querys[0]['content'])
    else:
        for query in querys:
            if query.get('role') == 'user':
                messages = messages + query_template.format(query=query['content'])
            elif query.get('role') == 'assistant':
                messages = messages + query.get('content')
        messages = system_template.format(system_prompt=system_prompt) + messages
    res = requests.post(url=url, json={'query': messages}, headers={'Content-Type': 'application/json'})
    if res.status_code == 200:
        return json.loads(res.text)['response'][0]
    else:
        raise ConnectionError('Failed to connect to Local pangu server')

def qwen3_8b(url, system_prompt, query):
    model_name = 'Qwen3-8B'
    r = requests.post(url=url, json={'model': model_name, 'messages': [{'role': 'system', 'content': [{'type': 'text', 'text': system_prompt}]}, {'role': 'user', 'content': [{'type': 'text', 'text': query[0]['content']}]}]}, headers={'Content-Type': 'application/json'})
    if r.status_code == 200:
        return json.loads(r.text)['choices'][0]['message']['content']
    else:
        raise ConnectionError('Failed to connect to Local pangu server')

def qwen3_32b(url, system_prompt, query):
    model_name = 'Qwen3-32B'
    messages = [{'role': 'system', 'content': system_prompt}, query[0]]
    payload = {'model': model_name, 'messages': messages}
    headers = {'Content-Type': 'application/json'}
    response = requests.request('POST', url, json=payload, headers=headers, verify=True)
    result = response.json()
    return result['choices'][0]['message']['content']

def pangu(url, system_prompt, querys):
    system_template = '[unused9]系统：{system_prompt}[unused10]'
    query_template = '[unused9]用户：{query}[unused10][unused9]助手：'
    messages = ''
    if len(querys) == 1:
        messages = system_template.format(system_prompt=system_prompt) + query_template.format(query=querys[0]['content'])
    else:
        for query in querys:
            if query.get('role') == 'user':
                messages = messages + query_template.format(query=query['content'])
            elif query.get('role') == 'assistant':
                messages = messages + query.get('content')
        messages = system_template.format(system_prompt=system_prompt) + messages
    res = requests.post(url=url, json={'query': messages}, headers={'Content-Type': 'application/json'})
    if res.status_code == 200:
        return json.loads(res.text)['response'][0]
    else:
        raise ConnectionError('Failed to connect to Local pangu server')

def pangu_72b(url, system_prompt, querys):
    system_template = '[unused9]系统：{system_prompt}[unused10]'
    query_template = '[unused9]用户：{query}[unused10][unused9]助手：'
    messages = ''
    if len(querys) == 1:
        messages = system_template.format(system_prompt=system_prompt) + query_template.format(query=querys[0]['content'])
    else:
        for query in querys:
            if query.get('role') == 'user':
                messages = messages + query_template.format(query=query['content'])
            elif query.get('role') == 'assistant':
                messages = messages + query.get('content')
        messages = system_template.format(system_prompt=system_prompt) + messages
    res = requests.post(url=url, json={'model': 'pangu-pro-moe-model', 'max_tokens': 65536, 'prompt': messages, 'top_p': 0.95, 'top_k': 50, 'temperature': 0.6}, headers={'Content-Type': 'application/json'})
    if res.status_code == 200:
        return json.loads(res.text)['choices'][0]['text']
    else:
        raise ConnectionError('Failed to connect to Local pangu server')

def mistral_small_3_2_24b(url, system_prompt, query):
    r = requests.post(url=url, json={'model': 'Mistral-Small-3.2-24B-Instruct-2506', 'messages': [{'role': 'system', 'content': system_prompt}, query[0]], 'temperature': 0.15, 'max_tokens': 100}, headers={'Content-Type': 'application/json'})
    if r.status_code == 200:
        return json.loads(r.text)['choices'][0]['message']['content']
    else:
        raise ConnectionError('Failed to connect to Local pangu server')

def qwen3_30b_a3_2507(url, system_prompt, query):
    model_name = 'Qwen3-30B-A3-2507'
    r = requests.post(url=url, json={'model': model_name, 'messages': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': query[0]['content']}]}, headers={'Content-Type': 'application/json'})
    if r.status_code == 200:
        return json.loads(r.text)['choices'][0]['message']['content']
    else:
        raise ConnectionError('Failed to connect to Local pangu server')
