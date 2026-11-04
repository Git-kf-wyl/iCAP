# Private iCAP Yellow business implementation. Do not publish.
import time
from datetime import datetime
import uuid
import random
import string
import re
from json import JSONDecodeError
import pandas as pd
import requests
import os
import pendulum
import json
from services.aisf.clarify.Trip.Version import logger
from services.aisf.clarify.Trip.Version import hotel_examine_prompt as answer_prompt
from services.aisf.clarify.Trip.Version import prompt as testedPrompt
from services.aisf.clarify.Trip.Version.constants import BASE_DIR, CURRENT_DIR
from services.aisf.thread_util import parse
from services.aisf.clarify.constants import CLARIFY_BASE_DIR_OUTPUT
url = 'http://127.0.0.1:1/unconfigured'
model_name = 'Qwen3-32B'

def getTime():
    years = pendulum.now().format('YYYY-MM-DD')
    weeks = pendulum.now().format('dddd')
    weekdays = {'Monday': '星期一', 'Tuesday': '星期二', 'Wednesday': '星期三', 'Thursday': '星期四', 'Friday': '星期五', 'Saturday': '星期六', 'Sunday': '星期天'}
    return years + ' ' + weekdays[weeks]

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        expected_answer = row['TestAnswer']
        travel_prompt = row['Use Prompt']
        current_date = row['当前日期']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'Use Prompt': travel_prompt, 'Current date': current_date})
    return test_cases

def write_to_excel(filename, out_data, successCount, successesRate, usePrompt, average_Time, max_elaspse_time, min_elaspse_time):
    df1 = pd.DataFrame(out_data)
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elaspse_time, 'Min_Elapse_Time': min_elaspse_time, '参数澄清Prompt': usePrompt}
    df2 = pd.DataFrame(data)
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)
        df2.to_excel(writer, sheet_name='Test Result Summary', index=False)

def connectModel(clarifyInput):
    headers = {'Content-Type': 'application/json'}
    body = {'model': model_name, 'messages': clarifyInput, 'temperature': 0}
    start_time = time.time()
    response = requests.post(url, json=body, headers=headers)
    end_time = time.time()
    elapsed_time = end_time - start_time
    my_logger.info('花费了:' + str(elapsed_time) + '秒')
    tokens = json.loads(response.text)['usage']
    my_logger.info('tokens为:' + str(tokens))
    message = json.loads(response.text)['choices'][0]['message']['content']
    return (message, elapsed_time, tokens)

def extract_contents_from_strings(text_list):
    """
    从字符串列表中提取 "content": "..." 的内容，并拼接成字符串

    Args:
        text_list (list): 包含 "content": "..." 的字符串列表

    Returns:
        str: 所有提取到的内容拼接成的字符串
    """
    if not isinstance(text_list, list):
        raise ValueError('输入必须是一个字符串列表')
    extracted_contents = []
    pattern = '"content"\\s*:\\s*"([^"]*)"'
    for text in text_list:
        if not isinstance(text, str):
            continue
        newText = text.encode().decode('utf-8')
        matches = re.findall(pattern, newText)
        extracted_contents.extend(matches)
    return ''.join(extracted_contents).encode().decode('utf-8')

def safe_decode(chunk: bytes, encodings: tuple=('utf-8', 'gbk', 'latin1')) -> str:
    """支持多编码自动检测的安全解码"""
    for encoding in encodings:
        try:
            return chunk.decode(encoding)
        except UnicodeDecodeError:
            continue
    return chunk.decode('utf-8', errors='replace')

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
    my_logger.info(message_body)
    parts = message_body.split('</think>', 1)
    if len(parts) == 2:
        answer_content = parts[1]
    else:
        answer_content = extract_clean_text(message_body)
    return answer_content

def generate_uuid(version: int=4) -> str:
    if version == 1:
        return str(uuid.uuid1())
    elif version == 4:
        return str(uuid.uuid4())
    else:
        raise ValueError('不支持的UUID版本，仅支持版本1或4')

def generate_event_time_stamp():
    current_utc_time = datetime.utcnow()
    iso_format_time = current_utc_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    return iso_format_time

def getClarifyAnswer(data):
    data = data.replace('```', '')
    data = data.replace('json', '')
    try:
        res = json.loads(data)
    except JSONDecodeError as e:
        my_logger.error('被测模型返回结果' + data + '非标准JSON格式')
        res = {'Type': 'result', 'Data': '', 'Desc': '被测模型返回结果' + data + '非标准JSON格式'}
    return json.dumps(res, ensure_ascii=False)

def getAnswer(data):
    data = data.replace('```', '')
    data = data.replace('json', '')
    try:
        result = json.loads(data)
    except JSONDecodeError as e:
        my_logger.error('问答助手返回结果' + data + '非标准JSON格式')
        result = {'问答回应': '问答助手返回结果' + data + '非标准JSON格式'}
    return json.dumps(result, ensure_ascii=False)
    return result

def getScore(data):
    data = data.replace('```', '')
    data = data.replace('json', '')
    data = data.replace('[', '')
    data = data.replace(']', '')
    res = json.loads(data)
    return (str(res['得分']), str(res['原因']))

def save_success_rate(file_path, success_rate):
    df1 = pd.DataFrame(success_rate)
    with pd.ExcelWriter(file_path) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)

def is_successful(TestAnaswer, LLMAnswer):
    try:
        TestAnaswer = TestAnaswer.replace("'", '"')
        LLMAnswer = LLMAnswer.replace("'", '"')
        TestAnaswer = json.loads(TestAnaswer)
        LLMAnswer = json.loads(LLMAnswer)
    except Exception as e:
        my_logger.error('字符串转化为JSON错误' + str(e))
        return (0, '模型输出格式有误')
    date_keys = {'dDate1', 'checkOutDate'}
    for key in TestAnaswer:
        if key not in date_keys:
            if TestAnaswer[key] not in LLMAnswer[key] and LLMAnswer[key] not in TestAnaswer[key]:
                return (0, '模型提取' + key + '参数错误')
    return (1, '模型提取参数正确')
