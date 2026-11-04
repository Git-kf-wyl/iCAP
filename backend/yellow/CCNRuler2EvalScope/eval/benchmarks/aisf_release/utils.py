# Private iCAP Yellow implementation. Do not publish.
import os
import pandas as pd
import requests
import json
import re
import time
import base64
import re
import json
import math
import logging
import requests
import time
import yaml
from pprint import pprint
from dateutil import parser
from datetime import datetime, timedelta
import jionlp as jio
import logging
from eval.benchmarks.aisf_release.prompt import AisfBoxParamExtractSystemPrompt
from docutils.nodes import field
from eval.benchmarks.aisf_release.auto_judge_func import *
from eval.benchmarks.aisf_release.qwen_resize import smart_resize
from PIL import Image
import ast
from eval.utils.logger import get_logger
logger = get_logger()

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename, keep_default_na=False)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        expected_answer = row['Test answer']
        if 'APP' in df.columns:
            app_name = row['APP']
        else:
            app_name = ''
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'APP': app_name})
    return test_cases

def read_from_excel_function_call(filename):
    test_cases = []
    df = pd.read_excel(filename, keep_default_na=False)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        expect_name = row['expect-name']
        expect_agent_name = row['expect-agent_name']
        expect_keywords1 = row['expect-keywords1']
        expect_keywords2 = row['expect-keywords2']
        old_ans = row['OldAns']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Expect name': expect_name, 'Expect agent name': expect_agent_name, 'Expect keywords1': expect_keywords1, 'Expect keywords2': expect_keywords2, 'old_ans': old_ans})
    return test_cases

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
    text = message_body['contents']
    parts = text.split('</think>', 1)
    if len(parts) == 2:
        think_content = extract_clean_text(parts[0])
        answer_content = extract_clean_text(parts[1])
    else:
        think_content = None
        answer_content = extract_clean_text(text)
    return answer_content

def get_json_structure(input, need_json_fix=False):
    """
    提取字符串中的json结构，去掉```json和```并取中间部分，若没有干扰的字符，直接取整个字符串转化为json
    """

    def get_json_data(loc_str, need_json_fix):
        try:
            json_data = json.loads(loc_str)
        except Exception as ex:
            if need_json_fix:
                loc_str = fix_json(loc_str)
            sub_json_str, sub_json_result = get_last_json_object(loc_str)
            replace_str = loc_str.replace(sub_json_str, '')
            sec_sub_json_str, sec_sub_json_result = get_last_json_object(replace_str)
            found_all_key = True
            for key_str in sub_json_result:
                if key_str not in sec_sub_json_result:
                    found_all_key = False
                    break
            if found_all_key:
                return {}
            return sub_json_result
        return json_data
    loc_str = input
    try:
        loc_str = erase_comment(loc_str)
        loc_str = loc_str.replace('\xa0', ' ')
        if '```json' in loc_str:
            json_str = loc_str.split('```json', 1)[-1].split('```', 1)[0]
            json_data = json.loads(json_str)
        elif '```' in loc_str:
            json_str = loc_str.split('```', 1)[-1].split('```', 1)[0]
            json_data = json.loads(json_str)
        else:
            return get_json_data(loc_str, need_json_fix)
    except Exception as ex:
        logging.error('get json error:' + loc_str)
        json_data = get_json_data(loc_str, need_json_fix)
    return json_data

def fix_json(self, json_str):
    json_str = json_str.strip()
    is_windows = '\r\n' in json_str
    enter_key = '\r\n' if is_windows else '\n'
    json_str_list = json_str.split('\r\n"') if is_windows else json_str.split('\n"')
    for i in range(len(json_str_list)):
        curr_kv = json_str_list[i]
        if not curr_kv.endswith('{') and (not curr_kv.endswith('}')):
            if not curr_kv.endswith('",'):
                if curr_kv.endswith('"'):
                    json_str_list[i] = curr_kv + ','
                else:
                    json_str_list[i] = curr_kv + '",'
    json_str = '\n"'.join(json_str_list)
    if json_str.endswith('".' + enter_key + '}'):
        json_str = re.sub('"\\.' + enter_key + '}$', '"' + enter_key + '}', json_str)
    json_str_list = json_str.split('": "')
    for i in range(len(json_str_list)):
        curr_str = json_str_list[i]
        second_split_str = '",\r\n"' if is_windows else '",\n"'
        if second_split_str in curr_str:
            sub_str_list = curr_str.split(second_split_str)
            for j in range(len(sub_str_list)):
                sub_str_list[j] = re.sub('(?<!\\\\)"', '', sub_str_list[j])
                sub_str_list[j] = re.sub(':\\\\ +\\\\"', ': \\"\\"', sub_str_list[j])
            curr_str = second_split_str.join(sub_str_list)
        json_str_list[i] = curr_str
    json_str = '": "'.join(json_str_list)
    return json_str

