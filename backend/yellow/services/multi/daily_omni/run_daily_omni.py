# Private iCAP Yellow business implementation. Do not publish.
from concurrent.futures import as_completed, ThreadPoolExecutor
from functools import partial
from services.multi.utils.eval_utils import *
DATASET_JSON_NAME = 'qa.json'

def process_single_item_worker(item_data, idx, model_info, base_path, model_function):
    question = item_data.get('Question', None)
    choices = item_data.get('Choice', None)
    correct_answer_char = item_data.get('Answer', None)
    video_id = item_data.get('video_id', None)
    qa_type = item_data.get('Type', None)
    video_category = item_data.get('video_category', None)
    video_duration = item_data.get('video_duration', None)
    my_custom_logger.info(f'Process num {idx}')
    if not all([question, choices, correct_answer_char, video_id, qa_type, video_category, video_duration]):
        return {'skipped': True, '视频路径': video_id, '问题': question, '模型答案': 'error_missing_fields', '标准答案': correct_answer_char, '是否正确': False, '是否api调用失败': False, 'qa_type': qa_type, 'video_category': video_category, 'video_duration': video_duration}
    video_path = get_video_path(video_id, base_path)
    if not os.path.exists(video_path):
        my_custom_logger.info(f'Warning: Video file not found for ID {video_id} at {video_path}')
        return {'skipped': True, '视频路径': video_path, '问题': question, '模型答案': 'error_video_not_found', '标准答案': correct_answer_char, '是否正确': False, '是否api调用失败': False, 'qa_type': qa_type, 'video_category': video_category, 'video_duration': video_duration}
    model_name = model_info.get('model_name', None)
    model_url = model_info.get('model_url', None)
    if model_name is None or model_url is None:
        return {'skipped': True, '视频路径': video_path, '问题': question, '模型答案': 'error_model_name_none', '标准答案': correct_answer_char, '是否正确': False, '是否api调用失败': False, 'qa_type': qa_type, 'video_category': video_category, 'video_duration': video_duration}
    api_answer = model_function(model_name, model_url, question, choices, video_path, my_custom_logger)
    if MLLM_CUSTOM_DATASETS_DEBUG_FLAG:
        my_custom_logger.info(f'Question: [{question[:30]}...], model answer: [{api_answer[:30]}]')
    api_call_failed = isinstance(api_answer, str) and api_answer.startswith('error_')
    is_correct = False
    if not api_call_failed:
        is_correct = evaluate_answer(api_answer, correct_answer_char)
    return {'skipped': False, '视频路径': video_path, '问题': question, '模型答案': api_answer, '标准答案': correct_answer_char, '是否正确': is_correct, '是否api调用失败': api_call_failed, 'qa_type': qa_type, 'video_category': video_category, 'video_duration': video_duration}

def run_daily_omni_tests(model_info, eval_info):
    output_path = eval_info['output_path']
    log_path = f'{output_path}/logs'
    my_custom_logger.update_log_dir(log_path)
    data_set_name = eval_info['dataset_name']
    my_custom_logger.info(f'--- Starting Tests {data_set_name}---')
    data_set_path = eval_info.get('input_path', None)
    if data_set_path is None:
        my_custom_logger.error('Error: data_set_path is None. Exiting.')
        return
    qa_json_path = os.path.join(data_set_path, DATASET_JSON_NAME)
    all_data = load_json_data(qa_json_path, my_custom_logger)
    if not all_data:
        my_custom_logger.error('Error: No data loaded. Exiting.')
        return
    max_items = eval_info.get('limit', 0)
    if max_items is not None and max_items > 0:
        my_custom_logger.info(f'Limiting processing to first {max_items} items.')
        data_to_process = all_data[:max_items]
    else:
        data_to_process = all_data
    total_items_requested = len(data_to_process)
    my_custom_logger.info(f'Total {total_items_requested} items to process.')
    if total_items_requested == 0:
        my_custom_logger.error('No items selected for processing.')
        return
    all_results = []
    start_time = time.time()
    num_workers = eval_info.get('num_workers', 1)
    worker_func_with_model = partial(process_single_item_worker, model_function=request_model_video)
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_func_with_model, item, idx, model_info, data_set_path) for idx, item in enumerate(data_to_process)]
        for future in as_completed(futures):
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                my_custom_logger.error(f'\nError retrieving result from worker process: {e}')
    end_time = time.time()
    my_custom_logger.info(f'\n--- Testing Complete ---')
    my_custom_logger.info(f'Total processing time: {end_time - start_time:.2f} seconds')
    suc_count, total_process_count = get_suc_count(all_results)
    model_id_basename = os.path.basename(model_info['model_id']).rstrip(os.sep)
    review_path = f"{eval_info['output_path']}/{model_id_basename}"
    gen_review_excel(data_set_name, 'default', all_results, review_path)
    gen_review_jsonl(all_results, review_path, data_set_name, 'default', False)
    gen_report_json(model_info['model_name'], review_path, suc_count, total_process_count, data_set_name)
