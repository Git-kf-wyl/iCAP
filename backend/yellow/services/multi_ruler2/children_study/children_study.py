# Private iCAP Yellow business implementation. Do not publish.
import base64
import json
import os.path
import re
import threading
import time
from datetime import datetime
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests
import time
from services import logger
from unicodedata import category
from utils.io_utils import *
from services.multi_ruler2.children_study.preprocess_evaluation import preprocess_excel
from services.multi_ruler2.children_study.result_evaluation import calculate_accuracy_with_styles
from services.multi_ruler2.children_study.result_statistics import processExcel, ATTENTION_SMALL_CATEGORIES, POSTURE_SMALL_CATEGORIES
from services.multi_ruler2.children_study.analyze_statistics import analyze_cost_time, write_to_excel
from services.multi_ruler2.outfit.auto_run import encode_image
from services.multi_ruler2.children_study.analyze_statistics import analyze_stability, merge_excel_files
thread_controls = {}
thread_controls_lock = threading.Lock()
BATCH_SIZE = 10

def pause_thread(thread_id):
    """暂停指定线程的任务提交"""
    with thread_controls_lock:
        if thread_id in thread_controls:
            thread_controls[thread_id]['paused'] = True
            logger.global_logger.info(f'Thread {thread_id} paused. Current tasks will complete, but no new tasks will be submitted.')
        else:
            logger.global_logger.info(f'Thread control for {thread_id} not found')

def resume_thread(thread_id):
    """恢复指定线程的任务提交"""
    with thread_controls_lock:
        if thread_id in thread_controls:
            thread_controls[thread_id]['paused'] = False
            with thread_controls[thread_id]['condition']:
                thread_controls[thread_id]['condition'].notify_all()
            logger.global_logger.info(f'Thread {thread_id} resumed')
        else:
            logger.global_logger.info(f'Thread control for {thread_id} not found')
EXCEL_COLUMNS = {'case_id': '用例编号', 'image_path': '当前帧t路径', 'image_path_prev': 't-1.0路径', 'baseline_image': '基准帧路径', 'attention_status': '注意力大类-单次结果', 'attention_category': '注意力小类-单次结果', 'sitting_posture_status': '坐姿大类', 'sitting_posture_category': '坐姿小类', 'image_source': '图片来源', 'resolution': '分辨率', 'attention_difficulty': '难易程度-注意力', 'sitting_posture_difficulty': '难易程度-坐姿'}
MODEL_FIELDS = {'attention_status': 'attention_status', 'attention_category': 'attention_category', 'sitting_posture_status': 'sitting_posture_status', 'sitting_posture_category': 'sitting_posture_category'}

def request_image(model_name, model_url, base64_image, base64_image_next, sys_prompt, user_prompt, temperature, max_tokens, api_key):
    """
    发送单次请求到模型API（模型协议），返回 (响应文本, token信息)
    失败时返回 ('', token_info)
    """
    global hasPrint
    token_info = {'total_tokens': 0, 'prompt_tokens': 0, 'completion_tokens': 0}
    response_text = ''
    try:
        messages = [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': []}]
        messages[1]['content'].append({'type': 'text', 'text': user_prompt})
        messages[1]['content'].append({'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{base64_image}'}})
        if base64_image_next:
            messages[1]['content'].append({'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{base64_image_next}'}})
        payload = {'model': model_name, 'temperature': temperature, 'messages': messages, 'max_tokens': max_tokens, 'chat_template_kwargs': {'enable_thinking': False}}
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
        http_response = requests.post(model_url, json=payload, headers=headers, timeout=600)
        http_response.raise_for_status()
        response_text = http_response.text
        response_data = http_response.json()
        usage = response_data.get('usage', {})
        token_info = {'total_tokens': usage.get('total_tokens', 0), 'prompt_tokens': usage.get('prompt_tokens', 0), 'completion_tokens': usage.get('completion_tokens', 0)}
        return (response_data['choices'][0]['message']['content'].strip(), token_info)
    except requests.exceptions.RequestException as req_err:
        logger.global_logger.error(f'模型请求失败: {req_err}')
        return ('', token_info)
    except (KeyError, IndexError) as parse_err:
        logger.global_logger.error(f'解析响应失败: {parse_err}, 原始响应: {response_text}')
        return ('', token_info)
    except Exception as other_err:
        logger.global_logger.error(f'模型请求异常: {other_err}')
        return ('', token_info)