def get_last_json_object(loc_str):
    end_pos = loc_str.rfind('}')
    left_brackets_indexs = find_all_index_of_char(loc_str, '{')
    find_json = False
    for i in left_brackets_indexs[::-1]:
        if i < end_pos:
            json_str = loc_str[i:end_pos + 1]
            try:
                json_result = json.loads(json_str)
                find_json = True
            except Exception as ex:
                json_result = {}
            if find_json:
                return (json_str, json_result)
    return ('{}', {})

def find_all_index_of_char(str, char):
    result = []
    for i in range(len(str)):
        if str[i] == char:
            result.append(i)
    return result

def erase_comment(erase_predict):
    lines = erase_predict.split('\n')
    new_lines = []
    for line in lines:
        if '//' in line:
            comma = line.find(',')
            pos = line.rfind('//')
            s_quotation = line.rfind("'")
            d_quotation = line.rfind('"')
            colon = line.find('\\:')
            rcolon = line.rfind('\\:')
            if (s_quotation < pos and d_quotation < pos or (comma > 0 and comma < pos and (colon == rcolon))) and colon < pos:
                line = line[:pos]
        new_lines.append(line)
    new_str = '\n'.join(new_lines)
    return new_str

def click_test(action, screenshot_file, order, resp_type):
    model_resp_cfg = resp_type
    bbox_pattern = model_resp_cfg['regex']
    width, height = Image.open(screenshot_file).size
    match = re.findall(bbox_pattern, action)
    if len(match) == 0:
        match = re.findall(DEFAULT_REGEX, action)
    xmin, ymin, xmax, ymax, x, y = (-999, -999, -999, -999, -999, -999)
    if len(match) > 0:
        try:
            xmin, ymin, xmax, ymax = list(map(int, match[0]))
        except:
            try:
                x, y = list(map(int, match[0]))
            except:
                logging.error(f'===err=== action err {match[0]}')
                return 0
    else:
        logging.error(f'===err=== action err {action}')
        return 0
    if xmin >= 0:
        if model_resp_cfg['isMillile']:
            xmin = int(xmin / 999 * width)
            ymin = int(ymin / 999 * height)
            xmax = int(xmax / 999 * width)
            ymax = int(ymax / 999 * height)
        x, y = (int((xmin + xmax) / 2), int((ymin + ymax) / 2))
    elif x >= 0:
        if model_resp_cfg['isMillile']:
            x = int(x / 999 * width)
            y = int(y / 999 * height)
    if model_resp_cfg['resize']:
        new_height, new_width = smart_resize(height, width)
        x = int(x * width / new_width)
        y = int(y * height / new_height)
    iter_ret = judge_click(order, x, y, width, height)
    if iter_ret is None:
        logging.error(f'test case: [{iter}] is error!! the order is [{order}]')
        return 0
    return iter_ret

def swipe_screen_test(action, screenshot_file, order):
    width, height = Image.open(screenshot_file).size
    position = action.split('<bbox>')[1].split('</bbox>')[0].strip('[').strip(']')
    direction = action.split('direction')[1].split('=')[1].strip(')')
    xmin, ymin, xmax, ymax = map(int, position.split(','))
    xmin = int(xmin / 999 * width)
    ymin = int(ymin / 999 * height)
    xmax = int(xmax / 999 * width)
    ymax = int(ymax / 999 * height)
    x, y = (int((xmin + xmax) / 2), int((ymin + ymax) / 2))
    return judge_scroll(xmin, ymin, xmax, ymax, width, height, order)

