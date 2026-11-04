# Private iCAP Yellow business implementation. Do not publish.
import base64
import json
import os.path
import re
from datetime import datetime
import pandas as pd
import requests
from services import logger
from utils.io_utils import *
DATASET_FILE_NAME = 'datasets.json'
DATASET_OPEN_FILE_NAME = 'datasets_open.json'

def encode_image(image_path) -> str:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f'{image_path} not found')
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def request_image(model_name, model_url, base64_image, prompt) -> str:
    """
    请求模型
    :param model_name:
    :param model_url:
    :param base64_image:
    :param prompt:
    :return:
    """
    try:
        payload = json.dumps({'model': model_name, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}, {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{base64_image}'}}]}]})
        response = requests.request('POST', model_url, data=payload, headers={'Content-Type': 'application/json'}).json()
        return response['choices'][0]['message']['content']
    except Exception as e:
        log_outfit.error(f'model:{model_name} req err {e}')
        return ''

def is_success(golden_ans, llm_ans, is_not_open) -> bool:
    if is_not_open:
        letters = re.findall('[A-Za-z]', golden_ans)
        model_letters = re.findall('[A-Za-z]', llm_ans)
        if not (letters and model_letters):
            return False
        return letters[0] == model_letters[0]
    else:
        return False

def run_dataset_eval(data_set_path, limit, model_name, model_url):
    dataset_file = os.path.join(data_set_path, DATASET_FILE_NAME)
    if not os.path.exists(dataset_file):
        log_outfit.error(f'dataset_file: {dataset_file}')
        raise FileNotFoundError(f'{dataset_file} not found')
    dataset_open_file = os.path.join(data_set_path, DATASET_OPEN_FILE_NAME)
    if not os.path.exists(dataset_open_file):
        log_outfit.error(f'dataset_file: {dataset_open_file}')
        raise FileNotFoundError(f'{dataset_open_file} not found')
    eval_data = json.load(open(dataset_file, 'r', encoding='utf-8'))
    is_start_open_index = len(eval_data)
    log_outfit.info(f'open_index: {is_start_open_index}')
    eval_open_data = json.load(open(dataset_open_file, 'r', encoding='utf-8'))
    eval_data += eval_open_data
    if limit is None or limit == 0:
        limit = 1000
    for index, item in enumerate(eval_data):
        if index > limit - 1:
            break
        image_file = os.path.join(data_set_path, item['images'][0])
        if not os.path.exists(image_file):
            raise FileNotFoundError(f'{image_file} not found')
    result_data_objective = []
    result_data_subjective = []
    suc_count = 0
    total_count = min(len(eval_data), limit)
    if total_count != 0:
        for index, item in enumerate(eval_data):
            if index > limit - 1:
                break
            img_path = item['images'][0]
            ques = item['messages'][0]['content']
            base64_image = encode_image(os.path.join(data_set_path, img_path))
            is_not_open = index < is_start_open_index
            model_answer = request_image(model_name, model_url, base64_image, ques)
            golden_ans = item['messages'][1]['content']
            if is_not_open:
                is_suc = is_success(golden_ans, model_answer, is_not_open)
                if is_suc:
                    suc_count += 1
                result_data_objective.append({'图片路径': img_path, '问题': ques, '标准答案': golden_ans, '模型答案': model_answer, '是否正确': 1 if is_suc else 0})
            else:
                result_data_subjective.append({'图片路径': img_path, '问题': ques, '标准答案': golden_ans, '模型答案': model_answer, '是否正确': ''})
            log_outfit.info(f'->The index of currently executed is {index + 1}, and the total number is {total_count}.<-')
    return (result_data_objective, result_data_subjective, suc_count, limit if limit < is_start_open_index else is_start_open_index)

def gen_review_jsonl(result_data_objective, review_path):
    review_lines = []
    for index, da in enumerate(result_data_objective):
        review_lines.append({'raw_input': {'img': da['图片路径'], 'Answer': da['模型答案'], 'No': index, 'Question': da['问题']}, 'choices': [{'review': {'gold': da['标准答案'], 'pred': da['模型答案'], 'result': da['是否正确']}, 'message': {'content': da['模型答案']}}], 'index': index, 'subset_name': 'default'})
    review_file: str = os.path.join(review_path, '视觉感知_default.jsonl')
    dump_jsonl_data(review_lines, review_file, dump_mode=DumpMode.APPEND)

def gen_report_json(model_name, report_path, suc_count, total_count):
    acc = suc_count / total_count if total_count != 0 else 0
    report_map = {'name': f'{model_name}_视觉感知', 'dataset_name': '视觉感知', 'model_name': model_name, 'score': acc, 'metrics': [{'categories': [{'macro_score': acc, 'name': ['default'], 'num': total_count, 'score': acc, 'subsets': [{'name': 'default', 'num': total_count, 'score': acc}]}], 'macro_score': acc, 'name': 'AverageAccuracy', 'num': total_count, 'score': acc}]}
    report_path_file: str = os.path.join(report_path, '视觉感知.json')
    os.makedirs(os.path.dirname(report_path_file), exist_ok=True)
    with open(report_path_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report_map, ensure_ascii=False, indent=4))

def gen_review_xlsx(result_data_objective, result_data_subjective, review_path):
    start_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file_name = os.path.join(review_path, f'视觉感知_{start_time}.xlsx')
    os.makedirs(os.path.dirname(output_file_name), exist_ok=True)
    result_df_obj = pd.DataFrame(result_data_objective)
    result_df_subj = pd.DataFrame(result_data_subjective)
    with pd.ExcelWriter(output_file_name) as writer:
        result_df_obj.to_excel(writer, sheet_name='客观题', index=False)
        result_df_subj.to_excel(writer, sheet_name='主观题', index=False)

def run_custom_outfit_eval(model_name, model_url, data_set_path, output_path, model_id, limit):
    """
    视觉穿搭评估
    :param model_name: model_name
    :param model_url: model_url
    :param data_set_path: 数据集路径
    :param limit: 测评数量
    :return:
    """
    log_path = f'{output_path}/logs'
    global log_outfit
    log_outfit = logger.Logger('eval_log')
    log_outfit.update_log_dir(log_path)
    cur_dir = os.getcwd()
    log_outfit.info(f'cur_dir: {cur_dir}')
    model_id_basename = os.path.basename(model_id).rstrip(os.sep)
    review_path = f'{output_path}/reviews/{model_id_basename}'
    report_path = f'{output_path}/reports/{model_id_basename}'
    result_data_objective, result_data_subjective, suc_count, total_count = run_dataset_eval(data_set_path, limit, model_name, model_url)
    gen_review_xlsx(result_data_objective, result_data_subjective, review_path)
    gen_review_jsonl(result_data_objective, review_path)
    gen_review_jsonl(result_data_subjective, review_path)
    gen_report_json(model_name, report_path, suc_count, total_count)