def request_unopen(model_url, base64_image_prev, base64_image, user_prompt, body, api_key, baseline_image=None):
    """
    发送单次请求到指定模型URL（自有协议）
    失败时返回 ('', token_info)

    参数:
        model_url: 模型服务的URL地址
        base64_image_prev: 第一张图片（上一帧 t-1.0）
        base64_image: 第二张图片（当前帧 t）
        user_prompt: 用户输入的提示文本
        body: 请求体的模板格式(可以是JSON字符串或字典)
        baseline_image: 基准帧图片的base64编码（可选）

    返回:
        tuple: (响应结果, token信息)
    """
    token_info = {'total_tokens': 0, 'prompt_tokens': 0, 'completion_tokens': 0}
    try:
        image_data_urls = []
        for img_path in [base64_image_prev, base64_image]:
            with open(img_path, 'rb') as f:
                img_data = f.read()
                image_base64 = base64.b64encode(img_data).decode('utf-8')
                image_data_urls.append(f'data:image/jpeg;base64,{image_base64}')
        payload = {'text': '检测视距、坐姿、离座和注意力', 'image_b64_list': image_data_urls, 'metadata': {'case': 'user-upload'}}
        if baseline_image:
            with open(baseline_image, 'rb') as f:
                baseline_img_data = f.read()
                baseline_image_b64 = base64.b64encode(baseline_img_data).decode('utf-8')
                payload['baseline_image_b64'] = f'data:image/jpeg;base64,{baseline_image_b64}'
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
        http_response = requests.post(model_url, json=payload, headers=headers, timeout=600)
        http_response.raise_for_status()
        if http_response.status_code == 200:
            response_data = http_response.json()
            return (json.dumps(response_data.get('results', {}), ensure_ascii=False), token_info)
        return ('', token_info)
    except Exception as e:
        print(f'请求失败: {e}')
        return ('', token_info)

def extract_last_json(text: str) -> dict:
    """
    从文本中提取最后一个有效的顶层 JSON 对象（只匹配最外层 {...}，跳过内嵌子对象）。
    遍历每个 '{' 位置，找到最外层闭合的 '}' 后尝试 json.loads，
    然后直接跳到该块之后继续，避免内嵌子对象被重复匹配。
    返回最后一个成功解析成 dict 的结果，全部失败则返回 None。
    """
    last_valid = None
    i = 0
    while i < len(text):
        if text[i] != '{':
            i += 1
            continue
        depth = 1
        j = i + 1
        in_string = False
        escape = False
        while j < len(text):
            ch = text[j]
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = not in_string
            elif not in_string:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict):
                                last_valid = parsed
                        except json.JSONDecodeError:
                            pass
                        i = j + 1
                        break
            j += 1
        else:
            i += 1
            continue
        continue
    return last_valid

def parse_model_response(model_ans_str: str) -> dict:
    """
    解析模型的回答字符串，提取出与标准答案相关的字段。
    如果解析失败或字段缺失，则返回默认值 "未知"。
    """
    parsed_status = {'attention_status': '未知', 'attention_category': '未知', 'sitting_posture_status': '未知', 'sitting_posture_category': '未知'}
    try:
        model_ans_json = extract_last_json(model_ans_str)
        if model_ans_json:
            if 'attention_detection' in model_ans_json:
                attention_detection = model_ans_json['attention_detection']
                parsed_status['attention_status'] = attention_detection.get('attention_status', '未知')
                parsed_status['attention_category'] = attention_detection.get('attention_category', '未知')
            if 'sitting_posture_detection' in model_ans_json:
                sitting_posture_detection = model_ans_json['sitting_posture_detection']
                parsed_status['sitting_posture_status'] = sitting_posture_detection.get('sitting_posture_status', '未知')
                parsed_status['sitting_posture_category'] = sitting_posture_detection.get('sitting_posture_category', '未知')
    except json.JSONDecodeError as e:
        logger.global_logger.warning(f'Failed to parse model response as JSON: {model_ans_str}. Error: {e}')
    except Exception as e:
        logger.global_logger.warning(f'An unexpected error occurred during parsing: {e}')
    leave_seat_values = {'离座'}
    leave_related_keys = ['attention_status', 'attention_category', 'sitting_posture_status', 'sitting_posture_category']
    if any((parsed_status.get(k) in leave_seat_values for k in leave_related_keys)):
        for k in leave_related_keys:
            parsed_status[k] = '离座'
    return parsed_status

def calculate_score(gold_dict: dict, pred_dict: dict) -> float:
    """
    计算预测与标准答案之间的得分（预测值需在标准答案的逗号分隔数组中）

    :param gold_dict: 标准答案字典（值应为字符串）
    :param pred_dict: 模型解析答案字典（值应为字符串）
    :return: 得分 (0.0 或 1.0)
    """
    if not gold_dict:
        return 0.0
    for gold_key, gold_value in gold_dict.items():
        if 'category' in gold_key:
            if gold_key not in pred_dict:
                return 0.0
            pred_value = pred_dict[gold_key].strip()
            gold_array = [item.strip() for item in re.split('[，,]', gold_value.strip())]
            if pred_value not in gold_array:
                return 0.0
    return 1.0

def load_prev_results(prev_review_path, dataset_name, task_id):
    """读取续测时旧的评测结果Excel，返回 {index: {model_output, tokens, cost_time}}。

    prev_review_path: 结果Excel所在目录（reviews/{model_name_safe}）
    返回：
        dict，key 为结果Excel的行序索引（与输入Excel行序一致），
        value 包含该行已生成的 原始答案 / token统计 / 耗时。
        若文件不存在或读取失败，返回 {}。
    """
    result = {}
    excel_file = os.path.join(prev_review_path, f'{dataset_name}报告_{task_id}.xlsx')
    if not os.path.exists(excel_file):
        return result
    try:
        prev_df = pd.read_excel(excel_file)
    except Exception as e:
        logger.global_logger.warning(f'续测：读取旧结果Excel失败({excel_file}): {e}')
        return result
    for idx, row in prev_df.iterrows():
        model_output = row.get('model_output', '')
        if model_output is None:
            model_output = ''
        model_output = str(model_output).strip()
        tokens = {'completion_tokens': _to_float(row.get('completion_tokens')), 'prompt_tokens': _to_float(row.get('prompt_tokens')), 'total_tokens': _to_float(row.get('total_tokens'))}
        result[int(idx)] = {'model_output': model_output, 'tokens': tokens, 'cost_time': _to_float(row.get('cost_time')), 'attention_category': row.get('attention_category'), 'sitting_posture_category': row.get('sitting_posture_category')}
    return result

