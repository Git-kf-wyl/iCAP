# Private iCAP Yellow business implementation. Do not publish.
import queue
import threading
import time
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import glob
import re
import json
import pandas as pd
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
module_path = os.path.join(current_dir, '../../backend')
if module_path not in sys.path:
    sys.path.append(module_path)
from server import *
from call_api import *
from utils.consts import *
from utils.utils import *
from utils.eval_utils import *
TRANSLATE_DIRECTION = {'enar': ['英文', '阿语'], 'aren': ['阿语', '英文'], 'then': ['泰语', '英文'], 'enth': ['英文', '泰语'], 'chth': ['中文', '泰语'], 'thch': ['泰语', '中文'], 'chen': ['中文', '英文'], 'ench': ['英文', '中文']}
TRANSLATE_DIRECTION_WORD = {'enar': ['English', 'Arabic'], 'aren': ['Arabic', 'English']}

def init_simu_inter_task_path(model_id, task_id):
    model_id_basename = os.path.basename(model_id).rstrip(os.sep)
    log_path = f'outputs/{model_id}/{task_id}/logs'
    review_path = f'outputs/{model_id}/{task_id}/reviews/{model_id_basename}'
    os.makedirs(log_path, exist_ok=True)
    os.makedirs(review_path, exist_ok=True)
    return (log_path, review_path)

