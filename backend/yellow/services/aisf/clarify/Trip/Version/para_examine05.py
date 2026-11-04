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
from services.aisf.clarify.Trip.Version import use_preference_prompt as answer_prompt
from services.aisf.clarify.Trip.Version import prompt as testedPrompt
from services.aisf.clarify.Trip.Version.constants import BASE_DIR, CURRENT_DIR
from services.aisf.clarify.constants import CLARIFY_BASE_DIR_OUTPUT
url = 'http://127.0.0.1:1/unconfigured'
model_name = 'Qwen3-32B'

def getTime():
    years = pendulum.now().format('YYYY-MM-DD')
    weeks = pendulum.now().format('dddd')
    weekdays = {'Monday': '星期一', 'Tuesday': '星期二', 'Wednesday': '星期三', 'Thursday': '星期四', 'Friday': '星期五', 'Saturday': '星期六', 'Sunday': '星期天'}
    return years + weekdays[weeks]

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        expected_answer = row['TestAnswer']
        travel_prompt = row['Use Prompt']
        user_prefer = row['历史偏好']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'Use Prompt': travel_prompt, 'User prefer': user_prefer})
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
        answer_content = extract_clean_text(parts[1])
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
        status = res['Type']
        text = res['Data']
        question = res['Desc']
    except JSONDecodeError as e:
        my_logger.error('被测模型返回结果' + data + '非标准JSON格式')
        status = 'result'
        text = ''
        question = '被测模型返回结果非标准JSON格式'
    result = {'Type': str(status), 'Data': str(text), 'Desc': str(question)}
    return json.dumps(result, ensure_ascii=False)

def getAnswer(data):
    data = data.replace('```', '')
    data = data.replace('json', '')
    try:
        res = json.loads(data)
        Content = res['问答回应']
    except JSONDecodeError as e:
        my_logger.error('问答助手返回结果' + data + '非标准JSON格式')
        Content = ''
    result = {'问答回应': str(Content)}
    return json.dumps(result, ensure_ascii=False)

def save_success_rate(file_path, success_rate):
    df1 = pd.DataFrame(success_rate)
    with pd.ExcelWriter(file_path) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)

def is_successful(TestAnswer, LLMAnswer):
    try:
        TestAnswer = TestAnswer.replace("'", '"')
        LLMAnswer = LLMAnswer.replace("'", '"')
        LLMAnswer = json.loads(LLMAnswer)
        TestAnswer = json.loads(TestAnswer)
    except Exception as e:
        my_logger.error('字符串转化为JSON错误' + str(e))
        return (0, '模型输出格式有误')
    for key in TestAnswer:
        if TestAnswer[key] not in LLMAnswer[key] and LLMAnswer[key] not in TestAnswer[key]:
            return (0, '模型提取' + key + '参数错误')
    return (1, '模型提取参数正确')

