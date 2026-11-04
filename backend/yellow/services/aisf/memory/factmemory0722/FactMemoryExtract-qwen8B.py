# Private iCAP Yellow business implementation. Do not publish.
import os
import pandas as pd
import requests
import json
import re
import time
import FactMemPrompt
from datetime import datetime
from logger import Logger
from services.aisf.memory.constants import BASE_DIR_OUTPUT, BASE_DIR
from services.aisf.thread_util import parse
url = '1'
model_name = '2'

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
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): f'{successRate}%', 'Prompt': FactMemPrompt.FACT_DETERMINE_PROMPT}
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
        match = parse_think_response_clean(response_text['choices'][0]['message']['content'])
        logger.info(f'######match:{match}')
        count = match.count('"')
        if count == 0:
            match = f'"{match}"'
        if match == '"[]"':
            match = '[]'
        logger.info(f'######match:{match}')
    except Exception as e:
        mtr['error'] = str(e)
        return (mtr, matchs)
    return (mtr, match, cost)

def is_sucessful(LLM_answer, expected_answer):
    logger.info('START CHECK')
    logger.info(f'expected_answer = {expected_answer}')
    logger.info(f'LLM_answer = {LLM_answer}')
    if str(expected_answer) not in str(LLM_answer):
        logger.info(f'{expected_answer} is not in {LLM_answer}')
        return False
    logger.info(f'{expected_answer} is in {LLM_answer}')
    return True

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
    parts = message_body.split('</think>', 1)
    if len(parts) == 2:
        answer_content = extract_clean_text(parts[1])
    else:
        answer_content = extract_clean_text(message_body)
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
