# Private iCAP Yellow business implementation. Do not publish.
import os
import pandas as pd
import requests
import json
import re
import time
import base64
import ThemeMemPrompt1015
from datetime import datetime
from logger import Logger
from services.aisf.memory.constants import BASE_DIR_OUTPUT, BASE_DIR
from services.aisf.thread_util import parse
url = 'http://9.15.87.199:8083/v1/chat/completions'
model_name = 'Qwen3-8B'

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append({'ID': row['ID'], 'Input': row['Input'], '历史记录': row['历史记录'], 'Test answer': row['Test answer']})
    return test_cases
successCount = 0
all_count = 0
successRate = 0

def write_to_excel(filename, out_data):
    df1 = pd.DataFrame(out_data)
    successesRate = f'{successRate}%'
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): f'{successRate}%', 'Prompt': ThemeMemPrompt1015.DETERMINE_PROMPT1015}
    df2 = pd.DataFrame(data)
    folder_path = os.path.dirname(filename)
    logger.info(f'完整路径: {filename}')
    logger.info(f'文件夹路径: {folder_path}')
    if folder_path:
        os.makedirs(folder_path, exist_ok=True)
        logger.info(f'确保文件夹存在: {folder_path}')
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)
        df2.to_excel(writer, sheet_name='Test Result Summary', index=False)

def connect_model(messages):
    mtr = {}
    raw_chunk_list = []
    token_cnt = 0
    content_buffer = []
    matchs = []
    payload = {'model': model_name, 'temperature': 0, 'messages': messages}
    headers = {'Content-Type': 'application/json'}
    try:
        logger.info(f'payload = {payload}')
        tick = time.time()
        response = requests.request('POST', url, json=payload, headers=headers, verify=True)
        tock = time.time()
        cost = tock - tick
        response_text = json.loads(response.text)
        logger.info(f'response_text = {response_text}')
        match = 'none'
        match = response_text['choices'][0]['message']['content']
        logger.info(f'######match:{match}')
    except Exception as e:
        mtr['error'] = str(e)
        return (mtr, matchs)
    return (mtr, match, cost)
import json

def normalize_value(val):
    """标准化值：将字符串数字转为数字，其他保持不变"""
    if isinstance(val, str):
        val = val.strip()
        if val.isdigit():
            return int(val)
        try:
            if '.' in val and val.replace('.', '', 1).isdigit():
                return float(val)
            return val
        except:
            return val
    return val

def is_successful(LLM_answer, expected_answer):
    try:
        expected_answer = expected_answer.replace("'", '"')
        LLM_answer = json.loads(LLM_answer)
        expected_answer = json.loads(expected_answer)
    except Exception as e:
        logger.error('字符串转化为JSON错误--' + str(e))
        return (0, '模型输出格式有误')
    if len(LLM_answer) != len(expected_answer):
        return (0, '长度不一样')
    score = 1
    error_reason = ''
    for key, expected_value in expected_answer.items():
        if key not in LLM_answer:
            score = 0
            error_reason = f'{key}不在LLM Output'
            break
        llm_value = LLM_answer[key]
        if normalize_value(llm_value) != normalize_value(expected_value):
            score = 0
            error_reason = f'{key}, LLMOutput: llm_value VS Answer expected_value'
            break
    if score:
        return (score, 'success')
    else:
        return (score, error_reason)

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
        matches = re.findall(pattern, text)
        extracted_contents.extend(matches)
    return ''.join(extracted_contents)

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
    logger.info(message_body)
    if 'contents' not in message_body.keys():
        return ''
    text = message_body['contents']
    logger.info('$$$$$$$$$$$$$$')
    logger.info(message_body)
    logger.info('###############')
    logger.info(isinstance(message_body, dict))
    logger.info('************************')
    logger.info(text)
    parts = text.split('</think>', 1)
    if len(parts) == 2:
        think_content = extract_clean_text(parts[0])
        answer_content = extract_clean_text(parts[1])
    else:
        think_content = None
        answer_content = extract_clean_text(text)
    return answer_content

def safe_decode(chunk: bytes, encodings: tuple=('utf-8', 'gbk', 'latin1')) -> str:
    """支持多编码自动检测的安全解码"""
    for encoding in encodings:
        try:
            return chunk.decode(encoding)
        except UnicodeDecodeError:
            continue
    return chunk.decode('utf-8', errors='replace')

def write_to_summary(file_path, data):
    current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        file_exists = os.path.isfile(file_path)
        if file_exists:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        file_exists = os.path.isfile(file_path)
        with open(file_path, 'a', encoding='utf-8') as f:
            if not file_exists or len(lines) == 0:
                f.write('date\t\t\t\t\t\t\t\tModelName\t\t\t\t\t\t\t\tFoodAgtSucRate\t\t\t\t\t\t\t\tShopAgtSucRate\t\t\t\t\t\t\t\tTravelAgtSucRate\t\t\t\t\t\t\t\tFuncCallSucRate')
            f.write(f"\n\n{current_date}\t\t\t\t\t\t\t\t{data['ModelName']}\t\t\t\t\t\t\t\t{data['FoodAgtSucRate']}\t\t\t\t\t\t\t\t{data['ShopAgtSucRate']}\t\t\t\t\t\t\t\t{data['TravelAgtSucRate']}\t\t\t\t\t\t\t\t{data['FuncCallSucRate']}")
    except Exception as e:
        logger.info(f'写入文件出错:{str(e)}')
