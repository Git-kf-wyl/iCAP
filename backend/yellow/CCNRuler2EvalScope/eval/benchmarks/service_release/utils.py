# Private iCAP Yellow implementation. Do not publish.
"""工具调用数据集-过滤函数的util"""
import re
import json
from pprint import pprint
from dateutil import parser
from datetime import datetime, timedelta
import jionlp as jio
import pandas as pd

def process_results(answer, predict, question, subset_name):
    score = re.search('\\d+', predict)
    num = float(score.group())
    return {'emotion_chat': num}

def process_results_intent(answer, predict, raw_input_d, subset_name):
    if predict == answer:
        return True
    else:
        return False

def read_from_excel(style, filename):
    test_cases = []
    df = pd.read_csv(filename, encoding='GBK')
    for index, row in df.iterrows():
        input_data = row['用户问题']
        test_cases.append({'Style': style, 'Question': input_data})
    return test_cases

def remove_think(text):
    cleaned_text = re.sub('<think>.*?</think>', '', text, flags=re.DOTALL)
    return cleaned_text.strip()

def remove_question(text):
    cleaned_text = re.sub('Question:.*?\\n', '', text, flags=re.DOTALL)
    return cleaned_text.strip()

def extract_time(time_str):
    time_str = time_str.strip()
    formats = ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y/%m/%dT%H:%M:%S', '%Y/%m/%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y年%m月%d日 %H:%M:%S', '%Y年%m月%d日 %H:%M', '%Y年%m月%d日%H:%M:%S', '%Y年%m月%d日%H:%M', '%Y%m%d%H%M%S', '%Y%m%d%H%M']
    for fmt in formats:
        try:
            if fmt.startswith('%Y年'):
                normalized_str = time_str.replace('年0', '年').replace('月0', '月').replace('日0', '日')
                return datetime.strptime(normalized_str, fmt)
            else:
                return datetime.strptime(time_str, fmt)
        except ValueError as e:
            continue
        except Exception as e:
            continue
    return None

def eval_args_element_tool(pred_action, gt_args, pred_args, if_all_gt=True):
    """按照要素萃取来"""
    logs = {'pred_miss': [], 'pred_hallu': [], 'gt_miss': [], 'pred_error': []}
    if 'CALL' in gt_args and 'CALL' in pred_args:
        return (1, logs)
    elif 'CALL' in gt_args or 'CALL' in pred_args:
        return (0, logs)
    if isinstance(gt_args, dict):
        comp_params = list(gt_args.keys())
    else:
        comp_params = []
    if not if_all_gt:
        if pred_action == 1:
            comp_params = list(set(list(gt_args.keys())) & set(['title', 'time']))
        elif pred_action == 4:
            comp_params = list(set(list(gt_args.keys())) & set(['index', 'title', 'time']))
    for param in comp_params:
        '先判断要素的存在性'
        if param in pred_args:
            gt_val = gt_args[param]
            pred_val = pred_args[param]
        elif param in gt_args and param not in pred_args:
            print(f'预测：{param}要素丢失')
            logs['pred_miss'].append(param)
            continue
        '都存在再判断正确与否'
        if param == 'title' or param == 'location' or param == 'partners':
            continue
        elif param == 'time':
            try:
                gt_time = parser.parse(gt_val).strftime('%Y-%m-%d %H:%M:%S')
                pred_time = parser.parse(pred_val).strftime('%Y-%m-%d %H:%M:%S')
            except:
                try:
                    gt_time = extract_time(gt_val)
                    pred_time = extract_time(pred_val)
                except:
                    gt_time = gt_val
                    pred_time = pred_val
            if gt_time == pred_time:
                continue
            else:
                print(f'time，真值为{gt_time}，预测为{pred_time}')
                logs['pred_error'].append(param)
        elif param == 'index':
            list1 = gt_val.split(',')
            list2 = pred_val.split(',')
            list1 = sorted([x.strip() for x in list1])
            list2 = sorted([x.strip() for x in list2])
            if list1 != list2:
                logs['pred_error'].append(param)
        else:
            pass
            if gt_val.replace(' ', '') != pred_val.replace(' ', ''):
                logs['pred_error'].append(param)
    if logs['pred_error'] or logs['pred_miss']:
        return (0, logs)
    else:
        return (1, logs)

def extract_params(data):
    data = data.replace('\n', '')
    data = data.replace('`', '')
    data = data.replace('json', '')
    if 'CALL' in data:
        return (4, 'CALL')
    match = re.match('(\\d+):(.*)', data)
    match1 = re.match('输出：(\\d+):(.*)', data)
    if match:
        key = int(match.group(1))
        json_part = match.group(2)
    elif match1:
        key = int(match1.group(1))
        json_part = match1.group(2)
    elif '<easy>' in data or '<hard>' in data:
        data = data[12:]
        split_data = data.split(':', 1)
        key = int(split_data[0])
        json_part = split_data[1]
    else:
        split_data = data.split(':', 1)
        key = int(split_data[0])
        json_part = split_data[1]
    if json_part:
        try:
            parsed_data = eval(json_part)
            res = {}
            for item in parsed_data:
                if isinstance(item, dict) and (not isinstance(item['value'], str)):
                    print(item)
                    item['value'] = str(item['value'])
                if 'name' in item and 'value' in item:
                    res[item['name']] = item['value'].strip('\n')
            return (key, res)
        except:
            return (key, {})
    else:
        return (key, {})

def process_results_parameter_extract(answer, predict, raw_input_d, subset_name):
    try:
        gt_action, gt_args = extract_params(answer)
    except Exception as e:
        print(f'gt-{answer}，捕捉到错误{e}')
        gt_action, gt_args = (-1, [])
    try:
        pred_action, pred_args = extract_params(predict)
    except Exception as e:
        pred_action, pred_args = (-2, [])
        print(f'gt-{predict}，捕捉到错误{e}')
    flag_tool_pred = False
    flag_param_pred = False
    if gt_action == pred_action:
        flag_tool_pred = True
        if_all_gt = True
        count, logs = eval_args_element_tool(gt_action, gt_args, pred_args, if_all_gt)
        flag_param_pred = True if count == 1 else False
    for message in raw_input_d['messages']:
        if message['role'] == 'user':
            question = message['content']
    return flag_param_pred

def process_results_tool_select(answer, predict, raw_input_d, subset_name):
    try:
        gt_action, gt_args = extract_params(answer)
    except Exception as e:
        print(f'gt-{answer}，捕捉到错误{e}')
        gt_action, gt_args = (-1, [])
    try:
        pred_action, pred_args = extract_params(predict)
    except Exception as e:
        pred_action, pred_args = (-2, [])
        print(f'gt-{predict}，捕捉到错误{e}')
    flag_tool_pred = False
    flag_param_pred = False
    if gt_action == pred_action:
        flag_tool_pred = True
        if_all_gt = True
        count, logs = eval_args_element_tool(gt_action, gt_args, pred_args, if_all_gt)
        flag_param_pred = True if count == 1 else False
    for message in raw_input_d['messages']:
        if message['role'] == 'user':
            question = message['content']
    return flag_tool_pred
