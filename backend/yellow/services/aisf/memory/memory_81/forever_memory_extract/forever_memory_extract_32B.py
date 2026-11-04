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
import prompt_forever_memory_extract as prompt
from services.aisf.memory.constants import BASE_DIR_OUTPUT, BASE_DIR
from services.aisf.thread_util import parse
url = 'http://127.0.0.1:1/unconfigured'
model_name = 'Qwen3-32B'
is_think = False

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append({'ID': row['ID'], 'user_input': row['UserInput'], 'hist': row['Hist'], 'test_answer': row['TestAnswer']})
    return test_cases

def extract_clean_text(text):
    """去除 HTML 标签并清理空白字符"""
    text = re.sub('<[^>]+>', '', text)
    text = re.sub('\\s+', ' ', text).strip()
    return text

def connect_model(content, sysprompt):
    if not is_think:
        content = f'{content}/nothink'
    headers = {'Content-Type': 'application/json'}
    body = {'model': model_name, 'messages': [{'role': 'system', 'content': sysprompt}, {'role': 'user', 'content': content}], 'temperature': 0}
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

def write_to_excel(filename, out_data, successCount, successesRate, average_Time, max_elaspse_time, min_elaspse_time):
    df1 = pd.DataFrame(out_data)
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elaspse_time, 'Min_Elapse_Time': min_elaspse_time, 'PROMPT': prompt.FOREVER_PROMPT}
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

def get_model_content(hist, user_input):
    user_input = user_input.replace("'", '"')
    hist = hist.replace("'", '"')
    return f'\n#### 用户输入\n{user_input}\n#### 历史数据\n{hist}'

def distinguish_format(input_str):
    try:
        if input_str.startswith('keep['):
            return 'keepOp'
        data = json.loads(input_str)
        if isinstance(data, list):
            return 'deleteOp'
        else:
            return 'addOp'
    except json.JSONDecodeError:
        return 'addOp'

def is_successful(llmoutput, answer):
    my_logger.info(f"{'-' * 20} Checking LLMOutput {'-' * 20}")
    answer = answer.replace('，', ',')
    answer = answer.strip()
    operation = distinguish_format(answer)
    if operation == 'deleteOp':
        if llmoutput != answer:
            return {'满意度': '不满意', '评测依据': 'delete操作不正确'}
    elif operation == 'addOp':
        if answer not in llmoutput:
            return {'满意度': '不满意', '评测依据': f'{answer} 不在模型输出'}
    else:
        answer = answer[4:]
        if llmoutput != answer:
            return {'满意度': '不满意', '评测依据': 'Keep操作不正确'}
    return {'满意度': '非常满意', '评测依据': '模型回答正确'}