def _to_float(val, default=0.0):
    """将Excel单元格值安全转换为float"""
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default

def _is_result_expectable(prev_info) -> bool:
    """内容续测时判断上一次结果是否符合预期，符合预期才允许复用。

    符合预期需同时满足：
        - attention_category 非空、非"未知"，且在 ATTENTION_SMALL_CATEGORIES 中；
        - sitting_posture_category 非空、非"未知"，且在 POSTURE_SMALL_CATEGORIES 中。
    任一不满足则视为不符合预期，需要重测。
    """

    def _valid(cat, standards):
        if cat is None:
            return False
        if isinstance(cat, float) and pd.isna(cat):
            return False
        cat = str(cat).strip()
        return cat != '' and cat != '未知' and (cat in standards)
    return _valid(prev_info.get('attention_category'), ATTENTION_SMALL_CATEGORIES) and _valid(prev_info.get('sitting_posture_category'), POSTURE_SMALL_CATEGORIES)

def build_reuse_result(item, prev_info, sys_prompt, user_prompt):
    """用续测时读取到的旧结果重建 result_data 中对应行的完整数据。

    item:     输入测试集Excel的一行（records 形式）
    prev_info: load_prev_results 返回的该行 {model_output, tokens, cost_time}
    返回: 与原 process_single_image 返回的 result 结构一致的数据；旧答案为
          空（内容续测场景需要重跑的行）时返回 None，由调用方决定是否处理。
    """
    model_raw_answer = prev_info.get('model_output', '')
    if not model_raw_answer:
        return None
    golden_answers = {MODEL_FIELDS['attention_status']: item.get(EXCEL_COLUMNS['attention_status'], ''), MODEL_FIELDS['attention_category']: item.get(EXCEL_COLUMNS['attention_category'], ''), MODEL_FIELDS['sitting_posture_status']: item.get(EXCEL_COLUMNS['sitting_posture_status'], ''), MODEL_FIELDS['sitting_posture_category']: item.get(EXCEL_COLUMNS['sitting_posture_category'], '')}
    parsed_model_answer = parse_model_response(model_raw_answer)
    item_score = calculate_score(golden_answers, parsed_model_answer)
    img_path_rel = item.get(EXCEL_COLUMNS['image_path'], '')
    if img_path_rel is None:
        img_path_rel = ''
    img_path_rel = str(img_path_rel).replace('\\', '/')
    return {'用例编号': item.get(EXCEL_COLUMNS['case_id'], ''), '图片路径': img_path_rel, '系统Prompt': sys_prompt, '问题': user_prompt, '标准答案': golden_answers, '模型原始答案': model_raw_answer, '模型解析答案': parsed_model_answer, '单项得分': item_score, '是否正确': '是' if item_score == 1.0 else '否', 'token统计': prev_info.get('tokens', {'completion_tokens': 0, 'prompt_tokens': 0, 'total_tokens': 0}), '处理时间': 0, 'image_info': {'source': item.get(EXCEL_COLUMNS['image_source'], '') if not pd.isna(item.get(EXCEL_COLUMNS['image_source'])) else '', 'resolution': item.get(EXCEL_COLUMNS['resolution'], '') if not pd.isna(item.get(EXCEL_COLUMNS['resolution'])) else ''}, 'difficulty_level': {'attention_difficulty': item.get(EXCEL_COLUMNS['attention_difficulty'], ''), 'sitting_posture_difficulty': item.get(EXCEL_COLUMNS['sitting_posture_difficulty'], '')}}

