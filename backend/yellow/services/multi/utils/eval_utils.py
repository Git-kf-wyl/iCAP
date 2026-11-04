# Private iCAP Yellow business implementation. Do not publish.
import argparse
import base64
import json
import os
import subprocess
import time
from datetime import datetime
import httpx
import pandas as pd
import requests
from openai import OpenAI
from services.logger import Logger
from utils.io_utils import DumpMode, dump_jsonl_data
MLLM_CUSTOM_DATASETS_DEBUG_FLAG = False

def encode_audio_base64_from_file(file_path: str, mime_type: str='audio/wav') -> str:
    """从本地文件编码音频为base64 data URL"""
    with open(file_path, 'rb') as f:
        audio_data = f.read()
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        return f'data:{mime_type};base64,{audio_base64}'

def request_audio(model_name, model_url, api_key, audio_base64, prompt, tem=0) -> str:
    """
    请求模型
    :param model_name:
    :param model_url:
    :param audio_base64:
    :param prompt:
    :param tem:
    :return:
    """
    audio_request_content = {'type': 'input_audio', 'input_audio': {'data': audio_base64, 'format': 'wav'}} if 'dashscope.aliyuncs.com' in model_url else {'type': 'audio_url', 'audio_url': {'url': audio_base64}}
    payload = {'model': model_name, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}, audio_request_content]}], 'stream': False}
    response = requests.request('POST', model_url, json=payload, verify=True, headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'} if api_key else {'Content-Type': 'application/json'}).json()
    return response['choices'][0]['message']['content']

def request_audio_openai(model_name, model_url, api_key, audio_base64, prompt, tem=0, logger: Logger=None) -> str:
    messages = [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}, {'type': 'input_audio', 'input_audio': {'data': audio_base64, 'format': 'wav'}}]}]
    return _call_openai_compatible_api(model_name, model_url, api_key, messages, {}, logger)

def gen_review_jsonl(result_data, review_path, dataset_name, subset_name, is_wer=False):
    review_lines = []
    for index, da in enumerate(result_data):
        review_lines.append({'raw_input': {'audio': da.get('音频路径', ''), 'video': da.get('视频路径', ''), 'Answer': da.get('模型答案', ''), 'No': index, 'Question': da.get('问题', '')}, 'choices': [{'review': {'gold': da.get('标准答案', ''), 'pred': da.get('模型答案', ''), 'result': da.get('WER', '') if is_wer else da.get('是否正确', '')}, 'message': {'content': da.get('模型答案', '')}}], 'index': index, 'subset_name': subset_name})
    review_file: str = os.path.join(review_path, f'{dataset_name}_{subset_name}.jsonl')
    dump_jsonl_data(review_lines, review_file, dump_mode=DumpMode.APPEND)

def write_report_json(report_path, dataset_name, report_map):
    report_path_file: str = os.path.join(report_path, f'{dataset_name}.json')
    os.makedirs(os.path.dirname(report_path_file), exist_ok=True)
    with open(report_path_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report_map, ensure_ascii=False, indent=4))

