# Private iCAP Yellow business implementation. Do not publish.
import json
import time
from datetime import datetime
import pendulum
import re
import pandas as pd
import requests
import os
from services.aisf.clarify.ShopFood_normal.Version_KnowledgeBase import logger
from services.aisf.clarify.ShopFood_normal.Version_KnowledgeBase import prompt as tested_Prompt
from services.aisf.clarify.ShopFood_normal.Version_KnowledgeBase import prompt_paraClarify_0816 as prompt_paraClarify
from services.aisf.clarify.ShopFood_normal.Version_KnowledgeBase import getContext
from services.aisf.clarify.ShopFood_normal.Version_KnowledgeBase.constants import BASE_DIR, CURRENT_DIR
from services.aisf.thread_util import parse
from services.aisf.clarify.constants import CLARIFY_BASE_DIR_OUTPUT
url = 'http://9.15.87.116:8084/v1/chat/completions'
model_name = 'Qwen3-32B'

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        input_data = row['Input']
        id_data = row['ID']
        item_type = row['物品分类']
        expected_answer = row['Test answer']
        hist_preference = row['历史偏好']
        must_answer = row['指定回答']
        clarify_ans = row['澄清结果Answer']
        test_cases.append({'id': id_data, 'Input': input_data, 'item_type': item_type, 'Test answer': expected_answer, 'hist_Pre': hist_preference, 'clarify_ans': clarify_ans, 'Must answer': must_answer})
    return test_cases

def write_to_excel(filename, out_data, successCount, successesRate, usePrompt, average_Time, max_elaspse_time, min_elaspse_time):
    df1 = pd.DataFrame(out_data)
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elaspse_time, 'Min_Elapse_Time': min_elaspse_time, '参数澄清Prompt': usePrompt, '评判正确模型Prompt': prompt_paraClarify.Food_Reply_Agent3, '评判满意度Prompt': '模型澄清内容 vs 历史偏好'}
    df2 = pd.DataFrame(data)
    folder_path = os.path.dirname(filename)
    if folder_path:
        os.makedirs(folder_path, exist_ok=True)
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)
        df2.to_excel(writer, sheet_name='Test Result Summary', index=False)

def read_and_update_excel(filename, out_data, sheet_name='LLM test'):
    try:
        with pd.ExcelFile(filename) as excel_file:
            df = excel_file.parse(sheet_name)
        if len(out_data) != len(df):
            raise ValueError('out_data 的长度与 Excel 文件中的行数不一致！')
        df['Input'] = [item['Input'] for item in out_data]
        with pd.ExcelWriter(filename, mode='w', engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
    except Exception as e:
        print(f'操作失败：{e}')

def check_hist_pre(clarification_str, preference_str):
    my_logger.info('------------------------------start checking not depend his')
    clarification_json = clarification_str.replace("'", '"')
    preference_json = preference_str.replace("'", '"')
    my_logger.info(str(clarification_json))
    my_logger.info(preference_json)
    try:
        clarification = json.loads(clarification_json)
    except json.JSONDecodeError:
        return {'满意度': '不满意', '评测依据': 'JSON解析失败' + str(clarification_json)}
    try:
        preference = json.loads(preference_json)
    except json.JSONDecodeError:
        return {'满意度': '不满意', '评测依据': 'JSON解析失败' + str(preference_json)}
    clarification_values = list(clarification.values())
    preference_values = list(preference.values())
    for pref_value in preference_values:
        flag = False
        for clar_value in clarification_values:
            if str(pref_value) in str(clar_value):
                flag = True
                break
        if not flag:
            reason = f'未找到匹配的值: {pref_value}'
            return {'满意度': '不满意', '评测依据': reason}
    return {'满意度': '非常满意', '评测依据': '对比 模型提参 vs 提参答案'}

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
        answer_content = extract_clean_text(parts[1])
    else:
        answer_content = extract_clean_text(message_body)
    return answer_content

def getClarifyAnswer(data):
    data = data.replace('```', '')
    data = data.replace('json', '')
    res = json.loads(data)
    status = res.get('澄清状态', '')
    product = res.get('商品属性', {})
    question = res.get('澄清问题', '')
    result = {'澄清状态': str(status), '商品属性': product, '澄清问题': str(question)}
    return result

def getAnswer(data):
    data = data.replace('```', '')
    data = data.replace('json', '')
    res = json.loads(data)
    Content = res['问答回应']
    result = {'问答回应': str(Content)}
    return result

def getTime():
    years = pendulum.now().format('YYYY-MM-DD')
    weeks = pendulum.now().format('dddd')
    weekdays = {'Monday': '星期一', 'Tuesday': '星期二', 'Wednesday': '星期三', 'Thursday': '星期四', 'Friday': '星期五', 'Saturday': '星期六', 'Sunday': '星期天'}
    return years + weekdays[weeks]

def getIsSatisfied(data):
    data = data.replace('[', '')
    data = data.replace(']', '')
    res = json.loads(data)
    answer = res['满意度']
    content = res['评测依据']
    result = {'满意度': str(answer), '评测依据': str(content)}
    return result

def save_success_rate(file_path, success_rate):
    df1 = pd.DataFrame(success_rate)
    with pd.ExcelWriter(file_path) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)

def judge_satisfy(resultPrint: str, data: dict):
    if isSatisfied['满意度'] != '非常满意':
        return False
    clarify_list = data['clarify'].split('、')
    for i in clarify_list:
        results1 = json.loads(resultPrint.replace("'", '"'))
        if i not in results1.keys():
            return False
    return True