def run_excel_eval(excel_path, eval_config, thread_id, reuse_map=None, on_batch_complete=None):
    """
    从Excel文件读取数据进行评估

    reuse_map: 续测复用映射 {index: prev_info}，提供时：
        - 索引续测：该 index 结果已存在且内容非空，直接复用不重新请求
        - 内容续测：仅复用结果符合预期（category 非空、非"未知"、且在
          对应小类集合内）的行；不在 reuse_map 中的行重新请求
    （reuse_map 由调用方 run_custom_posture_eval 按续测模式构造并过滤）

    on_batch_complete: 可选回调，按索引连续每满 BATCH_SIZE 条算完后触发，用于增量落盘。
        签名：on_batch_complete(result_data, end_index, total_score, valid_count, is_final)
        - result_data: 当前的 result_data 数组（result_data[:end_index] 为已算完段）
        - end_index: 本批连续段的终点索引（含）
        - total_score / valid_count: 截至目前累计得分/有效数（用于算累计平均分）
        - is_final: 是否最后一批（true 表示全部用例已算完，调用方应补完整统计）
        未提供时保持旧行为（不增量保存）。
    """
    model_name = eval_config['model_name']
    model_url = eval_config['model_url']
    temperature = eval_config['temperature']
    max_tokens = eval_config['max_tokens']
    user_prompt = eval_config['user_prompt']
    sys_prompt = eval_config['sys_prompt']
    eval_batch_size = eval_config['eval_batch_size']
    limit = eval_config['limit']
    body = eval_config['body']
    api_key = eval_config['api_key']
    print(f'api_key: {api_key}')
    reuse_map = reuse_map or {}
    if not os.path.exists(excel_path):
        logger.global_logger.error(f'Excel file not found: {excel_path}')
        raise FileNotFoundError(f'{excel_path} not found')
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        logger.global_logger.error(f'Failed to read Excel file: {e}')
        raise
    has_prev_image_col = EXCEL_COLUMNS['image_path_prev'] in df.columns
    base_path = os.path.dirname(excel_path)
    for index, item in df.iterrows():
        if limit is not None and index >= limit:
            break
        image_file_path = os.path.join(base_path, item[EXCEL_COLUMNS['image_path']].replace('\\', '/'))
        if not os.path.exists(image_file_path):
            raise FileNotFoundError(f'Image file not found: {image_file_path}')
        if has_prev_image_col and pd.notna(item[EXCEL_COLUMNS['image_path_prev']].replace('\\', '/')):
            prev_image_path = os.path.join(base_path, item[EXCEL_COLUMNS['image_path_prev']].replace('\\', '/'))
            if not os.path.exists(prev_image_path):
                raise FileNotFoundError(f'Previous image file not found: {prev_image_path}')
    excel_data = df.to_dict('records')

    def process_single_image(index, item):
        try:

            def parse_multi_part(text: str) -> str:
                match = re.search('MULTI:\\s*(.*)', text, re.DOTALL)
                if match:
                    return match.group(1).strip()
                return text

            def parse_single_part(text: str) -> str:
                single_match = re.search('SINGLE:\\s*(.*?)(?:\\s*MULTI:|$)', text, re.DOTALL)
                if single_match:
                    return single_match.group(1).strip()
                return text
            multi_sys_prompt = parse_multi_part(sys_prompt)
            multi_user_prompt = parse_multi_part(user_prompt)
            single_sys_prompt = parse_single_part(sys_prompt)
            single_user_prompt = parse_single_part(user_prompt)
            img_path_rel = item[EXCEL_COLUMNS['image_path']].replace('\\', '/')
            img_path_abs = os.path.join(base_path, img_path_rel)
            img_path_abs_prev = None
            has_two_images = False
            if has_prev_image_col and pd.notna(item.get(EXCEL_COLUMNS['image_path_prev']).replace('\\', '/')):
                img_path_prev_rel = item[EXCEL_COLUMNS['image_path_prev']].replace('\\', '/')
                img_path_abs_prev = os.path.join(base_path, img_path_prev_rel)
                has_two_images = True
            golden_answers = {MODEL_FIELDS['attention_status']: item[EXCEL_COLUMNS['attention_status']], MODEL_FIELDS['attention_category']: item[EXCEL_COLUMNS['attention_category']], MODEL_FIELDS['sitting_posture_status']: item[EXCEL_COLUMNS['sitting_posture_status']], MODEL_FIELDS['sitting_posture_category']: item[EXCEL_COLUMNS['sitting_posture_category']]}
            start_time = time.perf_counter()
            base64_image = encode_image(img_path_abs)
            base64_image_prev = encode_image(img_path_abs_prev) if img_path_abs_prev else None
            baseline_col = EXCEL_COLUMNS['baseline_image']
            has_baseline = baseline_col in item and pd.notna(item.get(baseline_col)) and (str(item.get(baseline_col, '')).strip() not in ('', '无'))
            baseline_path_abs = None
            if has_baseline:
                baseline_path_rel = str(item[baseline_col]).strip()
                baseline_path_abs = os.path.join(base_path, baseline_path_rel).replace('\\', '/')

            def is_field_valid(val):
                return val is not None and val != '' and (val != '未知')

            def request_with_retry(request_func, max_attempts=4, check_fields=None):
                """
                通用重试函数，统一管理重试逻辑。
                最多执行 max_attempts 次（1次首次 + max_attempts-1 次重试）。
                每次请求后检查指定的字段是否有效，全部有效则提前返回。
                返回 (最后一次响应文本, token信息)
                """
                if check_fields is None:
                    check_fields = ['attention_category', 'sitting_posture_category']
                last_raw_answer = ''
                last_token_info = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
                for attempt in range(max_attempts):
                    raw_answer, token_info = request_func()
                    last_raw_answer = raw_answer
                    last_token_info = token_info
                    if not raw_answer:
                        if attempt < max_attempts - 1:
                            logger.global_logger.info(f'模型请求失败，第{attempt + 2}次重试...')
                            time.sleep(1)
                        continue
                    parsed_temp = parse_model_response(raw_answer)
                    if all((is_field_valid(parsed_temp.get(k)) for k in check_fields)):
                        return (raw_answer, token_info)
                    if attempt < max_attempts - 1:
                        logger.global_logger.info(f'模型返回字段无效: {parsed_temp}，第{attempt + 2}次重试...')
                        time.sleep(1)
                return (last_raw_answer, last_token_info)
            if body != '':

                def single_request():
                    return request_unopen(model_url, img_path_abs_prev, img_path_abs, user_prompt, body, api_key, baseline_image=baseline_path_abs)
                model_raw_answer, token_info = request_with_retry(single_request)
            elif has_two_images:

                def multi_request():
                    return request_image(model_name, model_url, base64_image_prev, base64_image, multi_sys_prompt, multi_user_prompt, temperature, max_tokens, api_key)
                model_raw_answer_multi, token_info_multi = request_with_retry(multi_request, check_fields=['attention_category'])

                def single_request():
                    return request_image(model_name, model_url, base64_image, None, single_sys_prompt, single_user_prompt, temperature, max_tokens, api_key)
                model_raw_answer_single, token_info_single = request_with_retry(single_request, max_attempts=4, check_fields=['sitting_posture_category'])

                def safe_json_parse(raw_str):
                    if not raw_str:
                        return {}
                    parsed = extract_last_json(raw_str)
                    if parsed:
                        return parsed
                    logger.global_logger.warning(f'JSON解析失败，原始响应: {raw_str}')
                    return {}
                parsed_single = safe_json_parse(model_raw_answer_single)
                parsed_multi = safe_json_parse(model_raw_answer_multi)
                merged_answer = {}
                merged_answer.update(parsed_single)
                if 'attention_detection' in parsed_multi:
                    merged_answer.update(parsed_multi)
                model_raw_answer = json.dumps(merged_answer, ensure_ascii=False, indent=4, separators=(',', ': '))
                token_info = {'prompt_tokens': token_info_multi.get('prompt_tokens', 0) + token_info_single.get('prompt_tokens', 0), 'completion_tokens': token_info_multi.get('completion_tokens', 0) + token_info_single.get('completion_tokens', 0), 'total_tokens': token_info_multi.get('total_tokens', 0) + token_info_single.get('total_tokens', 0)}
            else:

                def single_request():
                    return request_image(model_name, model_url, base64_image, base64_image_prev, single_sys_prompt, single_user_prompt, temperature, max_tokens, api_key)
                model_raw_answer, token_info = request_with_retry(single_request)
            end_time = time.perf_counter()
            response_time = end_time - start_time
            parsed_model_answer = parse_model_response(model_raw_answer)
            item_score = calculate_score(golden_answers, parsed_model_answer)
            return {'status': 'success', 'index': index, 'result': {'用例编号': item.get(EXCEL_COLUMNS['case_id'], ''), '图片路径': img_path_rel, '系统Prompt': sys_prompt, '问题': user_prompt, '标准答案': golden_answers, '模型原始答案': model_raw_answer, '模型解析答案': parsed_model_answer, '单项得分': item_score, '是否正确': '是' if item_score == 1.0 else '否', 'token统计': token_info, '处理时间': response_time, 'image_info': {'source': item.get(EXCEL_COLUMNS['image_source'], '') if not pd.isna(item.get(EXCEL_COLUMNS['image_source'])) else '', 'resolution': item.get(EXCEL_COLUMNS['resolution'], '') if not pd.isna(item.get(EXCEL_COLUMNS['resolution'])) else ''}, 'difficulty_level': {'attention_difficulty': item.get(EXCEL_COLUMNS['attention_difficulty'], ''), 'sitting_posture_difficulty': item.get(EXCEL_COLUMNS['sitting_posture_difficulty'], '')}}, 'score': item_score}
        except Exception as e:
            logger.global_logger.error(f'处理索引 {index} 时出错: {str(e)}')
            return {'status': 'error', 'index': index, 'error': str(e), 'score': 0.0}
    max_workers = eval_batch_size if eval_batch_size is not None and eval_batch_size != 0 else 10
    total_tasks = min(limit, len(excel_data)) if limit is not None else len(excel_data)
    result_data = [None] * total_tasks
    pending_indices = list(range(total_tasks))
    active_futures = []
    total_score = 0
    valid_count = 0
    next_batch_end = 0
    if reuse_map:
        for idx in pending_indices[:]:
            prev_info = reuse_map.get(idx)
            if prev_info is None:
                continue
            try:
                reused = build_reuse_result(excel_data[idx], prev_info, sys_prompt, user_prompt)
            except Exception as e:
                logger.global_logger.warning(f'续测：重建第{idx}行旧结果失败，将重新处理：{e}')
                continue
            if reused is not None:
                result_data[idx] = reused
                total_score += reused['单项得分']
                valid_count += 1
                pending_indices.remove(idx)
                logger.global_logger.info(f"-> 续测复用 {idx + 1}/{total_tasks}, 得分: {reused['单项得分']} <-")
    executor = ThreadPoolExecutor(max_workers=max_workers)

    def process_completed_tasks():
        nonlocal total_score, valid_count
        done_futures = []
        for future in active_futures[:]:
            if future.done():
                done_futures.append(future)
                active_futures.remove(future)
        for future in done_futures:
            try:
                result = future.result()
                if result['status'] == 'success':
                    idx = result['index']
                    result_data[idx] = result['result']
                    total_score += result['score']
                    valid_count += 1
                    logger.global_logger.info(f"-> 已完成 {idx + 1}/{total_tasks}, 得分: {result['score']} <-")
                else:
                    logger.global_logger.warning(f"任务失败: {result['error']}")
            except Exception as e:
                logger.global_logger.error(f'任务处理异常: {str(e)}')
    while pending_indices or active_futures:
        with thread_controls_lock:
            control_info = thread_controls.get(thread_id, {'paused': False})
            is_paused = control_info['paused']
        process_completed_tasks()
        if on_batch_complete is not None:
            while next_batch_end + BATCH_SIZE <= total_tasks and all((r is not None for r in result_data[next_batch_end:next_batch_end + BATCH_SIZE])):
                next_batch_end += BATCH_SIZE
                on_batch_complete(result_data, next_batch_end, total_score, valid_count, False)
        if is_paused:
            time.sleep(0.5)
            continue
        while pending_indices and len(active_futures) < max_workers:
            idx = pending_indices.pop(0)
            item = excel_data[idx]
            logger.global_logger.info(f'开始任务：{idx + 1}/{total_tasks}')
            future = executor.submit(process_single_image, idx, item)
            active_futures.append(future)
        if active_futures:
            done, _ = concurrent.futures.wait(active_futures, timeout=0.5, return_when=concurrent.futures.FIRST_COMPLETED)
        else:
            time.sleep(0.1)
    executor.shutdown(wait=True)
    process_completed_tasks()
    if on_batch_complete is not None:
        on_batch_complete(result_data, total_tasks, total_score, valid_count, True)
    avg_score = total_score / valid_count if valid_count > 0 else 0
    return (result_data, avg_score, valid_count)

