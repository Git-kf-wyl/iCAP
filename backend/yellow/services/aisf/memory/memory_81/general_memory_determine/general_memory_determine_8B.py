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
import prompt_general_memory_determine as prompt
from services.aisf.memory.constants import BASE_DIR_OUTPUT, BASE_DIR
from services.aisf.thread_util import parse
url = 'http://127.0.0.1:1/unconfigured'
model_name = 'Qwen3-32B'
is_think = False

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append({'ID': row['ID'], 'UserInput': row['UserInput'], 'hist': row['hist']})
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
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elaspse_time, 'Min_Elapse_Time': min_elaspse_time, 'PROMPT': prompt.MEMORY_DETERMINE_PROMPT}
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

def get_model_content(input, user_input):
    input = input.replace("'", '"')
    return f'\n用户请求:\n{user_input}\n用户偏好:\n{input}'

def is_successful(llmoutput, answer):
    my_logger.info(f"{'-' * 20} Checking LLMOutput {'-' * 20}")
    answer = answer.replace('，', ',')
    answer_values = [a.strip() for a in answer.split(',') if a.strip()]
    if isinstance(llmoutput, str):
        llmoutput = llmoutput.strip()
        try:
            parsed_output = json.loads(llmoutput)
            if not isinstance(parsed_output, dict):
                return {'满意度': '不满意', '评测依据': 'LLM输出解析后不是字典类型'}
            llmoutput_dict = parsed_output
        except json.JSONDecodeError:
            return {'满意度': '不满意', '评测依据': 'LLM输出不是合法的JSON格式'}
    elif isinstance(llmoutput, dict):
        llmoutput_dict = llmoutput
    else:
        return {'满意度': '不满意', '评测依据': 'LLM输出既不是字符串也不是字典'}
    output_values = [str(v).strip() for v in llmoutput_dict.values() if v is not None]
    missing_values = []
    for val in answer_values:
        if not any((val in out_val for out_val in output_values)):
            missing_values.append(val)
    if missing_values:
        return {'满意度': '不满意', '评测依据': f'模型缺少以下关键信息（未在任何输出值中找到包含）：{missing_values}'}
    placeholder_pattern = '^属性\\d+$'
    suspicious_keys = [k for k in llmoutput_dict.keys() if re.fullmatch(placeholder_pattern, str(k).strip())]
    if suspicious_keys:
        return {'满意度': '不满意', '评测依据': f'模型使用了占位符键名：{suspicious_keys}，应使用具体语义键名'}
    return {'满意度': '非常满意', '评测依据': '模型回答包含所有关键字，且未使用占位符键名'}
