# Private iCAP Yellow business implementation. Do not publish.
"""
处理初始数据的脚本
初始数据目录topic_input
出后后的数据目录topic_output
"""
import json
import time
from datetime import datetime
import pendulum
import re
import pandas as pd
import requests
import os
import logger
import prompt_get_city_name as prompt
from services.aisf.memory.constants import BASE_DIR_OUTPUT, BASE_DIR
from services.aisf.thread_util import parse
url = 'http://127.0.0.1:1/unconfigured'
model_name = 'Qwen3-32B'
is_think = False

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename, keep_default_na=False)
    for index, row in df.iterrows():
        case_id = row['ID']
        user_input = row['Input']
        test_answer = row['TestAnswer']
        test_cases.append({'ID': case_id, 'Input': user_input, 'Test answer': test_answer})
    return test_cases

def write_to_excel(filename, out_data, successCount, successesRate, average_Time, max_elapse_time, min_elapse_time):
    df1 = pd.DataFrame(out_data)
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elapse_time, 'Min_Elapse_Time': min_elapse_time, 'Prompt': prompt.GET_CITY_NAME}
    df2 = pd.DataFrame(data)
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)
        df2.to_excel(writer, sheet_name='Test Result Summary', index=False)

def write_to_bad_case(filename, out_data):
    df1 = pd.DataFrame(out_data)
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)

def is_successful(LLM_answer, expected_answer):
    try:
        if LLM_answer == expected_answer:
            return (1, 'success')
        else:
            return (0, '城市名称提取错误')
    except Exception as e:
        my_logger.error('字符串转化为JSON错误--' + str(e))
        return (0, '模型输出有误')

def connect_model(data):
    content = str(data)
    if not is_think:
        content += '/nothink'
    headers = {'Content-Type': 'application/json'}
    body = {'model': model_name, 'messages': [{'role': 'system', 'content': prompt.GET_CITY_NAME}, {'role': 'user', 'content': content}], 'temperature': 0}
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

def extract_clean_text(text):
    """去除 HTML 标签并清理空白字符"""
    text = re.sub('<[^>]+>', '', text)
    text = re.sub('\\s+', ' ', text).strip()
    return text

def parse_think_response_clean(message_body):
    """
    解析消息体，分割出 think 内容和回答内容（纯文本）
    返回: (think_content, answer_content)
          如果没有 </think>，则 think_content=None
    """
    if '</think>' in message_body:
        parts = message_body.split('</think>', 1)
    else:
        parts = message_body
    if len(parts) == 2:
        answer_content = extract_clean_text(parts[1])
    else:
        answer_content = extract_clean_text(message_body)
    return answer_content