def gen_review_xlsx(excel_path, result_data, review_path, dataset_name, task_id, limit, subset_list, run_full_flow=True, run_index=None):
    """在现有Excel基础上追加评测结果列

    Args:
        run_full_flow: 是否执行完整流程（calculate_accuracy_with_styles + 统计）
        run_index: 第几轮运行（稳定性业务多轮时使用，为None则用原文件名）
    """
    if run_index is not None:
        output_file_name = os.path.join(review_path, f'{dataset_name}报告_{task_id}_run{run_index}.xlsx')
    else:
        output_file_name = os.path.join(review_path, f'{dataset_name}报告_{task_id}.xlsx')
    os.makedirs(os.path.dirname(output_file_name), exist_ok=True)
    from openpyxl import load_workbook
    wb = load_workbook(excel_path)
    sheet_name = wb.sheetnames[0]
    ws = wb[sheet_name]
    last_col = 1
    for row in ws.iter_rows(min_row=1, max_row=1):
        for cell in row:
            if cell.value is not None:
                last_col = cell.column
    start_col = last_col + 1
    case_id_col = None
    for cell in ws[1]:
        if cell.value == '用例编号':
            case_id_col = cell.column
            break
    if case_id_col is None:
        logger.global_logger.error("源文件中未找到'用例编号'列，无法匹配数据")
        return
    col_mapping = {}
    headers = ['attention_status', 'attention_category', 'sitting_posture_status', 'sitting_posture_category', 'completion_tokens', 'prompt_tokens', 'total_tokens', 'cost_time', 'model_output']
    for idx, header in enumerate(headers, start=start_col):
        col_mapping[header] = idx
        ws.cell(row=1, column=idx, value=header)
    case_id_to_row = {}
    for row_idx in range(2, ws.max_row + 1):
        case_id = ws.cell(row=row_idx, column=case_id_col).value
        if case_id is not None and str(case_id).strip():
            case_id_to_row[str(case_id).strip()] = row_idx
    for item in result_data:
        case_id = str(item.get('用例编号', '')).strip()
        if not case_id or case_id not in case_id_to_row:
            logger.global_logger.warning(f'未找到匹配的用例编号: {case_id}')
            continue
        row_idx = case_id_to_row[case_id]
        parsed_ans = item['模型解析答案']
        std_ans = item['标准答案']
        ws.cell(row=row_idx, column=col_mapping['attention_status'], value=parsed_ans['attention_status'])
        ws.cell(row=row_idx, column=col_mapping['attention_category'], value=parsed_ans['attention_category'])
        ws.cell(row=row_idx, column=col_mapping['sitting_posture_status'], value=parsed_ans['sitting_posture_status'])
        ws.cell(row=row_idx, column=col_mapping['sitting_posture_category'], value=parsed_ans['sitting_posture_category'])
        tokens = item['token统计']
        ws.cell(row=row_idx, column=col_mapping['completion_tokens'], value=tokens['completion_tokens'])
        ws.cell(row=row_idx, column=col_mapping['prompt_tokens'], value=tokens['prompt_tokens'])
        ws.cell(row=row_idx, column=col_mapping['total_tokens'], value=tokens['total_tokens'])
        ws.cell(row=row_idx, column=col_mapping['cost_time'], value=item['处理时间'])
        ws.cell(row=row_idx, column=col_mapping['model_output'], value=item['模型原始答案'])
    wb.save(output_file_name)
    print(f'评测报告已保存至: {output_file_name}')
    logger.global_logger.info(f'评测报告已生成')
    if run_full_flow:
        if '时延分布' in subset_list:
            cos_data, avg_time, total = analyze_cost_time(output_file_name)
            write_to_excel(output_file_name, cos_data, (avg_time, total), None, '时延分布统计')
            accuracy_dict = {}
        else:
            preprocess_excel(output_file_name, None)
            calculate_accuracy_with_styles(output_file_name)
            logger.global_logger.info(f'评测结果集成完毕')
            accuracy_dict = processExcel(output_file_name, limit)
        logger.global_logger.info(f'评测结果统计完毕,accuracy_dict={accuracy_dict}')
        return accuracy_dict
    else:
        logger.global_logger.info(f'跳过完整流程（仅生成结果Excel）')
        return output_file_name