def call_include_files(url, files):
    """发送带文件的POST请求，自动管理文件资源"""
    session = requests.Session()
    retry_strategy = Retry(total=3, status_forcelist=[], allowed_methods=['POST'], backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    try:
        response = session.post(url, files=files, timeout=(30, 3600))
        try:
            return (response.json(), response.status_code)
        except json.JSONDecodeError:
            return ({'message': f'服务端返回无效JSON: {response.text[:200]}', 'success': False}, 500)
    except FileNotFoundError as e:
        return ({'message': f'文件未找到: {str(e)}', 'success': False}, 404)
    except requests.exceptions.Timeout:
        return ({'message': '请求超时(3600秒)，请稍后再试', 'success': False}, 504)
    except requests.exceptions.RequestException as e:
        return ({'message': f'网络请求失败: {str(e)}', 'success': False}, 500)
    except Exception as e:
        return ({'message': f'未处理异常: {str(e)}', 'success': False}, 500)

def call_with_payload(url, payload):
    try:
        response = requests.post(url, json=payload)
        json_resp = response.json()
        status_code = response.status_code
    except requests.exceptions.RequestException as e:
        json_resp = {'message': f'请求失败{str(e)}', 'success': False}
        status_code = 500
    except Exception as e:
        json_resp = {'message': f'未知错误{str(e)}', 'success': False}
        status_code = 500
    return (json_resp, status_code)

def interleave_files(file1, output_file):
    """
    从两个文件中交替读取一行并写入到输出文件中。
    :param file1: 第一个文件的文件对象
    :param file2: 第二个文件的文件对象
    :param output_file: 输出文件的文件对象
    """
    line1 = file1.readline()
    while line1:
        if line1:
            output_file.write(line1)
            line1 = file1.readline()

def filename_trans(file1, outputfile):
    with open(file1, 'r', encoding='utf-8') as f1, open(outputfile, 'w', encoding='utf-8') as output_file:
        interleave_files(f1, output_file)

def remove_arabic_punctuation(text):
    arabic_punctuation = {'،', '"', '!', '.', ',', '?', '؛', ',', '؟', '۔', '٪', 'ـ'}
    return ''.join([c for c in text if c not in arabic_punctuation])

def process_line_chinese(line, output_file):
    """
    处理单行文本：
    - 如果行中包含 ".wav"，保留原样
    - 否则：
        - 保留所有汉字（逐字一行）
        - 保留所有英文单词（逐词一行）
        - 整行处理完成后，最后加一个 `.`（单独一行）
    """
    line = line.strip()
    all_punctuation = '[!"#$%&\\\'()*+,\\-\\\\/:;<=>?@[\\$\\^`{\\|}~，。！？；：“”‘’《》【】（）〔〕…—～·、]'
    line = re.sub(all_punctuation, '', line)
    if line:
        if line.endswith('wav'):
            output_file.write('.')
            output_file.write('\n')
            line_new = line.split('.')[0]
            output_file.write(line_new + '.wav\n')
        else:
            for word in line:
                output_file.write(word)
                output_file.write('\n')

def process_line(line, output_file):
    """
    处理单行文本，如果行中不包含 ".wav"，则将中英文按空格分割后竖着排列，
    去掉标点符号，并写入到输出文件中。
    """
    res_lines = []
    if '.wav' not in line:
        line = line.replace('/', ' ')
        line = line.replace('\\(', '')
        line = line.replace('\\)', '')
        line = line.replace('\\:', '')
        line = remove_arabic_punctuation(line)
        words = line.split()
        for word in words:
            word = word.lower()
            output_file.write(word + '\n')
            res_lines.append(word)
        output_file.write('.\n')
        res_lines.append('.')
    else:
        line_new = line.split('.')[0].split('/')[-1]
        output_file.write(line_new + '.wav\n')
        res_lines.append(line_new + '.wav')
    return res_lines

def generate_non_tokenized_asr_text(target_path, input_dict):
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    for result in input_dict:
        with open(target_path, 'a', encoding='utf-8') as f:
            f.write(result['file'] + '\n')
            f.write(result['asr_result'] + '\n')

def generate_tokenized_asr_text(non_tokenized_file, target_path):
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    res_lines = ['.']
    with open(non_tokenized_file, 'r', encoding='utf-8') as input_file, open(target_path, 'w', encoding='utf-8') as output_file:
        output_file.write('.\n')
        for line in input_file:
            curr_lines = process_line(line, output_file)
            res_lines += curr_lines
    return res_lines

def generate_asr_jsonl(case_eval_res, review_path, jsonl_res_file):
    jsonl_name = os.path.join(review_path, jsonl_res_file)
    idx = 0
    with open(jsonl_name, 'w', encoding='utf-8') as f:
        for key, entry in case_eval_res.items():
            formatted = {'choices': [{'index': 0, 'message': {'content': f"file_name: {key}, H: {entry['H']}, D: {entry['D']}, S: {entry['S']}, I:{entry['I']}, N: {entry['N']}; Accuracy Score: {entry['score']};Correct Score: {entry['correct']}"}, 'review': {'pred': entry['REC'], 'result': entry['score'] >= 99.0, 'accuracy': round(entry['score'] / 100, 4), 'correct': round(entry['correct'] / 100, 4)}}], 'raw_input': {'Question': key, 'Answer': entry['LAB']}, 'index': idx}
            f.write(json.dumps(formatted, ensure_ascii=False) + '\n')
            idx += 1

def common_api(model_cfg, system_prompt, query, config, req_cfg=None):
    try:
        model_name = model_cfg['model_id'].split('/')[-1]
        payload = {'model': model_name, 'messages': [{'role': 'system', 'content': 'You are a speech recognition model'}, {'role': 'user', 'content': query}]}
        headers = {'Content-Type': 'application/json'}
        if 'params' in config.keys():
            update_model_params(payload, config['params'])
        if req_cfg is not None:
            update_model_params(payload, req_cfg)
        print(f'开始发送请求:')
        r = requests.post(url=config['endpoint'], json=payload, headers=headers)
        if r.status_code == 200:
            return json.loads(r.text)['choices'][0]['message']['content']
        else:
            raise ConnectionError(f'Failed to connect to {model_name}')
    except Exception as e:
        print(f'调用common_api出错：{e}')
        return ''

def get_response_chat(model_cfg, query_content, req_cfg=None):
    config_available_list = model_cfg['config']['api_params_available']
    config_available = random.choice(config_available_list)
    model_func = model_cfg['info']['model_name'].strip()
    model_function = globals().get(model_func)
    if not callable(model_function):
        return common_api(model_cfg, '', query_content, config_available, req_cfg)
    true_url = config_available['endpoint']
    print('true_url', true_url)
    if config_available['is_openai_format']:
        return model_function(model_cfg, '', query_content, true_url)
    else:
        return model_function(model_cfg, '', query_content, true_url, req_cfg)

def generate_response(eval_log, wav_path, user_req_asr, endpoint):
    model_id = user_req_asr.get('model_id', [])
    language = user_req_asr.get('language', '')
    model_config = get_one_model_config(model_id)
    if not model_config:
        return ({'errType': f'Model ({model_path}) not registered'}, 400)
    req_cfg = None
    if 'config' in user_req_asr:
        req_cfg = user_req_asr['config']
    file_str = audio_to_base64_url(f'/home/aisf/w00649384/{wav_path}')
    text_str = f'Recognize this .wav file as text, in {language}, output only the converted text, do not output any other content.'
    model_resp = get_response_chat(model_config, [{'type': 'text', 'text': text_str}, {'type': 'audio_url', 'audio_url': {'url': file_str}}], req_cfg)
    return model_resp

def local_asr_eval(endpoint, user_req_asr, task_id, tasks, all_start_time):
    model_id = user_req_asr.get('model_id', [])
    datasets = user_req_asr.get('datasets', [])
    label = user_req_asr.get('label', '')
    language = user_req_asr.get('language', '')
    model_config = get_one_model_config(model_id)
    model_name = model_config['info']['model_name']
    is_ip_port = classify_url(endpoint)
    tasks[task_id] = generate_run_task_info(user_req_asr, model_id, model_name, model_config, task_id)
    set_tasks(tasks)
    log_path, review_path = init_simu_inter_task_path(model_id, task_id)
    task_path = f'outputs/{model_id}/{task_id}'
    main_log_path = os.path.join(log_path, 'eval_log.log')
    with open(main_log_path, 'a', encoding='utf-8') as eval_log:
        eval_log.write(f'开始写入日志：{main_log_path}\n')
        eval_log.flush()
        if not datasets:
            eval_log.write('警告：datasets参数为空！\n')
            eval_log.flush()
        idx = 0
        all_tokenized_lines = []
        for case in datasets:
            try:
                case_path = os.path.join(SIMU_INTERPRETATION_ASR, case)
                eval_log.write(f'当前用例路径: {case_path}\n')
                eval_log.flush()
                wav_files = []
                for root, dirs, files in os.walk(case_path):
                    for file in files:
                        if file.lower().endswith('.wav'):
                            wav_path = os.path.join(root, file)
                            wav_files.append(wav_path)
                eval_log.write(f'找到 {len(wav_files)} 个.wav文件\n')
                eval_log.flush()
                all_results = []
                for wav_path in wav_files:
                    eval_log.write(f'{wav_path}文件发送请求\n')
                    eval_log.flush()
                    model_resp = generate_response(eval_log, wav_path, user_req_asr, endpoint)
                    result = model_resp
                    if model_config['config']['filter']['tail']:
                        result = model_resp.split(model_config['config']['filter']['tail'])[-1]
                        think = model_resp.split(model_config['config']['filter']['tail'])[0].split(model_config['config']['filter']['head'])[-1]
                    if model_name == 'OmniVinci':
                        eval_log.write(f'{wav_path}文件原生响应：{result}\n')
                        pattern = "'(.*)'\\."
                        match = re.search(pattern, result)
                        result = match.group(1) if match else result
                    eval_log.write(f'{wav_path}文件的响应：{result}\n')
                    eval_log.flush()
                    all_results.append({'file': wav_path.split('/')[-1], 'asr_result': result})
                eval_log.write(f'dataset: {case} 处理完成, 共收到{len(all_results)}条结果\n')
                eval_log.flush()
                all_end_time = time.time()
                tasks[task_id]['runningTime'] = all_end_time - all_start_time
                if not all_results:
                    tasks[task_id]['status'] = 'failed'
                    eval_log.write(f'警告: {case} 无有效结果\n')
                    eval_log.flush()
                    continue
                non_tokenized_file = os.path.join(task_path, 'asr_result/non_tokenize', case.replace('\\', '_').replace('/', '_') + '.txt')
                generate_non_tokenized_asr_text(non_tokenized_file, all_results)
                tokenized_file = os.path.join(task_path, 'asr_result/tokenize', case.replace('\\', '_').replace('/', '_') + '.txt')
                tokenized_lines = generate_tokenized_asr_text(non_tokenized_file, tokenized_file)
                all_tokenized_lines = all_tokenized_lines + tokenized_lines
                payload = {'type': case.split('/')[2], 'asr_resp': tokenized_lines, 'label': label}
                eval_log.write(f'{os.path.basename(non_tokenized_file)} 写入成功\n')
                eval_log.flush()
                resp = requests.request(method='POST', url='http://127.0.0.1:1/unconfigured', json=payload)
                idx += 1
                if resp.status_code == 200:
                    eval_log.write(f'评估结果(全部信息)：{resp.json()}\n')
                    case_eval_res = resp.json()['detail']
                    eval_log.write(f'生成JSON文件：{case}\n')
                    eval_log.flush()
                    generate_asr_jsonl(case_eval_res, review_path, case.replace('\\', '_').replace('/', '_') + '.jsonl')
                    try:
                        resp_data = resp.json()
                        summary = resp_data['summary']
                        if 'WORD' in summary and 'accuracy' in summary['WORD']:
                            score = summary['WORD']['accuracy'] / 100
                        else:
                            raise KeyError('无法获取评分: 无WORD')
                        update_asr_eval_res(tasks, task_id, model_name, score, case, idx / len(datasets))
                        set_tasks(tasks)
                    except Exception as e:
                        tasks[task_id]['status'] = 'failed'
                        tasks[task_id]['error'] = str(e)
                        eval_log.write(f'更新任务状态失败: {str(e)}\n')
                else:
                    tasks[task_id]['status'] = 'failed'
                    eval_log.write(f'评估请求失败: {resp.status_code}\n')
                    break
            except Exception as e:
                tasks[task_id]['status'] = 'failed'
                eval_log.write(f'处理用例 {case} 时出错: {str(e)}\n')
                eval_log.flush()
    set_tasks(tasks)
    trans_jsonl_to_csv(review_path)
    return ({}, 200)

def process_large_file_async(file_path, results_container, log, batch_idx, async_url, poll_url_template, async_get_result):
    try:
        basename = os.path.basename(file_path)
        log.write(f'开始异步处理超大文件: {basename}\n')
        log.flush()
        with open(file_path, 'rb') as audio_file:
            files = [('files', (basename, audio_file, 'audio/x-wav'))]
            response = requests.post(async_url, files=files)
            if response.status_code != 202:
                log.write(f'异步请求失败: HTTP {response.status_code}\n')
                return
            task_id = response.json().get('task_id')
            if not task_id:
                log.write(f'未获取到异步任务ID\n')
                return
        poll_url = poll_url_template.format(task_id=task_id)
        start_time = time.time()
        timeout = 3600
        while True:
            if time.time() - start_time > timeout:
                log.write(f'轮询超时: {basename}\n')
                break
            poll_response = requests.get(poll_url)
            if poll_response.status_code == 200:
                data = poll_response.json()
                status = data.get('status')
                if status == 'completed':
                    download_url = async_get_result.format(task_id=task_id)
                    download_response = requests.get(download_url)
                    if download_response.status_code == 200:
                        download_data = download_response.json()
                        download_status = download_data.get('status')
                        if download_status == 'success':
                            if 'result' in download_data and isinstance(download_data['result'], list):
                                results_container.extend(download_data['result'])
                                log.write(f'成功获取异步处理结果: {basename}\n')
                            else:
                                log.write(f'异步响应格式错误: {basename}\n')
                        else:
                            log.write(f'异步响应状态错误: {basename}\n')
                elif status == 'processing':
                    log.write(f'处理中: {basename} - 等待重试...\n')
                    time.sleep(5)
                else:
                    log.write(f'处理失败: {basename} - 状态: {status}\n')
                    break
            else:
                log.write(f'轮询失败: HTTP {poll_response.status_code}\n')
                time.sleep(5)
    except Exception as e:
        log.write(f'处理超大文件异常: {str(e)}\n')
    finally:
        log.flush()

def process_current_batch(batch_files, batch_idx, results_container, log, url):
    file_objects = []
    files_tuples = []
    total_size = 0
    for item in batch_files:
        files_tuples.append(item['file_tuple'])
        file_objects.append(item['file_obj'])
        total_size += item['size']
    log.write(f'开始同步处理第{batch_idx}批文件 (共{len(batch_files)}个文件, 总大小{total_size}字节)\n')
    process_files(files_tuples, file_objects, results_container, log, batch_idx, url)

def process_files(files_list, file_objects, results_container, log, batch_idx, url):
    if files_list:
        try:
            log.write(f'发送第{batch_idx}批请求\n')
            log.flush()
            json_resp, status_code = call_include_files(url, files_list)
            log.write(f'第{batch_idx}批响应: [状态 {status_code}] {json.dumps(json_resp)[:300]}\n')
            log.flush()
            if 'result' in json_resp and isinstance(json_resp['result'], list):
                results_container.extend(json_resp['result'])
            else:
                log.write(f'第{batch_idx}批响应格式错误\n')
        except Exception as e:
            log.write(f'第{batch_idx}批请求失败: {str(e)}\n')
    else:
        log.write(f'第{batch_idx}批无有效文件\n')
    for file_obj in file_objects:
        try:
            file_obj.close()
        except:
            pass

def run_asr_eval(task_id, user_req):
    tasks = get_tasks()
    all_start_time = time.time()
    print('开始执行ASR测评---------------------------')
    user_req_asr = user_req.get('asr', None)
    if not user_req_asr:
        return ({'message': '未识别到asr参数', 'success': False}, 500)
    cascadeMT = user_req.get('mt', None) is not None
    cascadeTTS = user_req.get('tts', None) is not None
    user_req_asr['name'] = user_req['task_name']
    user_req_asr['assessmentType'] = 'ASR+MT+TTS' if cascadeTTS else 'ASR+MT' if cascadeMT else 'ASR'
    model_id = user_req_asr.get('model_id', [])
    datasets = user_req_asr.get('datasets', [])
    label = user_req_asr.get('label', '')
    language = user_req_asr.get('language', '')
    model_config = get_one_model_config(model_id)
    model_name = model_config['info']['model_name']
    try:
        endpoint = model_config['config']['api_params_available'][0]['endpoint']
    except:
        endpoint = ASR_EVAL_URL
    isTHEASR = '10.185.236.110' in endpoint
    if isTHEASR:
        url = endpoint + f'folder_asr_result?property={language}_16k_general'
        try:
            api_params = model_config['config']['api_params_available']
            api_param = api_params[1] if len(api_params) > 1 else api_params[0]
            endpoint = api_param.get('endpoint', '')
            async_url = f'{endpoint}folder_asr_result?property={language}_16k_general'
            POLL_URL_TEMPLATE = f'{endpoint}folder_asr_status/{{task_id}}'
            async_get_result = f'{endpoint}folder_asr_download{{task_id}}'
        except (KeyError, IndexError) as e:
            return ({'message': f'节点配置获取失败: {str(e)}', 'success': False}, 500)
        tasks[task_id] = generate_run_task_info(user_req_asr, model_id, model_name, model_config, task_id)
        set_tasks(tasks)
        log_path, review_path = init_simu_inter_task_path(model_id, task_id)
        task_path = f'outputs/{model_id}/{task_id}'
        main_log_path = os.path.join(log_path, 'eval_log.log')
        with open(main_log_path, 'a', encoding='utf-8') as eval_log:
            eval_log.write(f'开始写入日志：{main_log_path}\n')
            eval_log.flush()
            if not datasets:
                eval_log.write('警告：datasets参数为空！\n')
                eval_log.flush()
            idx = 0
            all_tokenized_lines = []
            for case in datasets:
                try:
                    case_path = os.path.join(SIMU_INTERPRETATION_ASR, case)
                    eval_log.write(f'当前用例路径: {case_path}\n')
                    eval_log.flush()
                    wav_files = glob.glob(os.path.join(case_path, '*.wav'))
                    if not wav_files:
                        eval_log.write(f'警告: 目录中没有找到WAV文件\n')
                        eval_log.flush()
                    else:
                        eval_log.write(f'成功找到{len(wav_files)}个WAV文件\n')
                        eval_log.flush()
                    all_results = []
                    max_batch_size_bytes = 50 * 1024 * 1024
                    current_batch_files = []
                    current_batch_size = 0
                    batch_count = 0
                    for f in wav_files:
                        try:
                            file_size = os.path.getsize(f)
                        except Exception as e:
                            eval_log.write(f'获取文件大小失败: {f}, 错误: {str(e)}\n')
                            eval_log.flush()
                            continue
                        if file_size > max_batch_size_bytes:
                            if current_batch_files:
                                batch_count += 1
                                process_current_batch(current_batch_files, batch_count, all_results, eval_log, url)
                                current_batch_files = []
                                current_batch_size = 0
                            batch_count += 1
                            eval_log.write(f'添加超大文件到异步处理: {os.path.basename(f)} (大小: {file_size}字节)\n')
                            process_large_file_async(f, all_results, eval_log, batch_count, async_url, POLL_URL_TEMPLATE, async_get_result)
                            continue
                        if current_batch_size + file_size > max_batch_size_bytes:
                            if current_batch_files:
                                batch_count += 1
                                process_current_batch(current_batch_files, batch_count, all_results, eval_log, url)
                                current_batch_files = []
                                current_batch_size = 0
                        try:
                            audio_file = open(f, 'rb')
                            current_batch_files.append({'file_obj': audio_file, 'file_tuple': ('files', (os.path.basename(f), audio_file, 'audio/x-wav')), 'size': file_size})
                            current_batch_size += file_size
                            eval_log.write(f'添加文件到批次: {os.path.basename(f)} (大小: {file_size}字节)\n')
                        except Exception as e:
                            eval_log.write(f'打开文件 {f} 失败: {str(e)}\n')
                            eval_log.flush()
                    if current_batch_files:
                        batch_count += 1
                        process_current_batch(current_batch_files, batch_count, all_results, eval_log, url)
                    eval_log.write(f'dataset: {case} 处理完成, 共收到{len(all_results)}条结果\n')
                    eval_log.flush()
                    all_end_time = time.time()
                    tasks[task_id]['runningTime'] = all_end_time - all_start_time
                    if not all_results:
                        tasks[task_id]['status'] = 'failed'
                        eval_log.write(f'警告: {case} 无有效结果\n')
                        eval_log.flush()
                        continue
                    non_tokenized_file = os.path.join(task_path, 'asr_result/non_tokenize', case.replace('\\', '_').replace('/', '_') + '.txt')
                    generate_non_tokenized_asr_text(non_tokenized_file, all_results)
                    tokenized_file = os.path.join(task_path, 'asr_result/tokenize', case.replace('\\', '_').replace('/', '_') + '.txt')
                    tokenized_lines = generate_tokenized_asr_text(non_tokenized_file, tokenized_file)
                    all_tokenized_lines = all_tokenized_lines + tokenized_lines
                    payload = {'type': case.split('/')[2], 'asr_resp': tokenized_lines, 'label': label, 'is_the_ASR': isTHEASR}
                    eval_log.write(f'{os.path.basename(non_tokenized_file)} 写入成功\n')
                    eval_log.flush()
                    resp = requests.request(method='POST', url='http://127.0.0.1:1/unconfigured', json=payload)
                    idx += 1
                    if resp.status_code == 200:
                        eval_log.write(f'评估结果(全部信息)：{resp.json()}\n')
                        case_eval_res = resp.json()['detail']
                        eval_log.write(f'评估结果：{case_eval_res}\n')
                        eval_log.write(f'生成JSON文件：{case}\n')
                        eval_log.flush()
                        generate_asr_jsonl(case_eval_res, review_path, case.replace('\\', '_').replace('/', '_') + '.jsonl')
                        try:
                            resp_data = resp.json()
                            summary = resp_data['summary']
                            if 'WORD' in summary and 'accuracy' in summary['WORD']:
                                score = summary['WORD']['accuracy'] / 100
                            else:
                                raise KeyError('无法获取评分: 无WORD')
                            update_asr_eval_res(tasks, task_id, model_name, score, case, idx / len(datasets))
                            set_tasks(tasks)
                        except Exception as e:
                            tasks[task_id]['status'] = 'failed'
                            tasks[task_id]['error'] = str(e)
                            eval_log.write(f'更新任务状态失败: {str(e)}\n')
                    else:
                        tasks[task_id]['status'] = 'failed'
                        eval_log.write(f'评估请求失败: {resp.status_code}\n')
                        break
                except Exception as e:
                    tasks[task_id]['status'] = 'failed'
                    eval_log.write(f'处理用例 {case} 时出错: {str(e)}\n')
                    eval_log.flush()
            all_payload = {'type': 'all', 'asr_resp': all_tokenized_lines, 'label': label, 'is_the_ASR': isTHEASR}
            eval_log.flush()
            resp = requests.request(method='POST', url='http://127.0.0.1:1/unconfigured', json=all_payload)
            if resp.status_code == 200:
                case_eval_res = resp.json()['detail']
                eval_log.write(f'生成全集JSON文件：all\n')
                eval_log.flush()
                generate_asr_jsonl(case_eval_res, review_path, 'all.jsonl')
                try:
                    resp_data = resp.json()
                    summary = resp_data['summary']
                    if 'WORD' in summary and 'accuracy' in summary['WORD']:
                        score = summary['WORD']['accuracy'] / 100
                    else:
                        raise KeyError('无法获取评分: 无WORD')
                    update_asr_eval_res(tasks, task_id, model_name, score, 'all', 1)
                    set_tasks(tasks)
                except Exception as e:
                    tasks[task_id]['status'] = 'failed'
                    tasks[task_id]['error'] = str(e)
                    eval_log.write(f'更新全集任务状态失败: {str(e)}\n')
                    eval_log.flush()
            else:
                tasks[task_id]['status'] = 'failed'
                eval_log.write(f'全集评估请求失败: {resp.status_code}\n')
                eval_log.flush()
        set_tasks(tasks)
        trans_jsonl_to_csv(review_path)
        return ({}, 200)
    else:
        local_asr_eval(endpoint, user_req_asr, task_id, tasks, all_start_time)

def generate_mt_jsonl(json_resp, task_id, endpoint, review_path):
    tasks = get_tasks()
    remote_output_path = json_resp['results'][-1]['output_dir']
    result = json_resp['results']
    url = endpoint + 'api/file/content'
    for item in result[:-1]:
        file_name = item['file']
        payload = {'file_path': f'{remote_output_path}/scored_{file_name}'}
        try:
            response = requests.post(url=url, json=payload, headers={'Content-Type': 'application/json'})
            resp = json.loads(response.json()['data']['content'])
            jsonl_name = file_name.replace('.json', '.jsonl')
            jsonl_file_path = os.path.join(review_path, jsonl_name)
            os.makedirs(os.path.dirname(jsonl_file_path), exist_ok=True)
            with open(jsonl_file_path, 'w', encoding='utf-8') as f:
                for entry in resp:
                    formatted = {'choices': [{'index': 0, 'message': {'content': f"Bleu Score: {round(entry['bleu_score'], 4)} / Comet Score: {round(entry['comet_score'], 4)}"}, 'review': {'pred': entry['mt'], 'result': entry['bleu_score'] >= 0.7, 'accuracy': round(entry['bleu_score'], 4), 'bleu': round(entry['bleu_score'], 4), 'comet': round(entry['comet_score'], 4)}}], 'raw_input': {'Question': entry['src'], 'Answer': entry['ref']}, 'index': entry['file']}
                    f.write(json.dumps(formatted, ensure_ascii=False) + '\n')
        except Exception as e:
            print(e)
            continue

def init_tts_jsonl(review_path, sentence_lines, jsonl_name):
    idx = 0
    jsonl_file = os.path.join(review_path, jsonl_name)
    with open(jsonl_file, 'w', encoding='utf-8') as f:
        for line in sentence_lines:
            formatted = {'choices': [{'index': 0, 'message': {'content': f''}, 'review': {'pred': '', 'result': '', 'mos': 0, 'correct': 0}}], 'raw_input': {'Question': line, 'Answer': ''}, 'index': idx}
            f.write(json.dumps(formatted, ensure_ascii=False) + '\n')
            idx += 1
    return jsonl_file

def trans_jsonl_to_csv(review_path):
    jsonl_files = glob.glob(os.path.join(review_path, '*.jsonl'))
    for jsonl_file in jsonl_files:
        csv_file = jsonl_file.replace('.jsonl', '.csv')
        jsonl_to_csv(jsonl_file, csv_file)

def update_asr_eval_res(tasks, task_id, model_name, score, dataset, progress):
    tasks[task_id]['progress'] = round(progress, 2)
    found = False
    for case in tasks[task_id]['result'][model_name]:
        if case['dataset_name'] == dataset:
            case['score'] = score
            case['progress'] = 1.0
            found = True
            break
    if not found:
        new_case = {'dataset_name': dataset, 'score': score, 'progress': 1.0}
        tasks[task_id]['result'][model_name].append(new_case)
    tasks[task_id]['status'] = 'completed' if progress >= 0.95 else 'running'

def update_tts_eval_res(tasks, task_id, model_name, resp):
    tasks[task_id]['progress'] = 1.0
    score = resp['results'][-1]['average_system_score'] if 'results' in resp else 0
    tasks[task_id]['result'][model_name][0]['score'] = score
    tasks[task_id]['result'][model_name][0]['progress'] = 1.0
    if 'success' in resp and resp['success']:
        tasks[task_id]['status'] = 'completed'
    else:
        tasks[task_id]['status'] = 'failed'
        if 'message' in resp:
            tasks[task_id]['error'] = resp['message']
        elif 'error' in resp:
            tasks[task_id]['error'] = resp['error']
        else:
            tasks[task_id]['error'] = '未知错误'

def update_mt_eval_res(tasks, task_id, model_name, resp):
    tasks[task_id]['progress'] = 1.0
    try:
        if resp.get('success') and 'results' in resp:
            results = [item for item in resp['results'] if 'system_score' in item]
            score_map = {}
            for item in results:
                filename = item['file'].split('/')[-1] if '/' in item['file'] else item['file']
                score_map[filename] = item['system_score']
            all_matched = True
            for case in tasks[task_id]['result'][model_name]:
                dataset_key = case['dataset_name'].split('/')[-1]
                expected_filename = f"{dataset_key.replace(' ', '_')}_seedx.json"
                if expected_filename in score_map:
                    case['score'] = score_map[expected_filename]
                    case['progress'] = 1.0
                else:
                    all_matched = False
                    case['error'] = f'未找到匹配结果: {expected_filename}'
            if all_matched:
                tasks[task_id]['status'] = 'completed'
            else:
                tasks[task_id]['status'] = 'failed'
                tasks[task_id]['error'] = '部分案例匹配失败'
        else:
            tasks[task_id]['status'] = 'failed'
            error_msg = resp.get('message') or resp.get('error') or '未知错误'
            tasks[task_id]['error'] = error_msg
    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = f'处理异常: {str(e)}'

def merge_two_task(origin_task, new_task):
    for key in new_task:
        if key not in origin_task:
            origin_task[key] = new_task[key]
    for key, val in origin_task.items():
        if key not in new_task:
            continue
        try:
            if key in ['modelType', 'createTime']:
                continue
            elif key == 'status':
                origin_task[key] = 'running'
            elif key == 'result' and isinstance(val, dict):
                val.update(new_task[key])
            elif key == 'use_cache':
                if not isinstance(val, list):
                    val = [val]
                if not isinstance(new_task[key], list):
                    origin_task[key] = val + [new_task[key]]
                else:
                    origin_task[key] = val + new_task[key]
            elif key == 'taskConfig' and isinstance(val, dict):
                merge_two_task(val, new_task[key])
            elif isinstance(val, str) and val != new_task[key] and (key != 'assessmentType'):
                origin_task[key] = f'{val};{new_task[key]}'
            elif isinstance(val, list):
                new_val = new_task[key]
                origin_task[key] = val + [new_val] if not isinstance(new_val, list) else val + new_val
        except Exception as e:
            print(f'合并键 {key} 时出错: {e}')

def get_asr_non_tokenized_res(user_req_asr, task_id, output_path):
    asr_model_id = user_req_asr['model_id']
    asr_res_path = os.path.join('outputs', asr_model_id, task_id, 'asr_result', 'non_tokenize')
    file_paths = glob.glob(os.path.join(asr_res_path, '*.txt'))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f'cascade_{timestamp}.txt'
    os.makedirs(output_path, exist_ok=True)
    output_file = os.path.join(output_path, output_filename)
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for i, file_path in enumerate(file_paths):
            if not os.path.exists(file_path):
                print(f'Warning: {file_path} not found. Skipping.')
                continue
            with open(file_path, 'r', encoding='utf-8') as infile:
                content = infile.read()
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            content = content.rstrip('\n')
            if content:
                outfile.write(content)
                if i < len(file_paths) - 1:
                    outfile.write('\n')
    return output_file

def generate_mt_input_by_lan(language, excel_path, output_dir, sheet_names):

    def get_translation_direction(language):
        if '关键词' in excel_path and language in TRANSLATE_DIRECTION_WORD:
            return (TRANSLATE_DIRECTION_WORD[language][0], TRANSLATE_DIRECTION_WORD[language][1])
        elif language in TRANSLATE_DIRECTION:
            return (TRANSLATE_DIRECTION[language][0], TRANSLATE_DIRECTION[language][1])
        return (None, None)
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f'Excel file not found: {excel_path}')
    source_lang, target_lang = get_translation_direction(language)
    if not source_lang:
        raise ValueError(f'Unsupported source language: {source_lang}. ')
    excel_file = pd.ExcelFile(excel_path)
    all_sheets = excel_file.sheet_names
    output_lines = []
    for sheet_name in sheet_names:
        if sheet_name not in all_sheets:
            raise ValueError(f'Sheet不存在: {sheet_name}')
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            if '序号' not in df.columns and 'NO.' not in df.columns:
                raise ValueError(f"Sheet '{sheet_name}' missing '序号' or 'NO.' column")
            if source_lang not in df.columns:
                raise ValueError(f"Sheet '{sheet_name}' missing source language column '{source_lang}' ")
            for idx, row in df.iterrows():
                serial_number = ''
                if '序号' in df.columns:
                    serial_number = str(row['序号']).strip() if pd.notna(row['序号']) else ''
                elif 'NO.' in df.columns:
                    serial_number = str(row['NO.']).strip() if pd.notna(row['NO.']) else ''
                if not serial_number:
                    continue
                try:
                    num_value = float(serial_number)
                    serial_number = str(int(num_value))
                except (ValueError, TypeError):
                    pass
                source_text = row[source_lang]
                if pd.isna(source_text):
                    source_text = ''
                else:
                    source_text = str(source_text).strip()
                if not source_text:
                    continue
                first_line = f'{sheet_name}_{serial_number.lower()}.wav'
                output_lines.append(first_line)
                output_lines.append(source_text)
        except Exception as e:
            raise RuntimeError(f"Error processing sheet '{sheet_name}': {str(e)}")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f'{language}_{timestamp}.txt'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
    except Exception as e:
        raise RuntimeError(f'Error writing output file: {str(e)}')
    print(f'Successfully generated MT input file: {output_path}')
    return output_path

