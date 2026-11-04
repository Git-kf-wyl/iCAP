# Private iCAP Yellow business implementation. Do not publish.
import os
import pandas as pd
import requests
import json
import re
import time
import prompt
from datetime import datetime
from logger import Logger
from services.aisf.function_call.constants import BASE_DIR, BASE_DIR_OUTPUT
from services.aisf.thread_util import parse
task_id = '123'
url = 'http://127.0.0.1:1/unconfigured'
model_name = 'Qwen3-32B'
test_name = 'function_call_test'
timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
log_name = f'{test_name}_{timestamp_str}'
today = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
week_day_cn = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append({'ID': row['ID'], 'Input': row['Input'], 'expect_agent_name': row['expect-agent_name'], 'expect-name': row['expect-name'], 'expect-keywords1': row['expect-keywords1'] if pd.notna(row['expect-keywords1']) else None, 'expect-keywords2': row['expect-keywords2'] if pd.notna(row['expect-keywords2']) else None, 'old_ans': row['OldAns']})
    return test_cases
successCount = 0
surroundSearch_case_success_num = 0
onlineSearch_case_success_num = 0
query_weather_case_success_num = 0
queryWebBrowser_case_success_num = 0
wiki_search_case_success_num = 0
ai_search_case_success_num = 0
all_count = 0
surroundSearch_case_total_num = 0
onlineSearch_case_total_num = 0
query_weather_case_total_num = 0
queryWebBrowser_case_total_num = 0
wiki_search_case_total_num = 0
ai_search_case_total_num = 0
successRate = 0
onlineSearchsuccessRate = 0
query_weathersuccessRate = 0
queryWebBrowsersuccessRate = 0
surroundSearchsuccessRate = 0
wiki_searchsuccessRate = 0
ai_searchsuccessRate = 0

def write_to_excel(filename, out_data):
    df1 = pd.DataFrame(out_data)
    successesRate = f'{successRate}%'
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): f'{successRate}%', f'onlineSearch-{onlineSearch_case_success_num}/{onlineSearch_case_total_num}': f'{onlineSearchsuccessRate}%', f'query_weather-{query_weather_case_success_num}/{query_weather_case_total_num}': f'{query_weathersuccessRate}%', f'queryWebBrowser-{queryWebBrowser_case_success_num}/{queryWebBrowser_case_total_num}': f'{queryWebBrowsersuccessRate}%', f'surroundSearch-{surroundSearch_case_success_num}/{surroundSearch_case_total_num}': f'{surroundSearchsuccessRate}%', f'wiki_search-{wiki_search_case_success_num}/{wiki_search_case_total_num}': f'{wiki_searchsuccessRate}%', f'ai_search-{ai_search_case_success_num}/{ai_search_case_total_num}': f'{ai_searchsuccessRate}%', 'Prompt': prompt.FC_PROMPT}
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

def step_single(model_url, messages, thinks, times, prompt_token, comp_token):
    payload = {'model': model_name, 'temperature': 0, 'messages': messages}
    headers = {'Content-Type': 'application/json'}
    tick = time.time()
    response = requests.request('POST', model_url, json=payload, headers=headers, verify=True)
    tock = time.time()
    cost = tock - tick
    response_text = json.loads(response.text)
    think = response_text['choices'][0]['message']['content']
    think = re.sub('<think>.*?</think>', '', think, flags=re.DOTALL)
    think = re.sub('^<tool_call>|</tool_call>$', '', think, flags=re.MULTILINE)
    think = think.replace('\n', '')
    think = think.replace(' ', '')
    p_token = response_text['usage']['prompt_tokens']
    c_token = response_text['usage']['completion_tokens']
    thinks.append(think)
    times.append(cost)
    prompt_token.append(p_token)
    comp_token.append(c_token)
    return think

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
