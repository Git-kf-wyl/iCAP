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
import prompt_extract as prompt
from services.aisf.memory.constants import BASE_DIR_OUTPUT, BASE_DIR
from services.aisf.thread_util import parse
url = 'http://127.0.0.1:1/unconfigured'
model_name = 'Qwen3-32B'
is_think = False
csvData = pd.read_csv(BASE_DIR + 'memory_81/extract2/domain_test.csv', encoding='utf-8')

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        user_input = row['UserInput']
        input_data = row['Input']
        test_cases.append({'ID': case_id, 'UserInput': user_input, 'Input': input_data, 'testAnswer': row['testAnswer']})
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
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elaspse_time, 'Min_Elapse_Time': min_elaspse_time, 'Fisrt_PROMPT': prompt.three, 'Second_PROMPT': prompt.pinlei}
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

def is_successful(model_output_str, answer_str):
    my_logger.info('------------------------------check Answer')
    my_logger.info(f'模型输出: {model_output_str}')
    my_logger.info(f'答案: {answer_str}')
    try:
        answer = json.loads(answer_str.replace("'", '"'))
        model_output = json.loads(model_output_str.replace("'", '"'))
    except json.JSONDecodeError as e:
        return {'满意度': '不满意', '评测依据': f'JSON解析失败: {str(e)}'}
    expected_keys = {'主题', '子主题', '品类'}
    model_keys = set(model_output.keys())
    if model_keys != expected_keys:
        missing = expected_keys - model_keys
        extra = model_keys - expected_keys
        reason_parts = []
        if missing:
            reason_parts.append(f'缺少必要字段: {list(missing)}')
        if extra:
            reason_parts.append(f'包含非法字段: {list(extra)}')
        return {'满意度': '不满意', '评测依据': '; '.join(reason_parts)}
    mismatch = []
    for key in expected_keys:
        ans_value = answer.get(key)
        model_value = model_output.get(key)
        if ans_value != model_value:
            mismatch.append(f"{key}: 答案='{ans_value}', 模型输出='{model_value}'")
    if mismatch:
        return {'满意度': '不满意', '评测依据': '；'.join(mismatch)}
    return {'满意度': '非常满意', '评测依据': '答案正确'}

def extract_entities_by_topic(topic, subtopic):
    """
    从 CSV 文件中根据 topic 和 subtopic 筛选 entity，并返回结构化 JSON 格式结果（自动去重）。

    参数:
        csv_file (str): CSV 文件路径
        topic (str): 主题名称（如 "清洁洗护"）
        subtopic (str): 子主题名称（如 "清洁用品"）

    返回:
        dict: 格式为 {f"{topic}-{subtopic}": [entity1, entity2, ...]} 的字典
              如果未找到匹配项，返回空字典 {}
    """
    try:
        filtered_df = csvData[csvData['sub_topic'] == subtopic]
        if filtered_df.empty:
            my_logger.info(f"未找到 sub_topic='{subtopic}' 的记录。")
            return {}
        if 'entity' not in filtered_df.columns:
            raise KeyError(f"CSV 中缺少 'entity' 列，请检查列名。当前列: {list(filtered_df.columns)}")
        result = filtered_df[['entity']].dropna(subset=['entity'])
        unique_entities = result['entity'].drop_duplicates().tolist()
        key = f'{topic}-{subtopic}'
        dict_new = {key: unique_entities}
        my_logger.info('Final dict:', dict_new)
        return dict_new
    except FileNotFoundError:
        my_logger.info(f'错误：文件未找到。')
        return {}
    except Exception as e:
        my_logger.info(f'处理过程中发生错误: {e}')
        return {}

def get_classification_result(input2):
    result = {}
    for temp in input2:
        res = extract_entities_by_topic(temp['主题'], temp['子主题'])
        result.update(res)
    content2 = '[\n'
    for key, value in result.items():
        parts = key.split('-', 1)
        if len(parts) == 2:
            topic = parts[0]
            subtopic = parts[1]
            newRes = {'主题': topic, '子主题': subtopic, '品类': value}
            newRes = json.dumps(newRes, ensure_ascii=False)
            content2 = content2 + newRes + '\n'
    content2 += ']'
    return content2

def getAnswer(data):
    data = data.replace('```', '')
    data = data.replace('json', '')
    return data

def is_successful1(model_output_str, answer_str):
    my_logger.info('------------------------------check topic and subtopic')
    my_logger.info(f'模型输出: {model_output_str}')
    my_logger.info(f'答案: {answer_str}')
    try:
        answer = json.loads(answer_str.replace("'", '"'))
        model_output_list = json.loads(model_output_str.replace("'", '"'))
    except json.JSONDecodeError as e:
        return {'满意度': '不满意', '评测依据': f'JSON解析失败: {str(e)}'}
    if not isinstance(model_output_list, list):
        return {'满意度': '不满意', '评测依据': '模型输出不是列表格式'}
    compare_keys = ['主题', '子主题']
    missing_in_answer = [key for key in compare_keys if key not in answer]
    if missing_in_answer:
        return {'满意度': '不满意', '评测依据': f'答案中缺少必要字段: {missing_in_answer}'}
    answer_values = {key: answer[key] for key in compare_keys}
    matched_items = []
    for idx, model_item in enumerate(model_output_list):
        if not isinstance(model_item, dict):
            continue
        model_values = {key: model_item.get(key) for key in compare_keys}
        if model_values == answer_values:
            matched_items.append((idx, model_item))
    if matched_items:
        first_match_idx, first_match_item = matched_items[0]
        return {'满意度': '非常满意', '评测依据': f'第 {first_match_idx + 1} 个结果匹配成功: {first_match_item}'}
    else:
        return {'满意度': '不满意', '评测依据': f'无匹配项。期望: {answer_values}'}
