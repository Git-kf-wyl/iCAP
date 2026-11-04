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
import copy
import prompt as tested_Prompt
import prompt_paraClarify_0816
import getContext
url = 'http://9.15.87.116:8084/v1/chat/completions'
model_name = 'Qwen3-32B'
dirs_name = str(datetime.now().strftime('%Y-%m-%d_%H'))
my_logger = logger.Logger('paraClarify2_origin_check_food_v2_2' + str(datetime.now().strftime('%Y-%m-%d_%H-%M-%S')), log_dir='./' + dirs_name + '/Logger/01_2food')
Food_Reply_Agent = '\n你是一个对话交互助手，你的任务是根据输入识别输入的问题给出相应的回应。\n\n**核心原则**：\n  - **精准性**：禁止猜测或添加默认值\n  - **专业性**：熟悉电商商品属性体系（如价格/品牌/尺码/材质等），符合电商筛选条件的业界惯例、熟悉外卖商品属性体系（如规格/口味/配送要求等），给对方的回答必须符合购物订单生成标准\n\n**上下文**\n\n对方是购物平台，根据我输入的请求，它帮我挑选商品，并向我询问购物的要求，你的责任是帮我回应它的请求。问题回应采取如下规则：\n\n根据商品的属性选择一个属性回答即可，例如我购买的是披萨，购物平台询问需要什么口味，你回答芝士榴莲即可。如果对方的询问中只问了是否还有额外的要求，直接回答没有即可。\n\n**角色设定**\n    - **身份**：对话交互助手\n    - **能力**：    \n      - 根据询问的问题，做相应的回答，如果问题中有多个问题，并且只需要针对其中一个问题回应即可（如"请问需要什么份量？还有其他的需求吗？" → 问答回应"小份"）\n    - **限制**：\n      - 回答回应要以肯定的语句，不能用反问句、问句 \n      - 简单回答即可\n      - 如果问题中不止存在一个问题，禁止在一次问答回应中回应多个问题，只针对第一个提到的问题做回答\n\n**输出格式**：用JSON列表输出,格式如下\n\n {\n  "问答回应": "问答回应"\n }\n\n**样例**\n请问需要什么规格的豆浆？\n\n输出：\n{\n "问答回应": "大杯"\n}\n\n<历史对话>\n{0}\n'

def compare_strings(s1, s2):
    if s1 == s2:
        my_logger.info('两个字符串相等')
        return
    my_logger.info('两个字符串不相等')
    min_len = min(len(s1), len(s2))
    for i in range(min_len):
        if s1[i] != s2[i]:
            my_logger.info(f'从第 {i + 1} 个字符开始不同（索引 {i}）:')
            my_logger.info(f"字符串1: '{s1[i]}'")
            my_logger.info(f"字符串2: '{s2[i]}'")
            return
    if len(s1) != len(s2):
        i = min_len
        my_logger.info(f'前面 {min_len} 个字符相同，但从第 {i + 1} 个字符开始不同（长度不同）:')
        if len(s1) > len(s2):
            my_logger.info(f"字符串1 多出字符: '{s1[i]}'")
        else:
            my_logger.info(f"字符串2 多出字符: '{s2[i]}'")

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        input_data = row['Input']
        id_data = row['ID']
        item_type = row['物品分类']
        expected_answer = row['Test answer']
        clarify_ans = row['澄清结果Answer']
        test_cases.append({'id': id_data, 'Input': input_data, 'item_type': item_type, 'Test answer': expected_answer, 'clarify_ans': clarify_ans})
    return test_cases

def checkans():
    my_logger.info('-----------------start checking para res')
    if resultPrint != data['clarify_ans']:
        compare_strings(resultPrint, data['clarify_ans'])
        isSatisfied = {'满意度': '不满意', '评测依据': f'对比 模型提参 vs 提参答案'}
    else:
        isSatisfied = {'满意度': '非常满意', '评测依据': f'对比 模型提参 vs 提参答案'}
    return

def check_hist_pre(clarification_str, preference_str):
    my_logger.info('------------------------------start checking para res')
    clarification_json = clarification_str.replace("'", '"')
    preference_json = preference_str.replace("'", '"')
    my_logger.info(str(clarification_json))
    my_logger.info(preference_json)
    try:
        clarification = json.loads(clarification_json)
        preference = json.loads(preference_json)
    except json.JSONDecodeError:
        return {'满意度': '不满意', '评测依据': 'JSON解析失败'}
    if '商品名称' in preference.keys():
        if '商品名称' not in clarification.keys() or preference['商品名称'] != clarification['商品名称']:
            return {'满意度': '不满意', '评测依据': '商品名称匹配错误'}
    if '店铺名称' in preference.keys():
        if '店铺名称' not in clarification.keys() or preference['店铺名称'] != clarification['店铺名称']:
            return {'满意度': '不满意', '评测依据': '店铺名称匹配错误'}
    if '数量' in preference.keys():
        if preference['数量'] != 1 and '数量' not in clarification.keys() or (preference['数量'] != 1 and preference['数量'] != clarification['数量']):
            return {'满意度': '不满意', '评测依据': '数量匹配错误'}
        elif preference['数量'] == 1:
            preference.pop('数量')
    clarification_values = list(clarification.values())
    preference_values = list(preference.values())
    for pref_value in preference_values:
        pref_value = str(pref_value)
        if len(pref_value.split(',')) > 1:
            pref_values = pref_value.split(',')
        elif len(pref_value.split('，')) > 1:
            pref_values = pref_value.split('，')
        elif len(pref_value.split('、')) > 1:
            pref_values = pref_value.split('、')
        else:
            pref_values = list(pref_value)
        flag = False
        for value in pref_values:
            for clar_value in clarification_values:
                if str(value) in str(clar_value):
                    flag = True
                    break
            if not flag:
                reason = f'未找到匹配的值: {value}'
                return {'满意度': '不满意', '评测依据': reason}
    return {'满意度': '非常满意', '评测依据': '对比 模型提参 vs 提参答案'}

def write_to_excel(filename, out_data, successCount, successesRate, usePrompt, average_Time, max_elaspse_time, min_elaspse_time):
    df1 = pd.DataFrame(out_data)
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elaspse_time, 'Min_Elapse_Time': min_elaspse_time, '参数澄清Prompt': usePrompt, '评判正确模型Prompt': prompt_paraClarify_0816.Food_Reply_Agent3, '评判满意度Prompt': '模型澄清内容 vs 历史偏好'}
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
    status = res['澄清状态']
    product = res['商品属性']
    question = res['澄清问题']
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
