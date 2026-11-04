# Private iCAP Yellow business implementation. Do not publish.
import glob
import os.path
import re
from services.multi.utils.eval_utils import *
from utils.io_utils import *

def string_match(answer, prediction, choices):

    def tokenize(text):
        return set(re.findall('\\b\\w+\\b', text.lower()))
    prediction_tokens = tokenize(prediction)
    answer_tokens = tokenize(answer)
    if not prediction_tokens:
        return False
    incorrect_tokens = set()
    for choice in choices:
        choice_tokens = tokenize(choice)
        if choice_tokens != answer_tokens:
            incorrect_tokens.update(choice_tokens - answer_tokens)
    cond1 = answer_tokens.issubset(prediction_tokens)
    cond2 = prediction_tokens.isdisjoint(incorrect_tokens)
    return cond1 and cond2

def is_success(golden_ans, llm_ans, choices) -> bool:
    return string_match(golden_ans, llm_ans, choices)

def run_dataset_eval(data_set_path, limit, model_info, dataset_name):
    audio_key = 'audio_path' if dataset_name.lower() == 'mmar' else 'WavPath'
    dataset_file_path = os.path.join(data_set_path, '*meta.json')
    files = glob.glob(dataset_file_path)
    if len(files) < 1:
        raise FileNotFoundError(f'Test meta files not found')
    dataset_file = files[0]
    if not os.path.exists(dataset_file):
        raise FileNotFoundError(f'Test meta data file {dataset_file} not found')
    eval_data = json.load(open(dataset_file, 'r', encoding='utf-8'))
    t_count = len(eval_data)
    if limit is None or limit == 0:
        limit = t_count
    else:
        limit = min(limit, t_count)
    result_data = []
    suc_count = 0
    for index, item in enumerate(eval_data):
        if index > limit - 1:
            break
        audio_file_path = os.path.join(data_set_path, item[audio_key])
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f'{item[audio_key]} audio in test meta data file not found')
        base64_audio = encode_audio_base64_from_file(audio_file_path)
        choices = '\n'.join(item['choices'])
        prompt = f"{item['question']}\nOptions:\n{choices}\nAnswer with the full correct sentence exactly as written in the options.\n"
        model_name = model_info['model_name']
        model_url = model_info['model_url']
        api_key = model_info.get('api_key', '')
        try:
            model_answer = request_audio(model_name, model_url, api_key, base64_audio, prompt)
        except Exception as e:
            my_custom_logger.error(f'model:{model_name} req err {e}')
            model_answer = ''
        if MLLM_CUSTOM_DATASETS_DEBUG_FLAG:
            my_custom_logger.info(f"gold_answer: {item['answer']}")
            my_custom_logger.info(f'model_answer: {model_answer}')
        is_suc = is_success(item['answer'], model_answer, item['choices'])
        if is_suc:
            suc_count += 1
        result_data.append({'音频路径': str(item[audio_key]), '问题': str(item['question']), '选项': str(item['choices']), '标准答案': str(item['answer']), '模型答案': model_answer, '是否正确': 1 if is_suc else 0})
        my_custom_logger.info(f'->The index of currently executed is {index + 1}, and the total number is {limit}.<-')
    return (result_data, suc_count, limit)

def gen_audio_review_jsonl(result_data, review_path, dataset_name):
    review_lines = []
    for index, da in enumerate(result_data):
        review_lines.append({'raw_input': {'audio': da['音频路径'], 'Answer': da['模型答案'], 'No': index, 'Question': da['问题'] + '\nOptions:\n' + da['选项']}, 'choices': [{'review': {'gold': da['标准答案'], 'pred': da['模型答案'], 'result': da['是否正确']}, 'message': {'content': da['模型答案']}}], 'index': index, 'subset_name': 'default'})
    review_file: str = os.path.join(review_path, f'{dataset_name}_default.jsonl')
    dump_jsonl_data(review_lines, review_file, dump_mode=DumpMode.APPEND)

def run_custom_audio_eval(model_info, eval_info):
    log_path = f"{eval_info['output_path']}/logs"
    my_custom_logger.update_log_dir(log_path)
    data_set_name = eval_info['input_path'].split('/')[-1]
    my_custom_logger.info(f'dataset: {data_set_name}')
    model_id_basename = os.path.basename(model_info['model_id']).rstrip(os.sep)
    review_path = f"{eval_info['output_path']}/{model_id_basename}"
    report_path = f"{eval_info['output_path']}/{model_id_basename}"
    result_data, suc_count, total_count = run_dataset_eval(eval_info['input_path'], eval_info['limit'], model_info, data_set_name)
    gen_review_excel(data_set_name, 'default', result_data, review_path)
    gen_audio_review_jsonl(result_data, review_path, data_set_name)
    gen_report_json(model_info['model_name'], report_path, suc_count, total_count, data_set_name)