def scroll_test(action, screenshot_file, order, resp_type):
    width, height = Image.open(screenshot_file).size
    try:
        bbox_pattern = '(\\d+), *(\\d+).*?(\\d+), *(\\d+)'
        match = re.findall(bbox_pattern, action)
        xmin, ymin, xmax, ymax = list(map(int, match[0]))
    except:
        try:
            bbox_pattern = "start_box=\\'[<\\|box_start\\|>]*\\((\\d+), *(\\d+)\\)[<\\|box_end\\|>]*\\', *end_box=\\'[<\\|box_start\\|>]*\\((\\d+), *(\\d+)\\)"
            match = re.findall(bbox_pattern, action)
            xmin, ymin, xmax, ymax = list(map(int, match[0]))
        except:
            return 0
    if resp_type['isMillile']:
        xmin = int(xmin / 999 * width)
        ymin = int(ymin / 999 * height)
        xmax = int(xmax / 999 * width)
        ymax = int(ymax / 999 * height)
    if resp_type['resize']:
        new_height, new_width = smart_resize(height, width)
        xmin = int(xmin * width / new_width)
        ymin = int(ymin * height / new_height)
        xmax = int(xmax * width / new_width)
        ymax = int(ymax * height / new_height)
    return judge_scroll(xmin, ymin, xmax, ymax, width, height, order)

def set_text_test(action, screenshot_file, order):
    text = action.split('text="')[-1].split('"')[0]
    print('text:', text)
    return judge_type(text, order)

def type_test(action, order, resp_type):
    try:
        if resp_type['resize']:
            text = action.split(':')[-1].split('"')[1]
        else:
            text = action.split("content='")[-1].split("'")[0]
    except:
        text = ''
    return judge_type(text, order)

def long_press_test(action, screenshot_file, order, resp_type):
    width, height = Image.open(screenshot_file).size
    xmin, ymin, xmax, ymax, x, y = (-999, -999, -999, -999, -999, -999)
    try:
        bbox_pattern = '(\\d+), *(\\d+), *(\\d+), *(\\d+)'
        match = re.findall(bbox_pattern, action)
        xmin, ymin, xmax, ymax = list(map(int, match[0]))
    except:
        try:
            bbox_pattern = '(\\d+), *(\\d+)'
            match = re.findall(bbox_pattern, action)
            x, y = list(map(int, match[0]))
        except:
            return 0
    if xmin > 0:
        x = int((xmin + xmax) / 2)
        y = int((ymin + ymax) / 2)
    if resp_type['isMillile']:
        x = int(x / 999 * width)
        y = int(y / 999 * height)
    if resp_type['resize']:
        new_height, new_width = smart_resize(height, width)
        x = int(x * width / new_width)
        y = int(y * height / new_height)
    return judge_long_press(x, y, width, height, order)

def open_app_test(action, screenshot_file, order):
    if 'open_app' not in action:
        return 0
    app_name = action.split("app_name='")[-1].split("'")[0]
    return judge_open_app(app_name, order)
ITER = 0

def process_results(answer, predict, raw_input_d, resp_type, base_dir):
    global ITER
    ITER += 1
    action = predict
    order = answer
    screenshot_file = os.path.join(base_dir, raw_input_d['img'])
    screenshot_file = screenshot_file.replace('\n', '')
    screenshot_file = screenshot_file.replace('\\', '/')
    if 'click' in action or 'handle_exception' in action:
        res = click_test(action, screenshot_file, order, resp_type)
        return res
    elif 'swipe_screen' in action:
        res = swipe_screen_test(action, screenshot_file, order)
        return res
    elif 'scroll' in action:
        res = scroll_test(action, screenshot_file, order, resp_type)
        return res
    elif 'set_text' in action:
        res = set_text_test(action, screenshot_file, order)
        return res
    elif 'call_user' in action:
        return judge_call_user(order, action)
    elif 'type' in action:
        res = type_test(action, order, resp_type)
        return res
    elif 'press_back' in action:
        res = judge_back(order)
        return res
    elif 'press_home' in action:
        res = judge_home(order)
        return res
    elif 'wait' in action:
        res = judge_wait(order)
        return res
    elif 'finished' in action:
        res = judge_finish(order)
        return res
    elif 'enter' in action:
        res = judge_enter(order)
        return res
    elif 'long_press' in action:
        res = long_press_test(action, screenshot_file, order, resp_type)
        return res
    elif 'swipe' in action:
        return scroll_test(action, screenshot_file, order, resp_type)
    elif 'terminate' in action:
        return judge_finish(order)
    elif 'system_button' in action and 'Back' in action:
        return judge_back(order)
    elif 'system_button' in action and 'Home' in action:
        return judge_home(order)
    elif get_order_type(order) is None:
        return 1
    else:
        return 0
    return 1