def main_entry(outer_task_id, outer_model_name, outer_url):
    if outer_task_id and outer_model_name and outer_url:
        task_id, model_name, url = (outer_task_id, outer_model_name, outer_url)
    dir_path = 'testInput_use_preference05'
    global my_logger
    my_logger = logger.Logger('使用历史偏好05' + str(datetime.now().strftime('%Y-%m-%d_%H-%M-%S')), log_dir=CLARIFY_BASE_DIR_OUTPUT + task_id + CURRENT_DIR + '/Logger/05')
    MAX_BAD_LENGTH = 19
    out_data_bad_case = []
    for file in os.listdir(BASE_DIR + dir_path):
        if file.endswith(('.xlsx', '.xls')):
            file_path = os.path.join(BASE_DIR + dir_path, file)
            inputData = read_from_excel(file_path)
            out_data = []
            out_data_bad_case = []
            successCount = 0
            usePrompt = ''
            max_elapse_time = 0
            min_elapse_time = 0
            sum_elapsed_time_print = 0
            bad_case_count = 0
            for data in inputData:
                score_judge_prompt = 0
                my_logger.info('当前用例ID' + data.get('ID') + ',当前用户输入:' + data['Input'])
                if data.get('Use Prompt') == 'Trip':
                    usePrompt = testedPrompt.TripPrompt
                elif data.get('Use Prompt') == 'Airplane':
                    usePrompt = testedPrompt.AirplanePrompt
                elif data.get('Use Prompt') == 'Hotel':
                    usePrompt = testedPrompt.HotelPrompt
                hisQuery = [data['Input']]
                hisClarify = []
                hisClarifyResult = []
                lastClarify = ''
                lastAnswer = ''
                hisQueryPrint = []
                results = []
                isSatisfied = {}
                flag = True
                question_for_clarify = ''
                question_for_judge = ''
                elapsed_time_print = 0
                tokens_print = {}
                clarifyInput = []
                judgeInput = []
                resultPrint = ''
                score = 0
                first_clarify = ''
                while True:
                    result = {}
                    if len(lastClarify):
                        model_test = str(question_for_clarify) + '\n\n/nothink'
                        clarifyInput.append({'role': 'assistant', 'content': str(lastClarify)})
                        clarifyInput.append({'role': 'user', 'content': str(model_test)})
                    else:
                        question_for_clarify = data['Input']
                        model_test = '## 历史偏好\n' + data['User prefer'] + '\n\n## 当前时间\n' + getTime() + '\n## 当前城市 \n南京市 ' + '\n\n用户输入 ' + question_for_clarify + '\n\n/nothink'
                        clarifyInput.append({'role': 'system', 'content': str(usePrompt)})
                        clarifyInput.append({'role': 'user', 'content': str(model_test)})
                        hisClarify.append('用户输入:' + data['Input'])
                    clarifyResult = {}
                    clarify = ''
                    try:
                        my_logger.info('开始调用被测模型')
                        my_logger.info('给被测模型的澄清结果:' + model_test)
                        LLM_answer, elapsed_time_print, tokens_print = connectModel(clarifyInput)
                        clarify = parse_think_response_clean(LLM_answer)
                        my_logger.info('澄清结果' + clarify)
                        clarifyResult = getClarifyAnswer(clarify)
                        lastClarify = clarify
                    except Exception as e:
                        clarifyResult = {'Desc': '', 'Type': 'result', 'Data': '模型回答出错'}
                        my_logger.error(str(e))
                    finally:
                        question_for_judge = json.loads(clarifyResult)['Desc']
                    if json.loads(clarifyResult)['Type'] == 'result':
                        resultPrint += str(json.loads(clarifyResult)['Data'])
                        break
                    hisQueryPrint.append(question_for_judge)
                    try:
                        if not len(lastAnswer):
                            judgeInput.append({'role': 'system', 'content': answer_prompt.Travel_Reply_Prompt})
                            judgeInput.append({'role': 'user', 'content': '\n<历史对话>\n' + str(hisQuery) + '\n <用户输入>\n' + question_for_judge})
                        else:
                            judgeInput.append({'role': 'assistant', 'content': lastAnswer})
                            judgeInput.append({'role': 'user', 'content': '<用户输入>\n' + question_for_judge})
                        my_logger.info('给评判模型的历史对话:' + str(hisQuery))
                        my_logger.info('给评判模型的本次输入:' + str(question_for_judge))
                        my_logger.info('开始调用问答助手模型')
                        LLM_answer, elapsed_time, tokens = connectModel(judgeInput)
                        resultAnswer = parse_think_response_clean(LLM_answer)
                        lastAnswer = resultAnswer
                        result = getAnswer(resultAnswer)
                        my_logger.info('模型应答：' + str(result))
                        results.append(result)
                        hisQuery.append(question_for_judge)
                        hisQuery.append(json.loads(result)['问答回应'])
                    except Exception as e:
                        result = {'问答回应': '模型回答失败!'}
                        result = json.dumps(result, ensure_ascii=False)
                        break
                    finally:
                        question_for_clarify = json.loads(result)['问答回应']
                        hisClarify.append(question_for_judge)
                        hisClarify.append(question_for_clarify)
                score, reason = is_successful(data['Test answer'], resultPrint)
                if score == 1:
                    successCount += 1
                    my_logger.info('success')
                if score == 0 and bad_case_count < MAX_BAD_LENGTH:
                    out_data_bad_case.append({'ID': data.get('ID'), 'Input': data.get('Input'), '澄清结果': hisQueryPrint, '评判模型输出': results, 'LLM answer': resultPrint, '历史偏好': data.get('User prefer'), 'Test Score': score, 'Fail Reason': reason, 'Elapsed_time': elapsed_time_print, 'Prompt_tokens': tokens_print['prompt_tokens'], 'Completion_tokens': tokens_print['completion_tokens'], 'Total_tokens': tokens_print['total_tokens']})
                    bad_case_count += 1
                out_data.append({'ID': data.get('ID'), 'Input': data.get('Input'), '澄清结果': hisQueryPrint, '评判模型输出': results, 'Test answer': data.get('Test answer'), 'LLM answer': resultPrint, '历史偏好': data.get('User prefer'), 'Test Score': score, 'Fail Reason': reason, 'Elapsed_time': elapsed_time_print, 'Prompt_tokens': tokens_print['prompt_tokens'], 'Completion_tokens': tokens_print['completion_tokens'], 'Total_tokens': tokens_print['total_tokens']})
                sum_elapsed_time_print += elapsed_time_print
                max_elapse_time = max(max_elapse_time, elapsed_time_print)
                min_elapse_time = min(min_elapse_time, elapsed_time_print)
            successRate = successCount / len(inputData)
            average_Time = sum_elapsed_time_print / len(inputData)
            output_dir = CLARIFY_BASE_DIR_OUTPUT + task_id + CURRENT_DIR + '/Output_use_preference05/'
            os.makedirs(output_dir, exist_ok=True)
            write_to_excel(str(output_dir + 'Use_preference05') + str(datetime.now().strftime('%Y-%m-%d_%H-%M-%S')) + '.xlsx', out_data, successCount, successRate, usePrompt, average_Time, max_elapse_time, min_elapse_time)
            write_to_excel(str(output_dir + 'Use_preference05_bad_case') + str(datetime.now().strftime('%Y-%m-%d_%H-%M-%S')) + '.xlsx', out_data_bad_case, successCount, successRate, usePrompt, average_Time, max_elapse_time, min_elapse_time)
            save_success_rate(str(CLARIFY_BASE_DIR_OUTPUT + task_id + CURRENT_DIR + '/05_result' + '.xlsx'), [{'Success_Count': successCount, 'Sum_Count': len(inputData), 'Success_Rate': successRate}])
