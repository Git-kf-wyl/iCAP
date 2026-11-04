# Private iCAP Yellow business implementation. Do not publish.
import os
import pandas as pd
import requests
import json
import re
import time
import logger
import prompt
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from services.aisf.perception_plan.constants import BASE_DIR, BASE_DIR_OUTPUT
from services.aisf.thread_util import parse
url = '1'
model_name = '2'
is_think = False

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename, keep_default_na=False)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        expected_answer = row['Test answer']
        if 'APP' in df.columns:
            app = row['APP']
        else:
            app = ''
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'APP': app})
    return test_cases

def write_to_excel(filename, out_data, successCount, successesRate, average_Time, max_elapse_time, min_elapse_time):
    df1 = pd.DataFrame(out_data)
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elapse_time, 'Min_Elapse_Time': min_elapse_time, 'Prompt': prompt.SingleIntentIdentPrompt}
    df2 = pd.DataFrame(data)
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)
        df2.to_excel(writer, sheet_name='Test Result Summary', index=False)

def write_to_bad_case(filename, out_data):
    df1 = pd.DataFrame(out_data)
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)

def connect_model(data):
    content = data.get('Input')
    if not is_think:
        content += '\n/nothink'
    headers = {'Content-Type': 'application/json'}
    body = {'model': model_name, 'messages': [{'role': 'system', 'content': prompt.SingleIntentIdentPrompt}, {'role': 'user', 'content': content}], 'temperature': 0}
    start_time = time.time()
    response = requests.post(url, json=body, headers=headers)
    end_time = time.time()
    elapsed_time = end_time - start_time
    my_logger.info('花费了:' + str(elapsed_time) + '秒')
    message = json.loads(response.text)['choices'][0]['message']['content']
    my_logger.info(response.text)
    tokens = json.loads(response.text)['usage']
    return (message, elapsed_time, tokens)

def is_successful(LLM_answer, expected_answer):
    test_answer = expected_answer.get('Test answer')
    data = LLM_answer.replace('```', '')
    data = data.replace('json', '')
    test_answer = test_answer.replace('```', '')
    test_answer = test_answer.replace('json', '')
    try:
        data = json.loads(data)
        test_answer = json.loads(test_answer)
    except Exception as e:
        return (0, '字符串转化为JSON错误')
    score = 1
    reason = ''
    if len(test_answer) != len(data):
        return (0, 'Agent数量匹配错误')
    for test_answer_item, data_item in zip(test_answer, data):
        if test_answer_item['agent_name'] != data_item['agent_name']:
            return (0, 'LLM模型返回的agent_name与测试答案不一致')
        if test_answer_item['agent_name'] == 'LifeAssistantAgent' and test_answer_item['APP'] == '':
            continue
        if test_answer_item['APP'] != data_item['APP']:
            return (0, 'LLM模型返回的APP与测试答案不一致')
    return (1, 'success')

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
    if '</think>' in message_body:
        parts = message_body.split('</think>', 1)
    else:
        parts = message_body
    if len(parts) == 2:
        answer_content = extract_clean_text(parts[1])
    else:
        answer_content = extract_clean_text(message_body)
    return answer_content

def write_to_summary(file_path, data):
    current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    think = 'think'
    if is_think == False:
        think = 'nothink'
    try:
        file_exists = os.path.isfile(file_path)
        if file_exists:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        file_exists = os.path.isfile(file_path)
        with open(file_path, 'a', encoding='utf-8') as f:
            if not file_exists or len(lines) == 0:
                f.write('date\t\t\t\t\t\t\t\tModelName\t\t\t\t\t\t\t\tIsThink\t\t\t\t\t\t\t\tFoodAgtSucRate\t\t\t\t\t\t\t\tShopAgtSucRate\t\t\t\t\t\t\t\tTravelAgtSucRate\t\t\t\t\t\t\t\tFuncCallSucRate\t\t\t\t\t\t\t\tRouteSucRate\t\t\t\t\t\t\t\tMultitaskSucRate')
                f.write(f"\n\n{current_date}\t\t\t\t\t\t\t\t{data['ModelName']}\t\t\t\t\t\t\t\t{think}\t\t\t\t\t\t\t\t{data['FoodAgtSucRate']}\t\t\t\t\t\t\t\t{data['ShopAgtSucRate']}\t\t\t\t\t\t\t\t{data['TravelAgtSucRate']}\t\t\t\t\t\t\t\t{data['FuncCallSucRate']}\t\t\t\t\t\t\t\t{data['RouteSucRate']}\t\t\t\t\t\t\t\t{data['MultitaskSucRate']}")
    except Exception as e:
        print(f'写入文件出错:{str(e)}')
