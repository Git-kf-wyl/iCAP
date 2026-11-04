# Private iCAP Yellow business implementation. Do not publish.
import os.path
from jiwer import wer
from services.multi.utils.eval_utils import *
DATASET_META_FILE_NAME = 'meta_data.json'

def run_subset(eval_info, model_info, subset_name: str):
    my_custom_logger.info(f'cur_subset_name: {subset_name}')
    data_set_path = eval_info['input_path']
    data_set_name = eval_info['dataset_name']
    model_id_basename = os.path.basename(model_info['model_id']).rstrip(os.sep)
    review_path = f"{eval_info['output_path']}/{model_id_basename}"
    limit = eval_info['limit']
    model_name = model_info['model_name']
    model_url = model_info['model_url']
    cur_meta_data_path = os.path.join(data_set_path, 'audio', subset_name, DATASET_META_FILE_NAME)
    if not os.path.exists(cur_meta_data_path):
        my_custom_logger.info(f'Warning: {cur_meta_data_path} not found')
        raise FileNotFoundError(f'{cur_meta_data_path} meta data file not found')
    eval_data = pd.read_json(cur_meta_data_path)
    t_count = len(eval_data)
    result_data = []
    eval_data['model_answer'] = ''
    if limit is None or limit == 0:
        limit = t_count
    average_score = 0
    total_count = 0
    for idx, item in eval_data.iterrows():
        if idx > limit - 1:
            break
        audio_path = os.path.join(data_set_path, item['path'])
        if not os.path.exists(audio_path):
            my_custom_logger.error(f'Warning: {audio_path} not found')
            raise FileNotFoundError(f'{audio_path} audio file not found')
        base64_audio = encode_audio_base64_from_file(audio_path, 'audio/flac')
        prompt = 'Transcribe the speech into text without adding any punctuation.'
        try:
            model_answer = request_audio(model_name, model_url, '', base64_audio, prompt)
        except Exception as e:
            my_custom_logger.error(f'model:{model_name} req err {e}')
            model_answer = ''
        model_answer = model_answer.upper()
        eval_data.loc[idx, 'model_answer'] = model_answer
        if MLLM_CUSTOM_DATASETS_DEBUG_FLAG:
            my_custom_logger.info(f"gold_answer:{item['text']}")
            my_custom_logger.info(f'model_answer:{model_answer}')
        wer_score = wer(item['text'], model_answer)
        my_custom_logger.info(f'question index: {idx}, wer: {wer_score}')
        score = wer_score
        result_data.append({'音频路径': audio_path, '问题': prompt, '标准答案': item['text'], '模型答案': model_answer, 'WER': score})
        total_count += 1
        average_score += score
    average_score = round(average_score / total_count, 4)
    real_score = wer(eval_data['text'].tolist(), eval_data['model_answer'].tolist())
    my_custom_logger.info(f'取均值WER: {average_score}, 整体list计算WER: {real_score}')
    gen_review_excel(data_set_name, subset_name, result_data, review_path)
    gen_review_jsonl(result_data, review_path, data_set_name, subset_name, True)
    return (total_count, average_score)

def run_librispeech_eval(model_info, eval_info):
    output_path = eval_info['output_path']
    log_path = f'{output_path}/logs'
    my_custom_logger.update_log_dir(log_path)
    model_name = model_info['model_name']
    dataset_name = eval_info['dataset_name']
    my_custom_logger.info(f'cur_dataset: {dataset_name}')
    report_map = {'name': f'{model_name}_{dataset_name}', 'dataset_name': dataset_name, 'model_name': model_name, 'score': 0.0, 'metrics': [{'categories': [{'name': ['default'], 'num': 0, 'score': 0.0, 'subsets': []}], 'name': 'AverageAccuracy', 'num': 0, 'score': 0.0}]}
    ave_score = 0.0
    total_count = 0
    for subset_name in eval_info['subset_list']:
        eval_res = run_subset(eval_info, model_info, subset_name)
        my_custom_logger.info(f'eval_res: {eval_res}')
        report_map['metrics'][0]['categories'][0]['subsets'].append({'name': subset_name, 'num': eval_res[0], 'score': eval_res[1]})
        total_count += eval_res[0]
        ave_score += eval_res[1]
    ave_score = round(ave_score / len(eval_info['subset_list']), 4)
    report_map['score'] = ave_score
    report_map['metrics'][0]['score'] = ave_score
    report_map['metrics'][0]['num'] = total_count
    report_map['metrics'][0]['categories'][0]['score'] = ave_score
    report_map['metrics'][0]['categories'][0]['num'] = total_count
    model_id_basename = os.path.basename(model_info['model_id']).rstrip(os.sep)
    report_path = f"{eval_info['output_path']}/{model_id_basename}"
    write_report_json(report_path, dataset_name, report_map)