def gen_review_jsonl(result_data, review_path, dataset_name, stability_index=None):
    """生成用于人工审核的jsonl文件

    Args:
        stability_index: 稳定性业务的轮次标记（1/2/3），非稳定性业务为None
    """
    review_lines = []
    for index, item in enumerate(result_data):
        record = {'raw_input': {'img': item['图片路径'], 'Answer': item['标准答案'], 'No': index, 'Sys_prompt': item['系统Prompt'], 'Question': item['问题']}, 'choices': [{'review': {'gold': item['标准答案'], 'pred': item['模型解析答案'], 'result': item['单项得分']}, 'message': {'content': item['模型原始答案']}}], 'index': index, 'subset_name': 'default', 'usage': item['token统计'], 'response_time': item['处理时间'], 'image_info': item['image_info'], 'difficulty_level': item['difficulty_level']}
        if stability_index is not None:
            record['index'] = str(stability_index - 1) + '-' + str(index)
        review_lines.append(record)
    review_file: str = os.path.join(review_path, f'{dataset_name}_default.jsonl')
    dump_mode = DumpMode.OVERWRITE if stability_index is None or stability_index == 1 else DumpMode.APPEND
    dump_jsonl_data(review_lines, review_file, dump_mode=dump_mode)
    logger.global_logger.info(f'Review JSONL generated (stability_index={stability_index})')

