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
import prompt_attribute as prompt
from services.aisf.memory.constants import BASE_DIR_OUTPUT, BASE_DIR
from services.aisf.thread_util import parse
url = 'http://127.0.0.1:1/unconfigured'
model_name = 'Qwen3-32B'
is_think = False

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        test_cases.append({'ID': case_id, 'Input': input_data, 'entity': row['entity'], 'TestAnswer': row['TestAnswer']})
    return test_cases

def extract_clean_text(text):
    """去除 HTML 标签并清理空白字符"""
    text = re.sub('<[^>]+>', '', text)
    text = re.sub('\\s+', ' ', text).strip()
    return text

def connect_model(content):
    headers = {'Content-Type': 'application/json'}
    body = {'model': model_name, 'messages': [{'role': 'system', 'content': prompt.ATTRIBUTES_EXTRACT_PROMPT3}, {'role': 'user', 'content': content + '\n\n/nothink'}], 'temperature': 0}
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
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elapse_time, 'Min_Elapse_Time': min_elapse_time, 'Prompt': prompt.ATTRIBUTES_EXTRACT_PROMPT3}
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
    try:
        LLM_answer = json.loads(LLM_answer)
        expected_answer = json.loads(expected_answer)
    except Exception as e:
        my_logger.error('字符串转化为JSON错误--' + str(e))
        return (0, '模型输出格式有误')
    if len(LLM_answer) != len(expected_answer):
        return (0, 'LLM萃取属性错误')
    for key, value in expected_answer.items():
        if key not in LLM_answer:
            return (0, 'LLM模型未萃取出 ' + key + '属性')
        if LLM_answer[key] != value:
            return (0, '属性萃取错误')
    return (1, 'success')

def parse_think_response_clean(message_body):
    """
    解析消息体，分割出 think 内容和回答内容（纯文本）
    返回: (think_content, answer_content)
          如果没有 </think>，则 think_content=None
    """
    my_logger.info(message_body)
    if '</think>' in message_body:
        parts = message_body.split('</think>', 1)
    else:
        parts = message_body
    if len(parts) == 2:
        answer_content = extract_clean_text(parts[1])
    else:
        answer_content = extract_clean_text(message_body)
    return answer_content

def getAnswer(data):
    data = data.replace('```', '')
    data = data.replace('json', '')
    return data

def getEntityList(entity_name):
    my_logger.info(f'Entity: {entity_name}')
    df = pd.read_csv(BASE_DIR + 'memoryNew/extractAttribute/attr_test.csv', encoding='utf-8')
    filtered_df = df[df['entity'] == entity_name]
    result = filtered_df[['attribute_level_1', 'attribute_level_2']]
    if not result.empty:
        for idx, row in result.iterrows():
            if pd.isna(row['attribute_level_1']):
                result = '[' + row['attribute_level_2'] + ']'
            else:
                result = '["' + row['attribute_level_1'] + '",' + row['attribute_level_2'] + ']'
            my_logger.info(result)
            return result
    else:
        my_logger.info('Not classified')
        return 'unclassified'

def get_model_content(input, entity_name):
    content = ''
    entity_list = getEntityList(entity_name)
    if entity_list != 'unclassified':
        content = '需提取的字段列表:' + entity_list + ' '
    content += '待提取文本:' + input.replace("'", '"')
    return content
