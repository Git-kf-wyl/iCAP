# Private iCAP Yellow business implementation. Do not publish.
import sys
from pathlib import Path
import requests
import pandas as pd
from system_prompt import skill_select_sys_prompt as sys_prompt
from health_skill_description import skill_description
import json
import re
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import warnings
warnings.filterwarnings('ignore')

def qwen_32b(messages, url, model_name, temp):
    payload = {'model': model_name, 'messages': messages, 'temperature': temp, 'chat_template_kwargs': {'enable_thinking': False}}
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, json=payload, headers=headers, verify=True, timeout=120)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
        cleaned = re.sub('^```(?:json|python)?\\s*|\\s*```$', '', content.strip(), flags=re.MULTILINE)
        return cleaned
    except Exception as e:
        print(f'请求失败: {e}')
        try:
            return response.text
        except Exception:
            return str(e)

def parse_LLM_output(LLM_output):
    """
    解析LLM输出
    """
    try:
        result = ast.literal_eval(LLM_output.strip())
        if isinstance(result, list) or isinstance(result, dict):
            return result
        else:
            print(f'model answer type wrong: {result}')
            return None
    except Exception as e:
        print(f'model answer format wrong: {e}')
        return None

def judge(A_evaluate, A_star):
    try:
        if A_evaluate == A_star:
            return True
        elif len(A_evaluate) == len(A_star):
            intents_num = len(A_evaluate)
            for i in range(intents_num):
                A_evaluate_intent, A_star_intent = (A_evaluate[i], A_star[i])
                A_evaluate_intent_name = A_evaluate_intent['skill_name']
                A_evaluate_intent_param = A_evaluate_intent['depends_on']
                A_star_intent_name = A_star_intent['skill_name']
                A_star_intent_param = A_star_intent['depends_on']
                if A_evaluate_intent_name != A_star_intent_name:
                    return False
                if A_evaluate_intent_param != A_star_intent_param:
                    return False
            return True
        else:
            return False
    except Exception as e:
        print(f'judge错误: {e}')
        return False

def build_history(row):
    history = []
    for i in range(1, 100):
        q_col = f'query{i}'
        a_col = f'answer{i}'
        if q_col in row and pd.notna(row[q_col]):
            history.append({'role': 'user', 'content': str(row[q_col])})
        if a_col in row and pd.notna(row[a_col]):
            history.append({'role': 'assistant', 'content': str(row[a_col])})
    return history

def build_messages(cur_query, history, skill_description):
    messages = [{'role': 'system', 'content': sys_prompt + '\n\n# 可用助手描述\n{{skill_description}}'.replace('{{skill_description}}', skill_description)}]
    messages.extend(history)
    messages.append({'role': 'user', 'content': '# 用户输入\n{{user_input}}'.replace('{{user_input}}', str(cur_query))})
    return messages

def clean_result(parsed_result, fallback_skill_name):
    if not isinstance(parsed_result, list):
        return []
    return [each for each in parsed_result if isinstance(each, dict) and each.get('skill_name') != fallback_skill_name]

def parse_expected_output(value):
    try:
        if pd.isna(value):
            return []
        return ast.literal_eval(str(value))
    except Exception as e:
        print(f'expected_output解析失败: {e}, value={value}')
        return []

def process_one_sample(index, row, url, model_name, temp):
    """
    一个样本内部串行：
    1. 请求A通道
    2. 请求B通道

    多个样本之间由线程池并行。
    """
    try:
        cur_query = row['cur_query']
        history = build_history(row)
        print(f'***********开始处理第 {index} 条**************')
        print(f'用户问题：{cur_query}')
        messages = build_messages(cur_query=cur_query, history=history, skill_description=skill_description)
        result = qwen_32b(messages, url, model_name, temp)
        result_parse = parse_LLM_output(result)
        expected_output = parse_expected_output(row['expected_output'])
        is_right = '1' if judge(result_parse, expected_output) else '0'
        print(f'第 {index} 条处理完成')
        print('输出结果：', result_parse)
        return {'index': index, 'messages': json.dumps(messages, ensure_ascii=False), 'result': result_parse, 'is_right': is_right, 'error': ''}
    except Exception as e:
        error_msg = traceback.format_exc()
        print(f'第 {index} 条处理失败: {e}')
        print(error_msg)
        return {'index': index, 'messages': '', 'result': '', 'is_right': '0', 'error': error_msg}
