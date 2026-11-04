# Private iCAP Yellow business implementation. Do not publish.
import json
import time
from datetime import datetime
import pendulum
import re
import pandas as pd
import requests
import os
import logger
import prompt_travel_time as prompt
from services.aisf.memory.constants import BASE_DIR_OUTPUT, BASE_DIR
from services.aisf.thread_util import parse
url = 'http://9.15.87.199:8083/v1/chat/completions'
model_name = 'Qwen3-8B'
is_think = False

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        test_cases.append({'ID': case_id, 'input_departureTime': row['input_departureTime'], 'answer_departureTime': row['answer_departureTime']})
    return test_cases

def extract_clean_text(text):
    """去除 HTML 标签并清理空白字符"""
    text = re.sub('<[^>]+>', '', text)
    text = re.sub('\\s+', ' ', text).strip()
    return text

def connect_model(data):
    content = str(data)
    if not is_think:
        content += '/nothink'
    headers = {'Content-Type': 'application/json'}
    body = {'model': model_name, 'messages': [{'role': 'system', 'content': prompt.TIME_PROMPT}, {'role': 'user', 'content': content}], 'temperature': 0}
    my_logger.info(f'Content: {content}')
    start_time = time.time()
    response = requests.post(url, json=body, headers=headers)
    end_time = time.time()
    elapsed_time = end_time - start_time
    my_logger.info('花费了:' + str(elapsed_time) + '秒')
    message = json.loads(response.text)['choices'][0]['message']['content']
    my_logger.info(response.text)
    tokens = json.loads(response.text)['usage']
    my_logger.info('tokens为:' + str(tokens))
    return (message, elapsed_time, tokens)

def write_to_excel(filename, out_data, successCount, successesRate, average_Time, max_elapse_time, min_elapse_time):
    df1 = pd.DataFrame(out_data)
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elapse_time, 'Min_Elapse_Time': min_elapse_time, 'Prompt': prompt.TIME_PROMPT}
    df2 = pd.DataFrame(data)
    folder_path = os.path.dirname(filename)
    my_logger.info(f'完整路径: {filename}')
    my_logger.info(f'文件夹路径: {folder_path}')
    if folder_path:
        os.makedirs(folder_path, exist_ok=True)
        my_logger.info(f'确保文件夹存在: {folder_path}')
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)
        df2.to_excel(writer, sheet_name='Test Result Summary', index=False)

def is_successful(LLM_answer, expected_answer):
    my_logger.info(f"{'-' * 20} Checking LLMOutput {'-' * 20}")
    my_logger.info(f'LLMOutput: {LLM_answer}')
    my_logger.info(f'Answer: {expected_answer}')
    expected_answer = expected_answer.replace('，', ',')
    try:
        LLM_answer = json.loads(LLM_answer)
        expected_answer = json.loads(expected_answer)
    except Exception as e:
        my_logger.error('字符串转化为JSON错误--' + str(e))
        return (0, '模型输出格式有误')
    if len(LLM_answer) != len(expected_answer):
        return (0, 'LLM萃取错误')
    score = 1
    error_reason = ''
    for key, value in expected_answer.items():
        if key not in LLM_answer:
            score = 0
            error_reason = key + '未萃取出 '
        if LLM_answer[key] != value:
            score = 0
            error_reason = key + '萃取错误 '
    if score:
        return (score, 'success')
    else:
        return (score, error_reason)