def gen_report_json(model_name, report_path, suc_count, total_count, dataset_name):
    acc = round(suc_count / total_count, 4) if total_count != 0 else 0.0
    report_map = {'name': f'{model_name}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_name, 'score': acc, 'metrics': [{'categories': [{'macro_score': acc, 'name': ['default'], 'num': total_count, 'score': acc, 'subsets': [{'name': 'default', 'num': total_count, 'score': acc}]}], 'macro_score': acc, 'name': 'AverageAccuracy', 'num': total_count, 'score': acc}]}
    write_report_json(report_path, dataset_name, report_map)

def gen_review_excel(data_set_name, subset, result_data, review_path):
    start_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file_name = os.path.join(review_path, f'{data_set_name}_{subset}_{start_time}.xlsx')
    os.makedirs(os.path.dirname(output_file_name), exist_ok=True)
    result_df = pd.DataFrame(result_data)
    result_df.to_excel(output_file_name, index=False)

def encode_video_base64(video_path, my_log: Logger):
    """Encodes the entire video file to base64."""
    try:
        with open(video_path, 'rb') as video_file:
            return base64.b64encode(video_file.read()).decode('utf-8')
    except FileNotFoundError:
        my_log.error(f'Error: Video file not found for encoding: {video_path}')
        return None
    except Exception as e:
        my_log.error(f'Error encoding video {video_path}: {e}')
        return None
CUR_MAX_RETRIES = 1
BASE_DELAY = 4
PROJECT_ROOT_PATH = '/home/aisf/w00649384/backend'
MLLM_ROOT_PATH = '/home/aisf/w00649384/backend/services/multi'

def _call_noopenai_compatible_api(model_name, model_url, messages, request_params, my_log: Logger) -> str:
    payload = {'model': model_name, 'messages': messages, 'stream': False, 'temperature': request_params.get('temperature', 0), 'max_tokens': request_params.get('max_tokens', 1024)}
    if 'qwen3.' in model_name.lower():
        payload.update({'chat_template_kwargs': {'enable_thinking': False}})
    try:
        response = requests.request('POST', model_url, json=payload, verify=True, headers={'Content-Type': 'application/json'}).json()
        model_res = response['choices'][0]['message']['content']
        return model_res
    except Exception as e:
        error_str = str(e).lower()
        my_log.error(f'Post Error: {error_str}.')
        return f'error_no_response'

def _call_openai_compatible_api(model_name, model_url, api_key, messages, request_params, my_log: Logger):
    """Internal helper to call OpenAI-compatible APIs with retry logic."""
    client = OpenAI(api_key='EMPTY' if not api_key else api_key, base_url=model_url.rstrip('/').rsplit('/chat/completions', 1)[0], http_client=httpx.Client(transport=httpx.HTTPTransport(retries=3, verify=True), timeout=3000), timeout=600)
    request_params = {'model': model_name, 'messages': messages, 'stream': False, 'temperature': request_params.get('temperature', 0), 'max_tokens': request_params.get('max_tokens', 1024)}
    for attempt in range(CUR_MAX_RETRIES):
        try:
            completion = client.chat.completions.create(**request_params)
            if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                llm_out = completion.choices[0].message.content.strip()
                return llm_out
            else:
                my_log.info(f'Warning: API response empty or malformed (Attempt {attempt + 1}). Response: {completion}')
                if attempt < CUR_MAX_RETRIES - 1:
                    delay = BASE_DELAY
                    my_log.info(f'Retrying due to empty/malformed response in {delay:.2f}s...')
                    time.sleep(delay)
                else:
                    my_log.error('Max retries reached with empty/malformed response.')
                    return 'error_empty_response'
        except Exception as e:
            error_str = str(e).lower()
            delay = BASE_DELAY
            if 'rate limit' in error_str or '429' in error_str:
                my_log.error(f'API Error (429/Rate Limit): {e}. Retrying in {delay:.2f}s... (Attempt {attempt + 1}/{CUR_MAX_RETRIES})')
                time.sleep(delay)
            elif 'billing' in error_str or 'quota' in error_str:
                my_log.error(f'API Error (Billing/Quota): {e}. Stopping retries.')
                return 'error_billing_quota'
            elif 'invalid api key' in error_str:
                my_log.error(f'FATAL: Invalid API Key. Please check config. {e}')
                return 'error_invalid_key'
            elif 'authentication' in error_str:
                my_log.error(f'FATAL: Authentication Error. Check API Key/Setup. {e}')
                return 'error_authentication'
            elif 'model' in error_str and ('not found' in error_str or 'does not exist' in error_str):
                my_log.error(f"FATAL: Model '{model_name}' not found or invalid for this endpoint. {e}")
                return 'error_invalid_model'
            else:
                my_log.error(f'API Error: {e}. Retrying in {delay:.2f}s... (Attempt {attempt + 1}/{CUR_MAX_RETRIES})')
                time.sleep(delay)
    my_log.error(f'API Error: Max retries exceeded for model {model_name}.')
    return 'error_max_retries'

def request_model_video(model_name, model_url, question, choices, video_path, my_log: Logger):
    system_prompt = f"Your task is to accurately answer multiple-choice questions based on the given video.\nSelect the single most accurate answer from the given choices.\nYour answer should be a capital letter representing your choice: A, B, C, or D. Don't generate any other text."
    prompt = f'Answer the question about a video below. Give the most reasonable answer.\nQuestion: {question}\nChoices: {choices}'
    encoded_video = encode_video_base64(video_path, my_log)
    if encoded_video is None:
        return 'error_video_encoding'
    video_base64_url = f'data:video/mp4;base64,{encoded_video}'
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': [{'type': 'text', 'text': prompt}, {'type': 'video_url', 'video_url': {'url': video_base64_url}}]}]
    request_param = {'temperature': 0, 'max_tokens': 1024}
    return _call_openai_compatible_api(model_name, model_url, '', messages, request_param, my_log)

def load_json_data(file_path, my_log: Logger):
    """Loads JSON data from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        my_log.error(f"Error: File not found at '{file_path}'")
        return None
    except json.JSONDecodeError:
        my_log.error(f"Error: Invalid JSON format in '{file_path}'")
        return None
    except Exception as e:
        my_log.error(f"Error loading JSON data from '{file_path}': {e}")
        return None

def get_video_path(video_id, base_path):
    """Constructs the video file path from a video ID."""
    return os.path.join(base_path, 'Videos', str(video_id), f'{str(video_id)}_video.mp4')

def evaluate_answer(api_answer, correct_answer_char):
    """
    Compares API's answer with the correct answer character.
    Handles potential errors or None values from API.
    Returns True if correct, False otherwise.
    """
    if not api_answer or not isinstance(api_answer, str) or api_answer.startswith('error_'):
        return False
    return api_answer.strip().upper().startswith(correct_answer_char.strip().upper())

def get_suc_count(results_data):
    stats = {'total_processed': 0, 'overall_correct': 0, 'api_failures': 0}
    for result in results_data:
        if result.get('skipped'):
            continue
        stats['total_processed'] += 1
        if result['是否api调用失败']:
            stats['api_failures'] += 1
        if not result['是否api调用失败'] and result['是否正确']:
            stats['overall_correct'] += 1
    items_for_accuracy = stats['total_processed'] - stats['api_failures']
    return (stats['overall_correct'], items_for_accuracy)

def run_mllm_script(script_path, model_info, eval_info):
    python_interpreter = 'python' if os.name == 'nt' else 'python3'
    env = os.environ.copy()
    env['PYTHONPATH'] = PROJECT_ROOT_PATH
    print('start subprocess run.')
    model_info_str = json.dumps(model_info)
    eval_info_str = json.dumps(eval_info)
    subprocess.run([python_interpreter, script_path, model_info_str, eval_info_str], env=env)
    print('end subprocess run.')

def parse_param():
    parser = argparse.ArgumentParser(description='run mmlm')
    parser.add_argument('model_info', type=str, help='Model information.')
    parser.add_argument('eval_info', type=str, help='Evaluation information.')
    try:
        args = parser.parse_args()
        model_info = args.model_info
        eval_info = args.eval_info
    except BaseException as e:
        raise Exception(f'parser err:{e}')
    return (model_info, eval_info)