def save_review_jsonl_batch(batch_result_data, end_index, review_path, dataset_name, mode=DumpMode.APPEND):
    """将已完成的前 end_index 条评测结果写入jsonl（用于每满一批增量保存/断点保护）。

    Args:
        batch_result_data: run_excel_eval 的 result_data 数组（按索引填充，未完成项为 None）
        end_index: 已算完的连续段终点（只写 result_data[:end_index] 中非 None 的行）
        review_path: 输出目录
        dataset_name: 数据集名（用于拼文件名 {dataset_name}_default.jsonl）
        mode: DumpMode.APPEND（增量追加，中间批）或 DumpMode.OVERWRITE（覆盖，最终批）
    """
    review_lines = []
    for idx, item in enumerate(batch_result_data[:end_index]):
        if item is None:
            continue
        record = {'raw_input': {'img': item['图片路径'], 'Answer': item['标准答案'], 'No': idx, 'Sys_prompt': item['系统Prompt'], 'Question': item['问题']}, 'choices': [{'review': {'gold': item['标准答案'], 'pred': item['模型解析答案'], 'result': item['单项得分']}, 'message': {'content': item['模型原始答案']}}], 'index': idx, 'subset_name': 'default', 'usage': item['token统计'], 'response_time': item['处理时间'], 'image_info': item['image_info'], 'difficulty_level': item['difficulty_level']}
        review_lines.append(record)
    review_file = os.path.join(review_path, f'{dataset_name}_default.jsonl')
    dump_jsonl_data(review_lines, review_file, dump_mode=mode)
    logger.global_logger.info(f'Review JSONL batch saved (mode={mode}, {len(review_lines)} 条)')

