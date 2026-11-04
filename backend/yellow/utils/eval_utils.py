from state_storage import open_state, state_exists, state_isfile
# Private iCAP Yellow business implementation. Do not publish.
import glob
import json
import os
import re
from datetime import datetime
import numpy as np
import pandas as pd
from flask import send_file, jsonify
from utils.consts import *
from utils.utils import get_encoding
BOX_BASE_DIR = 'outputs/aisf_box'
from services.aisf.function_call.constants import BASE_DIR as FC_BASE_DIR
from services.aisf.intent_category.constants import BASE_DIR as IC_BASE_DIR
from services.aisf.memory.constants import BASE_DIR as MEM_BASE_DIR
from services.aisf.perception_plan.constants import BASE_DIR as PP_BASE_DIR
from services.aisf.clarify.constants import CLARIFY_BASE_DIR_OUTPUT
from .utils import set_tasks

def generate_run_task_info(user_req, model_id, model_name, model_config, task_id):
    create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    base_info = {'ID': task_id, 'name': user_req['name'], 'model_id': model_id, 'model_name': model_name, 'modelType': model_config['info']['category'], 'datasets': user_req['datasets'], 'assessmentType': user_req['assessmentType'], 'status': 'running', 'progress': 0.0, 'createTime': create_time, 'creator': 'admin' if 'username' not in user_req else user_req['username'], 'runningTime': 0, 'description': user_req['description'] if 'description' in user_req else '', 'result': {model_config['info']['model_name']: [{'create_time': create_time, 'dataset_name': data_set, 'progress': 0, 'score': 0} for data_set in user_req['datasets']]}, 'taskConfig': {**user_req, 'use_cache': f'./outputs/{model_id}/{task_id}'}}
    return base_info