def is_valid(var):
    if var is None:
        return False
    if isinstance(var, (str, list, dict, tuple, set)):
        if len(var) == 0:
            return False
    if isinstance(var, float):
        if math.isnan(var):
            return False
    return True

def is_sucessful(LLM_answer, expected_answer):
    if str(expected_answer) not in str(LLM_answer):
        return False
    return True

def read_from_excel_1(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        if 'TestAnswer' in row:
            expected_answer = row['TestAnswer']
        elif 'Test answer' in row:
            expected_answer = row['Test answer']
        travel_prompt = row['Use Prompt']
        current_date = row['当前日期']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'Use Prompt': travel_prompt, 'Current date': current_date})
    return test_cases

def read_from_excel_2(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        travel_prompt = row['Use Prompt']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Use Prompt': travel_prompt})
    return test_cases

def read_from_excel_3(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        if 'TestAnswer' in row:
            expected_answer = row['TestAnswer']
        elif 'Test answer' in row:
            expected_answer = row['Test answer']
        travel_prompt = row['Use Prompt']
        addition_input = row['追加']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'Use Prompt': travel_prompt, 'Addition input': addition_input})
    return test_cases

def read_from_excel_4(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        if 'TestAnswer' in row:
            expected_answer = row['TestAnswer']
        elif 'Test answer' in row:
            expected_answer = row['Test answer']
        travel_prompt = row['Use Prompt']
        user_prefer = row['历史偏好']
        query_content = row['询问内容']
        must_answer = row['指定回答']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'Use Prompt': travel_prompt, 'User prefer': user_prefer, 'Query content': query_content, 'Must answer': must_answer})
    return test_cases

def read_from_excel_5(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        if 'TestAnswer' in row:
            expected_answer = row['TestAnswer']
        elif 'Test answer' in row:
            expected_answer = row['Test answer']
        travel_prompt = row['Use Prompt']
        user_prefer = row['历史偏好']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'Use Prompt': travel_prompt, 'User prefer': user_prefer})
    return test_cases

def read_from_excel_taxi_para_check(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        expected_answer = row['TestAnswer']
        travel_prompt = row['Use Prompt']
        default_addr = row['代指地址']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'Use Prompt': travel_prompt, 'default_address': default_addr})
    return test_cases