def gen_report_json(model_name, report_path, avg_score, accuracy_dict, total_count, dataset_name):
    """生成评测报告JSON文件"""
    print(f'accuracy_dict:{accuracy_dict}')
    subsets = []
    special_keywords = ['注意力检测', '坐姿检测']
    if accuracy_dict is not None:
        for keyword in special_keywords:
            if keyword in accuracy_dict:
                keyword_info = accuracy_dict[keyword]
                subsets.append({'name': keyword, 'num': keyword_info['num'], 'score': float(keyword_info['score'].rstrip('%')) / 100, 'subsets': keyword_info.get('subsets', [])})
    report_map = {'name': f'{model_name}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_name, 'score': avg_score, 'metrics': [{'categories': [{'macro_score': avg_score, 'name': ['default'], 'num': total_count, 'score': avg_score, 'subsets': subsets}], 'macro_score': avg_score, 'name': 'AverageAccuracy', 'num': total_count, 'score': avg_score}]}
    report_path_file = os.path.join(report_path, f'{dataset_name}.json')
    os.makedirs(os.path.dirname(report_path_file), exist_ok=True)
    with open(report_path_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps(report_map, ensure_ascii=False, indent=4))
    logger.global_logger.info('报告JSON已生成')

def run_custom_posture_eval(task_config, dataset_name, limit, thread_id, temperature=0, max_tokens=1024):
    """
    执行自定义的儿童伴读
    """
    model_name = task_config['model_name']
    model_url = task_config['api_url']
    excel_path = task_config['excel_path']
    output_dir = task_config['output_path']
    eval_batch_size = task_config.get('eval_batch_size', 10)
    subset_list = task_config.get('subset_list', ['default'])
    api_key = task_config.get('api_key', 'EMPTY')
    user_prompt = re.sub('\\\\n', '\n', task_config['user_prompt'])
    sys_prompt = re.sub('\\\\n', '\n', task_config['sys_prompt'])
    task_id = task_config['task_id']
    log_path = os.path.join(output_dir, 'logs')
    os.makedirs(log_path, exist_ok=True)
    logger.global_logger = logger.Logger('eval_log')
    logger.global_logger.update_log_dir(log_path)
    logger.global_logger.info(f'开始模型评测: {model_name}')
    logger.global_logger.info(f'**** Start evaluating on dataset {dataset_name} ****')
    print_config = task_config.copy()
    print_config['user_prompt'] = user_prompt
    print_config['sys_prompt'] = sys_prompt

    class CustomJSONEncoder(json.JSONEncoder):

        def default(self, obj):
            if isinstance(obj, str):
                return obj
            return super().default(obj)
    formatted_config = json.dumps(print_config, indent=2, ensure_ascii=False, cls=CustomJSONEncoder, sort_keys=True)
    logger.global_logger.info(f'任务参数: \n{formatted_config}')
    model_output_dir = os.path.join(output_dir, 'reviews', model_name.replace('/', '_').replace('\\', '_'))
    report_path = os.path.join(output_dir, 'reports', model_name.replace('/', '_').replace('\\', '_'))
    os.makedirs(model_output_dir, exist_ok=True)
    os.makedirs(report_path, exist_ok=True)
    eval_config = {'model_name': model_name, 'model_url': model_url, 'temperature': temperature, 'max_tokens': max_tokens, 'user_prompt': user_prompt, 'sys_prompt': sys_prompt, 'eval_batch_size': eval_batch_size, 'limit': limit, 'body': task_config['body'] if 'body' in task_config else '', 'api_key': api_key}
    retry_enabled = bool(task_config.get('retry_enabled'))
    retry_content_none = bool(task_config.get('retry_content_none', False))
    reuse_map = {}
    if retry_enabled:
        prev_results = load_prev_results(model_output_dir, dataset_name, task_id)
        reuse_map = {idx: info for idx, info in prev_results.items() if info.get('model_output')}
        if retry_content_none:
            reuse_map = {idx: info for idx, info in reuse_map.items() if _is_result_expectable(info)}
        logger.global_logger.info(f"续测({('内容续测' if retry_content_none else '索引续测')})：旧结果可复用 {len(reuse_map)} 行")
    if '稳定性' in subset_list:
        stability_excel_paths = []
        for run_idx in range(3):
            logger.global_logger.info(f'稳定性评测: 第{run_idx + 1}/3轮开始')
            run_result_data, run_avg_score, run_total_count = run_excel_eval(excel_path, eval_config, thread_id)
            is_first = run_idx == 0
            run_excel_path = gen_review_xlsx(excel_path, run_result_data, model_output_dir, dataset_name, task_id, limit, subset_list, run_full_flow=is_first, run_index=run_idx + 1)
            if is_first:
                run_excel_file = os.path.join(model_output_dir, f'{dataset_name}报告_{task_id}_run1.xlsx')
                run_accuracy_dict = run_excel_path
                gen_report_json(model_name, report_path, run_avg_score, run_accuracy_dict, run_total_count, dataset_name)
                logger.global_logger.info(f'稳定性第1轮: 平均分 {run_avg_score:.2f}')
            else:
                run_excel_file = run_excel_path
                logger.global_logger.info(f'稳定性第{run_idx + 1}轮: 仅生成结果Excel')
            gen_review_jsonl(run_result_data, model_output_dir, dataset_name, stability_index=run_idx + 1)
            stability_excel_paths.append(run_excel_file)
            with thread_controls_lock:
                if thread_id in thread_controls:
                    thread_controls[thread_id]['paused'] = False
        logger.global_logger.info('开始稳定性分析...')
        stability_data = analyze_stability(stability_excel_paths)
        output_stability_file = os.path.join(model_output_dir, f'{dataset_name}_稳定性分析_{task_id}.xlsx')
        merge_excel_files(stability_excel_paths, output_stability_file)
        write_to_excel(output_stability_file, stability_data=stability_data)
        logger.global_logger.info(f'稳定性分析完成，结果已保存至: {output_stability_file}')
        logger.global_logger.info(f'稳定性评测完成: {model_name}')
    else:

        def on_batch_complete(batch_result_data, end_index, cur_score, cur_count, is_final):
            """每满 BATCH_SIZE 条（或全部完成）触发一次：增量落盘 excel/jsonl/json。

            - excel：中间批仅写结果列（不跑统计），最后一批跑完整统计并返回 accuracy_dict；
            - jsonl：中间批 append，最后一批覆盖保证最终文件干净完整；
            - json：中间批用累计统计生成简化报告，最后一批用完整 accuracy_dict。
            """
            done_items = [r for r in batch_result_data[:end_index] if r is not None]
            acc = gen_review_xlsx(excel_path, done_items, model_output_dir, dataset_name, task_id, limit, subset_list, run_full_flow=is_final)
            save_review_jsonl_batch(batch_result_data, end_index, model_output_dir, dataset_name, mode=DumpMode.OVERWRITE if is_final else DumpMode.APPEND)
            gen_report_json(model_name, report_path, cur_score, acc if is_final else None, cur_count, dataset_name)
        result_data, avg_score, total_count = run_excel_eval(excel_path, eval_config, thread_id, reuse_map=reuse_map if retry_enabled else None, on_batch_complete=on_batch_complete)
        logger.global_logger.info(f'评测完成: {model_name} 平均分: {avg_score:.2f}')