def extract_dataset_after_phrase(log_file_path, phrase='Start evaluating on dataset'):
    """
    在日志文件中查找最后一次包含指定短语的行，
    提取该短语后紧接的**第一个单词**（即一级测试集名称）。
    现存的问题就是运行程序在用尺子一跑和用尺子二跑的时候，Start evaluating on dataset后的并不总是数据集名称，尺子二的情况下会是含有/testsuite的路径，
    """
    pattern = re.compile('\\b' + re.escape(phrase) + '\\s+(\\S+)(?=\\s|$)')
    last_dataset = None
    try:
        encodings = get_encoding(log_file_path)
        with open_state(log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if phrase not in line:
                    continue
                match = pattern.search(line)
                if match:
                    last_dataset = match.group(1)
    except Exception as e:
        print(e)
    return last_dataset

def get_last_percentage_as_float(log_file_path):
    percent_pattern = re.compile(b'(\\d+(?:\\.\\d+)?)\\s*%')
    fraction_pattern = re.compile(b'(\\d+)/(\\d+)')
    try:
        with open_state(log_file_path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            buffer_size = 8192
            leftover = b''
            percent_match = None
            fraction_match = None
            while f.tell() > 0:
                read_size = min(buffer_size, f.tell())
                f.seek(-read_size, os.SEEK_CUR)
                chunk = f.read(read_size)
                f.seek(-read_size, os.SEEK_CUR)
                buffer = chunk + leftover
                lines = buffer.split(b'\n')
                for line in reversed(lines[:-1]):
                    percent_match = percent_pattern.search(line)
                    if percent_match:
                        return float(percent_match.group(1)) / 100.0
                    fraction_match = fraction_pattern.search(line)
                    if fraction_match:
                        numerator = int(fraction_match.group(1))
                        denominator = int(fraction_match.group(2))
                        if denominator != 0:
                            fraction_value = numerator / denominator
                            if fraction_value == 1.0:
                                return 0.99
                            else:
                                return fraction_value
                leftover = lines[0]
            if leftover:
                percent_match = percent_pattern.search(leftover)
                if percent_match:
                    return float(percent_match.group(1)) / 100.0
                fraction_match = fraction_pattern.search(leftover)
                if fraction_match:
                    numerator = int(fraction_match.group(1))
                    denominator = int(fraction_match.group(2))
                    if denominator != 0:
                        fraction_value = numerator / denominator
                        if fraction_value == 1.0:
                            return 0.99
                        else:
                            return fraction_value
    except FileNotFoundError:
        print(f'[ERROR] 文件不存在: {log_file_path}')
    except Exception as e:
        print(f'[ERROR] 读取文件时出错: {e}')
    return None

def update_eval_rate(tasks):
    for key, val in tasks.items():
        if val['status'] != 'running':
            continue
        model_id = val['model_id']
        task_id = key
        datasets = val['datasets']
        dataset_number = len(datasets)
        log_abspath = os.path.abspath(f'outputs/{model_id}/{task_id}/logs/eval_log.log')
        last_dataset = extract_dataset_after_phrase(log_abspath, 'Start evaluating on dataset')
        print(f'last_dataset: {last_dataset}')
        model_names = val['model_name'].split(';')
        results = val['result'][model_names[0]]
        last_sub_dataset = 0
        updated_progress = 0
        if last_dataset is not None:
            try:
                last_dataset_number = datasets.index(last_dataset)
            except ValueError:
                print(f"last_dataset '{last_dataset}' not found in datasets, fallback to percentage only")
                last_dataset = None
            last_sub_dataset = get_last_percentage_as_float(log_abspath)
            if last_dataset is not None:
                updated_progress = round((last_dataset_number + last_sub_dataset) / dataset_number, 2)
            elif last_sub_dataset is not None:
                updated_progress = round(last_sub_dataset, 2)
        else:
            last_sub_dataset = get_last_percentage_as_float(log_abspath)
            if last_sub_dataset is not None:
                updated_progress = round(last_sub_dataset, 2)
        val['progress'] = updated_progress
        if val['progress'] > 1:
            val['progress'] = 0.99
        elif val['progress'] < 0:
            val['progress'] = 0.0
        try:
            last_index = datasets.index(last_dataset)
        except ValueError:
            print(f"last_dataset '{last_dataset}' not found in dataset_names")
            last_index = -1
        REPORTS_PATH = f'outputs/{model_id}/{task_id}/reports/{model_id}'
        for result in results:
            dataset_name = result['dataset_name']
            try:
                current_index = datasets.index(dataset_name)
            except ValueError:
                continue
            if current_index < last_index:
                result['progress'] = 1.0
            elif current_index == last_index:
                result['progress'] = last_sub_dataset
            else:
                result['progress'] = 0.0
            report_path = os.path.join(REPORTS_PATH, f'{dataset_name}.json')
            if state_exists(report_path):
                try:
                    with open_state(report_path, 'r') as f:
                        report_data = json.load(f)
                    if 'score' in report_data:
                        result['score'] = report_data['score']
                    else:
                        print(f'警告: {dataset_name}.json 缺少score字段')
                        result['score'] = 0
                except Exception as e:
                    print(f'读取报告失败: {report_path}, 错误: {str(e)}')
                    result['score'] = 0
            else:
                result['score'] = 0

def get_report_file(datasets, task_id, user_name, users):
    dataset_to_dir = {'aisf_clarify_32b': CLARIFY_BASE_DIR_OUTPUT, 'aisf_box_scene_classify_4b': BOX_BASE_DIR + 'output/', 'aisf_box_param_extract_4b': BOX_BASE_DIR + 'output/', 'aisf_box_param_extract_32b': BOX_BASE_DIR + 'output/', 'aisf_box_bert': BOX_BASE_DIR + 'output/', 'aisf_functioncall_32b': FC_BASE_DIR + 'output/', 'aisf_intentcategory_32b': IC_BASE_DIR + 'output/', 'aisf_perceptionplan_32b': PP_BASE_DIR + 'output/', 'aisf_memory_forever_32b': MEM_BASE_DIR + 'output/', 'aisf_memory_travel_agent_8b': MEM_BASE_DIR + 'output/', 'aisf_memory_attribute_extract_8b': MEM_BASE_DIR + 'output/', 'aisf_memory_topic_8b': MEM_BASE_DIR + 'output/', 'aisf_memory_fact_8b': MEM_BASE_DIR + 'output/', 'aisf_memory_intent_classify_8b': MEM_BASE_DIR + 'output/', 'aisf_memory_32b_open': MEM_BASE_DIR + 'output/', 'aisf_memory_8b_open': MEM_BASE_DIR + 'output/'}
    for dataset in datasets:
        if dataset in dataset_to_dir:
            report_file = dataset_to_dir[dataset] + task_id + (AISF_RESULT_FILE if user_name in users else AISF_ERR_RESULT_FILE)
            if not state_exists(report_file):
                return (jsonify({'error': 'path is not exist'}), 400)
            return send_file(report_file, as_attachment=True)
    return (jsonify({'error': 'report path is not exist'}), 400)

def load_csv_score(file_path, column_name, convert_to_percent=False):
    try:
        df = pd.read_csv(file_path)
        value = float(df[column_name].mean())
        return round(value / (100 if convert_to_percent else 1), 4)
    except Exception as e:
        print(f'Error loading CSV file {file_path}: {e}')
        return None

def handle_nanhook(obj):
    for key, value in obj.items():
        if isinstance(value, str) and value.lower() == 'nan':
            obj[key] = None
    return obj

def load_json_score(file_path, key_name, convert_to_percent=False):
    try:
        with open_state(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f, object_hook=handle_nanhook)
        print(f'load_json_score, key_name: {key_name}')
        if key_name == 'overall':
            value = data.get(key_name, dict())
            if isinstance(value, dict):
                print(f'overall value is dict.')
                value = float(value.get(key_name, 0))
            elif isinstance(value, list):
                print(f'overall value is list.')
                value = round(float(value[2].rstrip('%')) / 100, 4) if len(value) == 3 else 0
            else:
                print(f'Unexpected score json, {data}')
                value = 0
        else:
            value = data.get(key_name, 0)
        return round(value / (100 if convert_to_percent else 1), 4)
    except Exception as e:
        print(f'Error loading JSON file {file_path}: {e}')
        return None

def get_dataset_handlers(model_name):
    dataset_handlers = {'MMMU': {'pattern': f'{model_name}_MMMU_DEV_VAL_acc.csv', 'loader': load_csv_score, 'args': ('Overall', False)}, 'HallusionBench': {'pattern': f'{model_name}_HallusionBench_score.csv', 'loader': load_csv_score, 'args': ('aAcc', True)}, 'MMStar': {'pattern': f'{model_name}_MMStar_acc.csv', 'loader': load_csv_score, 'args': ('Overall', False)}, 'OCRBench': {'pattern': f'{model_name}_OCRBench_score.json', 'loader': load_json_score, 'args': ('Final Score Norm', True)}, 'ScreenSpot_Pro': {'pattern': f'{model_name}_ScreenSpot_Pro_*_score.json', 'loader': lambda pattern: round(np.nanmean([load_json_score(file, 'Overall_Accuracy', True) for file in glob.glob(pattern) if file]), 4)}, 'WorldSense': {'pattern': f'{model_name}_WorldSense_rating.json', 'loader': load_json_score, 'args': ('overall', False)}, 'Video-MME': {'pattern': f'{model_name}_Video-MME_rating.json', 'loader': load_json_score, 'args': ('overall', False)}, 'MVBench': {'pattern': f'{model_name}_MVBench_rating.json', 'loader': load_json_score, 'args': ('overall', False)}}
    return dataset_handlers

def update_vlm_res(tasks, task_id, model_name, model_id):
    if model_id:
        expected_dir = f'outputs/{model_id}/{task_id}/reports/{os.path.basename(model_id)}'
        expected_names = tasks[task_id].get('datasets', [])
        if not expected_names or not all(state_isfile(os.path.join(expected_dir, f'{name}.json')) for name in expected_names):
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = '执行器没有生成完整评测结果，请检查数据集格式和运行日志'
            set_tasks(tasks)
            return
    tasks[task_id]['status'] = 'completed'
    tasks[task_id]['progress'] = 1.0
    print(f'update_vlm_res start.')
    model_id_basename = os.path.basename(model_id).rstrip(os.sep)
    report_path = f'outputs/{model_id}/{task_id}/{model_id_basename}'
    print(f'update_vlm_res report_path: {report_path}')
    for model_node in tasks[task_id]['result'][model_name]:
        try:
            dataset_name = model_node['dataset_name']
            print(f'update_vlm_res idx:{model_node},dataset_name:{dataset_name}')
            file_prefix = model_id_basename
            cur_dataset_handlers = get_dataset_handlers(file_prefix)
            if dataset_name in cur_dataset_handlers:
                handler = cur_dataset_handlers[dataset_name]
                pattern = os.path.join(report_path, handler['pattern'])
                if dataset_name == 'ScreenSpot_Pro':
                    model_node['score'] = handler['loader'](pattern)
                else:
                    file_path = pattern
                    if state_exists(file_path):
                        print(f'file_path exist, {file_path}')
                        model_node['score'] = handler['loader'](file_path, *handler['args'])
            elif dataset_name in MLLM_CUSTOM_DATASETS:
                json_file = os.path.join(report_path, f'{dataset_name}.json')
                if state_exists(json_file):
                    try:
                        with open_state(json_file, 'r', encoding='utf-8') as f:
                            dataset_report_info = json.load(f)
                        model_node.update({k: v for k, v in dataset_report_info.items()})
                    except Exception as e:
                        print(f'Error loading custom dataset JSON: {e}')
            else:
                print(f'This is an unexpected dataset, {dataset_name}.')
                model_node['score'] = 0
        except FileNotFoundError as e:
            print(f'File not found: {e}')
            model_node['score'] = 0
        except json.JSONDecodeError as e:
            print(f'JSON decode error: {e}')
            model_node['score'] = 0
        except Exception as e:
            print(f'Unexpected error: {e}')
            model_node['score'] = 0
        finally:
            model_node['progress'] = 1.0

def update_eval_res(tasks, task_id, model_name, model_id):
    if tasks[task_id]['status'] != 'running':
        return
    tasks[task_id]['status'] = 'completed'
    tasks[task_id]['progress'] = 1.0
    set_tasks(tasks)
    if not model_id:
        return
    model_id_basename = os.path.basename(model_id).rstrip(os.sep)
    report_path = f'outputs/{model_id}/{task_id}/reports/{model_id_basename}'
    if not state_exists(report_path):
        print('report path does not exist.')
        return
    model_reports = [i for i in os.listdir(report_path)]
    for idx in range(len(model_reports)):
        dataset_name = tasks[task_id]['result'][model_name][idx]['dataset_name']
        try:
            json_file = os.path.join(report_path, f'{dataset_name}.json')
            with open_state(json_file, 'r', encoding='utf-8') as f:
                dataset_report_info = json.load(f)
            tasks[task_id]['result'][model_name][idx].update({k: v for k, v in dataset_report_info.items()})
        except:
            tasks[task_id]['result'][model_name][idx]['score'] = 0
        tasks[task_id]['result'][model_name][idx]['progress'] = 1.0
    set_tasks(tasks)

def get_need_model_config(param_list, key):
    for param in param_list:
        if param['key'] == key:
            return param['value']
    return None

def get_generate_config(cfg_list, model_name):
    res = {}
    for cfg in cfg_list:
        key = cfg.get('key')
        value = cfg.get('value')
        if key.lower() == 'enable_thinking' and 'qwen3.' in model_name.lower():
            print(f'enable_thinking={value}')
            if value.lower() in ('0', 'false'):
                res['chat_template_kwargs'] = {'enable_thinking': False}
        else:
            res[key] = value
    print(f'get_generate_config: {res}')
    return res

def get_metric(dataset_name, type='common', index=0):
    testcase_file = COMMON_TESTCASE_PATH if type == 'common' else FILED_TESTCASE_PATH
    with open_state(testcase_file, 'r', encoding='utf-8') as f:
        testcase_cfg = json.load(f)
    for key, val in testcase_cfg.items():
        if key == dataset_name:
            return val['metric_list']
    raise ValueError(f'{dataset_name} not registered! please check!')

def get_dataset_args(model_cfg, opensource_testcases, metric_list, user_dataset_arg, user_all_arg=None, is_dev=False):
    dataset_args = {}
    dataset_name = user_dataset_arg['dataset_name']
    for case_name, case_info in opensource_testcases.items():
        if case_name == dataset_name:
            dataset_args[case_name] = {'few_shot_num': case_info['few_shot_num'], 'metric_list': metric_list}
            if model_cfg['config']['filter']['tail']:
                dataset_args[case_name]['filters'] = {'remove_until': model_cfg['config']['filter']['tail']}
            if 'local_path' in case_info:
                dataset_args[case_name]['local_path'] = case_info['local_path']
            if 'input_path' in case_info:
                dataset_args[case_name]['input_path'] = case_info['input_path']
            if user_dataset_arg is not None and 'subset_list' in user_dataset_arg and user_dataset_arg['subset_list']:
                dataset_args[case_name].update({'subset_list': user_dataset_arg['subset_list']})
            if 'extra_params' in case_info:
                if user_all_arg is not None and 'extra_params' in user_all_arg:
                    dataset_args[case_name].update({'extra_params': user_all_arg['extra_params']})
                else:
                    dataset_args[case_name].update({'extra_params': case_info['extra_params']})
            dataset_args[case_name].update({'testcase_tags': case_info['testcase_tags']})
            try:
                if user_dataset_arg is not None and 'system_prompt' in user_dataset_arg and is_dev:
                    dataset_args[case_name].update({'system_prompt': user_dataset_arg['system_prompt']})
                else:
                    dataset_args[case_name].update({'system_prompt': case_info['system_prompt']})
            except BaseException as e:
                print('get system_prompt error: ', e)
            print('user_dataset_arg: ', user_dataset_arg)
            break
    return dataset_args

def get_limit(user_limit):
    if isinstance(user_limit, int) and user_limit > 0:
        return user_limit
    if isinstance(user_limit, str):
        try:
            int_limit = int(user_limit)
            if int_limit > 0:
                return int_limit
        except Exception as e:
            print('user_limit str to int error: ', e)
            return None
    return None