def read_from_excel_taxi_must_clarify(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        clarify_content = row['必须澄清的属性']
        travel_prompt = row['Use Prompt']
        default_addr = row['代指地址']
        test_cases.append({'ID': case_id, 'Input': input_data, 'clarify': clarify_content, 'Use Prompt': travel_prompt, 'default_address': default_addr})
    return test_cases

def read_from_excel_taxi_change_user(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        expected_answer = row['TestAnswer']
        travel_prompt = row['Use Prompt']
        addition_input = row['追加']
        default_addr = row['代指地址']
        test_cases.append({'ID': case_id, 'Input': input_data, 'Test answer': expected_answer, 'Use Prompt': travel_prompt, 'Addition input': addition_input, 'default_address': default_addr})
    return test_cases

def is_successful(test_anaswer, llm_answer):
    try:
        test_anaswer = test_anaswer.replace("'", '"')
        llm_answer = llm_answer.replace("'", '"')
        test_anaswer = json.loads(test_anaswer)
        llm_answer = json.loads(llm_answer)
    except Exception as e:
        logger.error('字符串转化为JSON错误' + str(e))
        print('字符串转化为JSON错误' + str(e))
        return False
    for key in test_anaswer:
        if key not in llm_answer:
            return False
        if test_anaswer[key] not in llm_answer[key] and llm_answer[key] not in test_anaswer[key]:
            logger.error('模型提取' + key + '参数错误')
            print('模型提取' + key + '参数错误')
            return False
    return True

def is_successful_hotel(test_answer, llm_answer):
    try:
        test_answer = test_answer.replace("'", '"')
        llm_answer = llm_answer.replace("'", '"')
        test_answer = json.loads(test_answer)
        llm_answer = json.loads(llm_answer)
    except Exception as e:
        logger.error('字符串转化为JSON错误' + str(e))
        print('字符串转化为JSON错误' + str(e))
        return False
    date_keys = ['dDate1', 'checkOutDate']
    for key in test_answer:
        if key not in llm_answer:
            return False
        if key not in date_keys:
            if test_answer[key] not in llm_answer[key] and llm_answer[key] not in test_answer[key]:
                logger.error('模型提取' + key + '参数错误')
                print('模型提取' + key + '参数错误')
                return False
    return True

def is_successful_2(LLMAnswer):
    hotel_must_clariy = ['dDate1', 'checkOutDate', 'aCity1']
    try:
        LLMAnswer = LLMAnswer.replace("'", '"')
        LLMAnswer = json.loads(LLMAnswer)
        print(LLMAnswer)
    except Exception as e:
        logging.error('字符串转化为JSON错误' + str(e))
        return 0
    for key in hotel_must_clariy:
        if LLMAnswer[key] == '':
            logging.error('模型未澄清' + key + '属性')
            return 0
    return 1

def partial_format(template: str, **kwargs):

    def replacer(match):
        index = int(match.group(1))
        return kwargs.get(f'{index}', match.group(0))
    return re.sub('\\{(\\d+)\\}', replacer, template)

def read_from_excel_food_1(filename):
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

def read_from_excel_food_2(filename):
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

def read_from_excel_food_3(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        input_data = row['Input']
        id_data = row['ID']
        expected_answer = row['Test answer']
        hist_preference = row['历史偏好']
        hist_answer = row['澄清结果Answer']
        test_cases.append({'id': id_data, 'Input': input_data, 'Test answer': expected_answer, 'hist_Pre': hist_preference, 'hist_ans': hist_answer})
    return test_cases

def read_from_excel_food_4(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        input_data = row['Input']
        id_data = row['ID']
        item_type = row['物品分类']
        expected_answer = row['Test answer']
        if 'TestAnswer' in row:
            my_testAnswer = row['TestAnswer']
        elif '澄清结果Answer' in row:
            my_testAnswer = row['澄清结果Answer']
        add_clarify = row['追加澄清answer']
        test_cases.append({'id': id_data, 'Input': input_data, 'item_type': item_type, 'Test answer': expected_answer, 'add_clarify': add_clarify, 'my_testAnswer': my_testAnswer})
    return test_cases

def read_from_excel_food_5(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        input_data = row['Input']
        id_data = row['ID']
        compare_answer = row['参数澄清Test Answer']
        expected_answer = row['Test answer']
        test_cases.append({'id': id_data, 'Input': input_data, 'compare_answer': compare_answer, 'Test answer': expected_answer})
    return test_cases

def check_hist_pre(clarification_str, preference_str):
    logger.info('------------------------------start checking para res')
    clarification_json = clarification_str.replace("'", '"')
    preference_json = preference_str.replace("'", '"')
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

def check_add_more_clarify(clarification_str, more_clarify):
    logging.info('------------------------------start checking not depend his')
    clarification_json = clarification_str.replace("'", '"')
    preference_json = more_clarify.replace("'", '"')
    logging.info(str(clarification_json))
    logging.info(preference_json)
    try:
        clarification = json.loads(clarification_json)
        preference = json.loads(preference_json)
    except json.JSONDecodeError:
        return {'满意度': '不满意', '评测依据': 'JSON解析失败'}
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

def replace_nan_with_empty(value):
    if isinstance(value, float) and math.isnan(value):
        return ''
    return value

def read_from_excel_box_scene_classify(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        case_structure = replace_nan_with_empty(row['CaseStructure'])
        input_data = row['Input']
        classify_expected = row['ClassifyAnswer']
        intent_expected = row['IntentAnswer']
        param_expected = row['ParamAnswer']
        test_cases.append({'id': case_id, 'input': input_data, 'case_structure': case_structure, 'classify_answer': classify_expected, 'intent_answer': intent_expected, 'param_answer': param_expected})
    return test_cases

def is_successful_aisf_box_scene_classify(expected, actual):
    real_expected = expected.strip()
    real_actual = actual.strip()
    print('~~~~~~~~~~~~~~~~~')
    print(real_expected)
    print(real_actual)
    print('~~~~~~~~~~~~~~~~~')
    if len(real_actual) != len(real_expected):
        print('分类结果与预期场景个数不相等')
        return False
    if real_actual != real_expected:
        print('分类结果错误')
        return False
    return True

def get_args(new_df):
    args_name = 'args'
    args_list = []
    for i in range(13):
        new_args_name = args_name + str(i + 1)
        try:
            if len(new_df[new_args_name]) > 0:
                args_name_value = new_df[new_args_name][0]
                args_jsonl = json.loads(args_name_value)
                args_list.append(args_jsonl)
        except Exception as e:
            return args_list
    return args_list

def params_extract_create(api, df, prompt):
    new_df = df[df['intent'] == api].reset_index(drop=True)
    args_description = get_args(new_df)
    new_prompt = prompt + str(args_description)
    if is_valid(api) and 'VIDEO_SEARCH_PLAY' in api:
        new_prompt += "\n\n##注意\n1. 如果用户没有明确提到xx导/xx演/xx主演，且你不确定该人名为导演/演员/角色，该参数无需提取，并设置networkSearch的值为1。\n2. 如果用户提到想看的xxx且你不确定用户提到的内容为影视名/剧情等，该参数无需提取，并设置networkSearch的值为1。\n\n## 示例\n我要看成龙演的中国电影 -> {'actor':'成龙','category':'电影','region':'中国内地'}\n我要看周星驰演的香港喜剧片 -> {'actor':'周星驰','type':'喜剧','category':'电影','region':'中国香港'}"
    return new_prompt

def read_from_excel_box_param_extract(filename, intent_df):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        case_structure = replace_nan_with_empty(row['CaseStructure'])
        input_data = row['Input']
        classify_expected = row['ClassifyAnswer']
        intent_expected = row['IntentAnswer']
        param_expected = row['ParamAnswer']
        sysprompt = params_extract_create(intent_expected, intent_df, AisfBoxParamExtractSystemPrompt)
        test_cases.append({'id': case_id, 'input': input_data, 'case_structure': case_structure, 'classify_answer': classify_expected, 'intent_answer': intent_expected, 'param_answer': param_expected, 'sysprompt': sysprompt})
    return test_cases

def compare_dicts(answer, extracted):
    try:
        answer_dict = ast.literal_eval(answer)
        if not isinstance(answer_dict, dict):
            raise ValueError('参考答案格式错误')
        extracted_dict = ast.literal_eval(extracted)
        if not isinstance(extracted_dict, dict):
            raise ValueError('模型输出格式有误')
    except Exception as e:
        logging.error(f'解析失败: {e}')
        return False
    for k, v in answer_dict.items():
        if k not in extracted_dict:
            print('模型提取 {k} 参数错误')
            return False
        if extracted_dict[k] != v:
            print(f'模型提取 {k} 参数值错误')
            return False
    if len(answer_dict) != len(extracted_dict):
        print('模型提取非指定参数')
        return False
    return True

def compare_dicts_aisf_box_llm32(answer, extracted_dict):
    try:
        answer_dict = ast.literal_eval(answer)
        if not isinstance(answer_dict, dict):
            raise ValueError('参考答案格式错误')
        if not isinstance(extracted_dict, dict):
            raise ValueError('模型输出格式有误')
    except Exception as e:
        print(f'解析失败: {e}')
        return False
    for k, v in answer_dict.items():
        if k not in extracted_dict:
            print('模型提取 {k} 参数错误')
            return False
        if extracted_dict[k] != v:
            print('模型提取 {k} 参数值错误')
            return False
    if len(answer_dict) != len(extracted_dict):
        print('模型提取非指定参数')
        return False
    return True

def read_from_excel_agent_memory_determine(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append({'ID': row['ID'], 'user_input': row['UserInput'], 'Input': row['Input'], 'test_answer': row['TestAnswer']})
    return test_cases

def read_from_excel_agent_memory_summary(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        test_answer = row['TestAnswer']
        subtopic = row['subtopic']
        test_cases.append({'ID': case_id, 'Input': input_data, 'test_answer': test_answer, 'subtopic': subtopic})
    return test_cases

def read_from_excel_forever_memory_extract(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append({'ID': row['ID'], 'user_input': row['UserInput'], 'hist': row['Hist'], 'test_answer': row['TestAnswer']})
    return test_cases

def read_from_excel_general_memory_determine(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append({'ID': row['ID'], 'UserInput': row['UserInput'], 'hist': row['hist']})
    return test_cases

def read_from_excel_general_memory_extract(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append({'ID': row['ID'], 'Input': row['Input']})
    return test_cases

def read_from_excel_general_memory_recall(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        test_cases.append({'ID': row['ID'], 'UserInput': row['UserInput']})
    return test_cases

def read_from_excel_memory_travel_hotel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        test_cases.append({'ID': case_id, 'input_hotelName': row['input_hotelName'], 'answer_hotelName': row['answer_hotelName']})
    return test_cases

def read_from_excel_memory_travel_time(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        case_id = row['ID']
        test_cases.append({'ID': case_id, 'input_departureTime': row['input_departureTime'], 'answer_departureTime': row['answer_departureTime']})
    return test_cases

def get_model_content_agent_memory_determine(input, user_input):
    input = input.replace("'", '"')
    return f'\n用户请求:\n{user_input}\n用户偏好:\n{input}'

def get_model_content_agent_memory_summary(input, suboptic):
    input = input.replace("'", '"')
    return f'\n### 关注维度\n{suboptic}\n### 历史数据\n{input}'

def get_model_content_forever_memory_extract(hist, user_input):
    user_input = user_input.replace("'", '"')
    hist = hist.replace("'", '"')
    return f'\n#### 用户输入\n{user_input}\n#### 历史数据\n{hist}'

def is_successful_agent_memory_determine(llmoutput, answer):
    logging.info(f"{'-' * 20} Checking LLMOutput {'-' * 20}")
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

def is_successful_agent_memory_summary(llmoutput, answer):
    print('~~~~~~~~~~~~~~~~~~~~')
    print(answer)
    print(llmoutput)
    print('~~~~~~~~~~~~~~~~~~~~')
    logging.info(f"{'-' * 20} Checking LLMOutput {'-' * 20}")
    answer = answer.replace('，', ',')
    if answer == 'Null' and llmoutput == 'null':
        return {'满意度': '非常满意', '评测依据': '模型回答包含所有关键字'}
    if answer == 'Null' and llmoutput != 'null':
        return {'满意度': '不满意', '评测依据': f'模型不应该输出总结'}
    answer_entities = [a.strip() for a in answer.split(',') if a.strip()]
    missing_key = []
    for entity in answer_entities:
        if entity not in llmoutput:
            missing_key.append(entity)
    if missing_key:
        return {'满意度': '不满意', '评测依据': f'模型缺少以下关键值：{missing_key}'}
    return {'满意度': '非常满意', '评测依据': '模型回答包含所有关键字'}

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

def is_successful_forever_memory_extract(llmoutput, answer):
    logging.info(f"{'-' * 20} Checking LLMOutput {'-' * 20}")
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

def is_successful_travel_hotel(LLM_answer, expected_answer):
    logging.info(f"{'-' * 20} Checking LLMOutput {'-' * 20}")
    logging.info(f'LLMOutput: {LLM_answer}')
    logging.info(f'Answer: {expected_answer}')
    expected_answer = expected_answer.replace('，', ',')
    try:
        LLM_answer = json.loads(LLM_answer)
        expected_answer = json.loads(expected_answer)
    except Exception as e:
        logging.error('字符串转化为JSON错误--' + str(e))
        print('模型输出格式有误')
        return False
    if len(LLM_answer) != len(expected_answer):
        print('LLM萃取错误')
        return False
    score = True
    error_reason = ''
    for key, value in expected_answer.items():
        if key not in LLM_answer:
            score = False
            error_reason = key + '未萃取出 '
        if LLM_answer[key] != value:
            score = False
            error_reason = key + '萃取错误 '
    if score:
        return score
    else:
        print(error_reason)
        return score

def is_successful_travel_time(LLM_answer, expected_answer):
    logging.info(f"{'-' * 20} Checking LLMOutput {'-' * 20}")
    logging.info(f'LLMOutput: {LLM_answer}')
    logging.info(f'Answer: {expected_answer}')
    expected_answer = expected_answer.replace('，', ',')
    try:
        LLM_answer = json.loads(LLM_answer)
        expected_answer = json.loads(expected_answer)
    except Exception as e:
        logging.error('字符串转化为JSON错误--' + str(e))
        print('模型输出格式有误')
        return False
    if len(LLM_answer) != len(expected_answer):
        print('LLM萃取错误')
        return False
    score = True
    error_reason = ''
    for key, value in expected_answer.items():
        if key not in LLM_answer:
            score = False
            error_reason = key + '未萃取出 '
        if LLM_answer[key] != value:
            score = False
            error_reason = key + '萃取错误 '
    if score:
        return score
    else:
        print(error_reason)
        return score
if __name__ == '__main__':
    result = '<think>\n好的，我现在需要处理用户的这个查询：“我这两天要从CTU出发去三亚，有什么机票订什么机票”。首先，根据规则，我需要识别用户的意图和任务类型。\n\n用户提到从CTU（应该是武汉的机场代码）出发去三亚，时间是“这两天”，这涉及到行程安排和机票预订。根据感知规则，出行类的任务属于TravelAgent，而订机票属于出行类的任务，所以应该归类到TravelAgent。\n\n接下来，任务分解。用户的需求是订机票，但并没有指定具体的时间、航班、航空公司或价格等细节。不过，用户提到了“这两天”，所以需要在context中明确时间要素，即这两天。同时，出发地是CTU，目的地是三亚。根据规则，时间要素必须显式包含在context中，所以这里需要明确时间。\n\n另外，用户的问题是“有什么机票订什么机票”，可能是在询问推荐或预订选项。但根据规则，订票属于TravelAgent的任务，不需要进一步分解，因为出行规划不涉及订票和酒店预订的话不需要分解，但这里用户明确提到了订票，所以应该分解为订机票的任务。\n\n检查是否有其他规则适用：比如系统类是否涉及？这里用户是在订票，属于明确的出行预订，所以不属于SysAgent。路由类也不相关。购物或外卖也不适用，因为是机票，属于出行类。\n\n数量方面，用户没有提到具体数量，但根据规则，如果是模糊请求如“订张”，数量为1，但这里用户没有用这样的词，所以可能不需要特别说明数量，但订机票通常默认是单程或往返，但用户没有说明，可能需要默认处理，但根据规则，任务分解需要精确提取需求，这里可能需要假设是单程，但用户没有明确，所以可能需要在context中保持原样，或者根据常规处理。不过根据规则，任务分解需要准确提取，但用户没有指定数量，可能这里不需要分解数量，但必须包含时间、地点等关键要素。\n\n另外，用户提到“这两天”，需要显式包含时间，所以context中必须包括时间。出发地CTU，目的地三亚，任务类型是订机票。\n\n所以，最终的JSON应该是一个列表，包含一个agent，类型是TravelAgent，context包括出发地、目的地、时间，以及订票的需求。可能需要将用户的问题转化为明确的订票请求，但用户没有指定航班或价格，所以context中可能需要保持原样，或者根据规则，是否需要进一步分解？但根据规则，复合请求分解为独立子任务，这里可能只有一个子任务，即订机票，包含时间、地点等要素。\n\n另外，检查是否有其他意图，比如用户可能在询问推荐，但根据规则，推荐类属于SysAgent，但这里用户是在订票，所以还是TravelAgent。因此，正确的处理是将整个请求归类到TravelAgent，分解为订机票的任务，包含时间、出发地、目的地。\n</think>\n```json\n[\n  {\n    "agent_name": "TravelAgent",\n    "context": "从CTU机场出发，两天内抵达三亚，订一张机票"\n  }\n]\n```'
    pred = get_json_structure(result)
    print(pred)