def run_mt_eval(task_id, user_req):
    all_start_time = time.time()
    print('开始执行MT测评---------------------------')
    user_req_asr = user_req.get('asr', None)
    cascade = user_req_asr is not None
    cascadeTTS = user_req.get('tts', None) is not None
    user_req_mt = user_req.get('mt', None)
    if not user_req_mt:
        return ({'message': '未识别到mt参数', 'success': False}, 500)
    user_req_mt['name'] = user_req['task_name']
    user_req_mt['assessmentType'] = 'ASR+MT+TTS' if cascadeTTS else 'ASR+MT' if cascade else 'MT'
    datasets = user_req_mt.get('dataset', [])
    if not datasets:
        return ({'errType': 'datasets参数不能为空'}, 400)
    excel_file_name = None
    sheet_names = []
    for ds in datasets:
        parts = ds.split('/')
        print(f'parts: {parts}')
        if len(parts) != 4:
            return ({'errType': f'无效的datasets格式: {ds}'}, 400)
        if excel_file_name is None:
            excel_file_name = os.path.join(parts[0], parts[1], parts[2])
        elif excel_file_name != os.path.join(parts[0], parts[1], parts[2]):
            return ({'errType': '所有datasets必须来自同一Excel文件'}, 400)
        sheet_names.append(parts[3])
    print(f'Excel文件名: {excel_file_name}\nSheet名称: {sheet_names}')
    excel_path = os.path.join(SIMU_INTERPRETATION_MT, excel_file_name)
    if not os.path.exists(excel_path):
        return ({'errType': f'Excel文件不存在: {excel_file_name}'}, 400)
    print(f'Excel文件路径: {excel_path}')
    user_req_mt['datasets'] = datasets
    model_id = user_req_mt['model_id']
    model_config = get_one_model_config(model_id)
    if not model_config:
        print(f'errType: Model ({model_id}) not registered')
        return ({'errType': f'Model ({model_id}) not registered'}, 400)
    try:
        language = user_req_mt['language']
    except:
        print(f'缺失语言转换类型！')
        return ({'message': f'缺失语言转换类型！', 'success': False}, 500)
    translate_type = 'hwc'
    model_type = 'word' if '关键词' in excel_path else 'normal'
    model_name = model_config['info']['model_name']
    tasks = get_tasks()
    if task_id not in tasks.keys():
        tasks[task_id] = generate_run_task_info(user_req_mt, model_id, model_name, model_config, task_id)
    elif cascade:
        merge_two_task(tasks[task_id], generate_run_task_info(user_req_mt, model_id, model_name, model_config, task_id))
    else:
        print(f'任务id被占用: {task_id}')
        return ({'message': f'任务id被占用: {task_id}', 'success': False}, 500)
    print(f'task_id:{task_id}\ntask_info:{tasks[task_id]}')
    set_tasks(tasks)
    endpoint = MT_EVAL_URL
    url = f'{endpoint}batch_evalution?lang={language}&type={translate_type}&model_type={model_type}'
    log_path, review_path = init_simu_inter_task_path(model_id, task_id)
    txt_dir = f'outputs/{model_id}/{task_id}/mt_input_text'
    if cascade:
        text_path = get_asr_non_tokenized_res(user_req_asr, task_id, txt_dir)
    else:
        text_path = generate_mt_input_by_lan(language, excel_path, txt_dir, sheet_names)
    print(f'发送MT请求：{url}\n输入文件：{text_path}\nExcel文件：{excel_path}')
    files = [('file', (os.path.basename(text_path), open(text_path, 'rb'), 'text/plain')), ('excel_file', (os.path.basename(excel_path), open(excel_path, 'rb'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))]
    with open(os.path.join(log_path, 'eval_log.log'), 'w') as f:
        f.write(f'language: {language}\ntext_file: {text_path}\nexcel_file: {excel_path}\n\n')
    json_resp, status_code = call_include_files(url, files)
    write_log(log_path, f'MT model server response status code: {status_code}\nTHE MT MODEL SERVER RESPONSE:\n{json.dumps(json_resp)}')
    all_end_time = time.time()
    tasks = get_tasks()
    tasks[task_id]['runningTime'] = all_end_time - all_start_time
    update_mt_eval_res(tasks, task_id, model_name, json_resp)
    set_tasks(tasks)
    if status_code == 200:
        generate_mt_jsonl(json_resp, task_id, endpoint, review_path)
        trans_jsonl_to_csv(review_path)
    else:
        tasks = get_tasks()
        tasks[task_id]['success'] = 'failed'
        set_tasks(tasks)
    return (json_resp, status_code)

def jsonl_to_txt(jsonl_files_pattern, txt_file_path, model_id, task_id):
    """
    将多个MT评估生成的jsonl文件转换为TTS任务所需的单个txt文件。
    从所有匹配的jsonl文件中提取每个对象的Answer字段值，依次写入txt文件。
    """
    jsonl_files = glob.glob(jsonl_files_pattern)
    if not jsonl_files:
        print(f'未找到匹配的JSONL文件: {jsonl_files_pattern}')
        return None
    jsonl_files.sort()
    with open(txt_file_path, 'w', encoding='utf-8') as txt_file:
        for jsonl_file in jsonl_files:
            print(f'处理文件: {jsonl_file}')
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        answer = data.get('raw_input', {}).get('Answer', '')
                        if answer:
                            txt_file.write(answer + '\n')
                    except json.JSONDecodeError:
                        print(f'跳过无效的JSON行: {line.strip()}')
    print(f'TTS输入文件已生成: {txt_file_path}')
    return txt_file_path

def _generate_tts_input_cascade(user_req, log_path, review_path, task_id):
    mt_model_id = user_req['mt']['model_id']
    model_id_basename = os.path.basename(mt_model_id).rstrip(os.sep)
    mt_review_path = f'outputs/{mt_model_id}/{task_id}/reviews/{model_id_basename}'
    model_id = user_req['tts']['model_id']
    language = user_req['tts']['language']
    txt_dir = f'outputs/{model_id}/{task_id}/tts_input_text'
    os.makedirs(txt_dir, exist_ok=True)
    txt_file_path = os.path.join(txt_dir, 'tts_input.txt')
    jsonl_to_txt(os.path.join(mt_review_path, '*.jsonl'), txt_file_path, model_id, task_id)
    excel_file_name = task_id.replace('_', '')
    excel_path = os.path.join(review_path, f'{excel_file_name}_{language}_出租车_男_1_50.xlsx')
    excel_path_list, sentence_lines = txt_to_excel(txt_file_path, excel_path)
    input_files = []
    languages = [[language] * 1]
    all_sentence = []
    input_files.append(excel_path_list)
    all_sentence += sentence_lines
    return (input_files if input_files else [], languages if languages else [], [], [], [], all_sentence if all_sentence else [])

def _generate_tts_input_normal(user_req, log_path, review_path):
    user_req_tts = user_req.get('tts', None)
    if not user_req_tts:
        write_log(log_path, '未识别到tts参数')
        return ([], [], [], [], [], [])
    datasets = user_req_tts.get('datasets', '')
    input_files = []
    languages = []
    sent_files = []
    label_files = []
    dataset_language = []
    all_sentence = []
    for dataset in datasets:
        input_path = glob.glob(os.path.join(SIMU_INTERPRETATION_TTS, dataset, '*_sents.txt'))
        label_path = glob.glob(os.path.join(SIMU_INTERPRETATION_TTS, dataset, '*_labels.txt'))
        if not input_path or not label_path:
            write_log(log_path, f'datasets ({dataset}) not exist!')
            continue
        language = dataset.split('/')[1]
        dataset_name = dataset.replace('/', '').replace('\\', '').replace('_', '').strip()
        if language not in ['ar', 'zh', 'en', 'th']:
            write_log(log_path, f'dataset ({dataset}) language({language}) does not support!')
            continue
        excel_path = os.path.join(review_path, f'{dataset_name}_{language}_出租车_男_1_50.xlsx')
        excel_path_list, sentence_lines = txt_to_excel(input_path[0], excel_path)
        input_files.append(excel_path_list)
        languages.append([language] * len(excel_path_list))
        all_sentence += sentence_lines
        sent_files.append(input_path[0])
        label_files.append(label_path[0])
        dataset_language.append(language)
    return (input_files if input_files else [], languages if languages else [], sent_files if sent_files else [], label_files if label_files else [], dataset_language if dataset_language else [], all_sentence if all_sentence else [])

def _generate_tts_input(user_req, log_path, review_path, cascade, task_id):
    return _generate_tts_input_cascade(user_req, log_path, review_path, task_id) if cascade else _generate_tts_input_normal(user_req, log_path, review_path)

def update_tts_res(json_resp, json_file):
    content = json_resp['data']['content']
    pattern = '(\\[\\d+\\]:.*?)(?=\\n\\n\\[\\d+\\]:|\\n\\nTotal:|\\Z)'
    blocks = re.findall(pattern, content, re.DOTALL)
    idx = 0
    with open(json_file, 'w', encoding='utf-8') as f:
        for block in blocks:
            question_dict = {'Question': '', 'pred': [], 'answer': '', 'accuracy': ''}
            lines = block.strip().split('\n')
            for line in lines:
                if line.startswith('[') and ']:' in line:
                    question_dict['Question'] = line.split('\t', 1)[1]
                elif line.startswith('label:'):
                    answer = line.split('\t', 1)[1]
                    question_dict['pred'].append(answer)
                elif line.startswith('result:'):
                    question_dict['answer'] = line.split('\t', 1)[1]
                elif line.startswith('check:'):
                    question_dict['accuracy'] = line.split('\t', 1)[1]
            formatted = {'choices': [{'index': 0, 'message': {'content': f'{block}'}, 'review': {'pred': question_dict['answer'], 'result': question_dict['accuracy'], 'accuracy': 'true' in question_dict['accuracy'], 'mos': 0}}], 'raw_input': {'Question': question_dict['Question'], 'Answer': question_dict['pred']}, 'index': idx}
            f.write(json.dumps(formatted, ensure_ascii=False) + '\n')
            idx += 1

def run_tts_eval(task_id, user_req):
    global jsonFile
    tasks = get_tasks()
    all_start_time = time.time()
    print('开始执行TTS测评---------------------------')
    user_req_tts = user_req.get('tts', None)
    user_req_tts['name'] = user_req['task_name']
    datasets = user_req_tts.get('datasets', '')
    user_req_tts['datasets'] = datasets
    model_id = user_req['tts']['model_id']
    model_config = get_one_model_config(model_id)
    model_name = model_config['info']['model_name']
    try:
        endpoint = model_config['config']['api_params_available'][0]['endpoint']
    except:
        endpoint = TTS_EVAL_URL
    log_path, review_path = init_simu_inter_task_path(model_id, task_id)
    exec_list = user_req.get('exec_list', [])
    cascade = exec_list[0] == 'asr'
    user_req_tts['assessmentType'] = 'ASR+MT+TTS' if cascade else 'TTS'
    if task_id not in tasks.keys():
        tasks[task_id] = generate_run_task_info(user_req_tts, model_id, model_name, model_config, task_id)
    elif cascade:
        merge_two_task(tasks[task_id], generate_run_task_info(user_req_tts, model_id, model_name, model_config, task_id))
    set_tasks(tasks)
    excel_path, languages, sent_files, label_files, dataset_language, all_sentence = _generate_tts_input(user_req, log_path, review_path, cascade, task_id)
    for excel_files, lang, sentence_lines in zip(excel_path, languages, all_sentence):
        for excel_file in excel_files:
            jsonFile = init_tts_jsonl(review_path, sentence_lines, os.path.basename(excel_file).replace('.xlsx', '.jsonl'))
            files = [('excel_file', (os.path.basename(excel_file), open(excel_file, 'rb'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))]
            write_log(log_path, f'input_file: {os.path.basename(excel_file)}\n\n')
            eval_endpoint = endpoint + f'tts_result?lang={lang[0]}'
            print(f'开始发送请求：{eval_endpoint}')
            json_resp, status_code = call_include_files(eval_endpoint, files)
            if status_code == 200:
                write_log(log_path, f'excel_file ({excel_file}) success!\n')
                file_endpoint = endpoint + f'api/file/content'
                for file_info in json_resp['result']:
                    json_resp, file_api_status = call_with_payload(file_endpoint, {'file_path': file_info['path']})
                    if file_api_status == 200:
                        wav_file = os.path.join(review_path, file_info['file'])
                        base64_to_audio(json_resp['data']['content'], wav_file)
                        write_log(log_path, f'write audio file to: {wav_file}')
                    else:
                        write_log(log_path, f"get wav file ({file_info['file']}) failed!\n")
                write_log(log_path, f'文件{excel_file}处理完成\n')
            else:
                write_log(log_path, f'excel_file ({excel_file}) failed!error:{json_resp}\n')
                tasks[task_id]['status'] = 'failed'
    write_log(log_path, f'.wav文件生成结束\n')
    if not cascade:
        idx = 0
        for sent_file, label_file, lang, dataset in zip(sent_files, label_files, dataset_language, datasets):
            idx += 1
            test_mode = 'compare_pinyin' if '归一化' not in sent_file else 'compare_numnorm'
            correct_endpoint = endpoint + f'tts_accuracy?lang={lang}&test_mode={test_mode}'
            files = [('sentence_file', (os.path.basename(sent_file), open(sent_file, 'rb'), 'text/plain')), ('label_file', (os.path.basename(label_file), open(label_file, 'rb'), 'text/plain'))]
            json_resp, status_code = call_include_files(correct_endpoint, files)
            if status_code == 200:
                write_log(log_path, f'test {sent_file} with label({label_file}) success!\n')
                file_endpoint = endpoint + f'api/file/content'
                for file_info in json_resp['result']:
                    json_resp, file_api_status = call_with_payload(file_endpoint, {'file_path': file_info['path']})
                    if file_api_status == 200:
                        res_file = os.path.join(review_path, file_info['file'])
                        write_log(log_path, f'get result file ({res_file}) success!\n')
                        write_log(log_path, f'json_resp: {json_resp}\n')
                        update_tts_res(json_resp, jsonFile)
                        ret_str = json_resp['data']['content'][-500:]
                        match = re.search('rate:\\s*([0-9]*\\.?[0-9]+)', ret_str)
                        if match:
                            rate_value = round(float(match.group(1)), 4)
                        else:
                            rate_value = 0.0
                        tasks[task_id]['evalRes'] = rate_value
                        update_asr_eval_res(tasks, task_id, model_name, rate_value, dataset, idx / len(sent_files))
                        set_tasks(tasks)
                    else:
                        write_log(log_path, f"get result file ({file_info['path']}) failed!\n")
                        tasks[task_id]['status'] = 'failed'
            else:
                write_log(log_path, f'excel_file ({sent_file}) failed!error:{json_resp}\n')
                tasks[task_id]['status'] = 'failed'
    elif tasks[task_id]['status'] != 'failed':
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 1.0
    all_end_time = time.time()
    tasks[task_id]['runningTime'] = all_end_time - all_start_time
    set_tasks(tasks)
    return ({}, 200)
