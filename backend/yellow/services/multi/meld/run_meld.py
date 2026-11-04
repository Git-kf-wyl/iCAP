# Private iCAP Yellow business implementation. Do not publish.
import os.path
from services.multi.utils.eval_utils import *
DATASET_META_FILE_NAME = 'test_sent_emo.csv'

def run_dataset_eval(data_set_path, limit, model_name, model_url):
    dataset_file = os.path.join(data_set_path, 'data', DATASET_META_FILE_NAME)
    if not os.path.exists(dataset_file):
        raise FileNotFoundError(f'Test meta data file {dataset_file} not found')
    eval_data = pd.read_csv(dataset_file)
    t_count = len(eval_data)
    if limit is None or limit == 0:
        limit = t_count
    else:
        limit = min(limit, t_count)

    def is_match(gold_ans, llm_ans):
        return llm_ans.lower() in gold_ans.lower()
    result_data = []
    suc_count = 0
    for idx, item in eval_data.iterrows():
        if idx > limit - 1:
            break
        file_name = f"dia{item['Dialogue_ID']}_utt{item['Utterance_ID']}.wav"
        audio_file_path = os.path.join(data_set_path, 'data', 'audio', file_name)
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f'{audio_file_path} audio in test meta data file not found')
        base64_audio = encode_audio_base64_from_file(audio_file_path)
        prompt = 'You are a helpful assistant that classifies emotions in dialogue. You must respond ONLY with the emotion label: anger, disgust, fear, joy, neutral, sadness, or surprise.'
        try:
            model_answer = request_audio(model_name, model_url, '', base64_audio, prompt)
        except Exception as e:
            my_custom_logger.error(f'model:{model_name} req err {e}')
            model_answer = ''
        if MLLM_CUSTOM_DATASETS_DEBUG_FLAG:
            my_custom_logger.info(f"gold_answer:{item['Emotion']}")
            my_custom_logger.info(f'model_answer:{model_answer}')
        is_suc = is_match(str(item['Emotion']), model_answer)
        if is_suc:
            suc_count += 1
        result_data.append({'音频路径': file_name, '问题': prompt, '标准答案': str(item['Emotion']), '模型答案': model_answer, '是否正确': 1 if is_suc else 0})
        my_custom_logger.info(f'->The index of currently executed is {idx + 1}, and the total number is {limit}.<-')
    return (result_data, suc_count, limit)

def run_meld_eval(model_info, eval_info):
    output_path = eval_info['output_path']
    log_path = f'{output_path}/logs'
    my_custom_logger.update_log_dir(log_path)
    data_set_name = eval_info['dataset_name']
    my_custom_logger.info(f'cur_dataset: {data_set_name}')
    result_data, suc_count, total_count = run_dataset_eval(eval_info['input_path'], eval_info['limit'], model_info['model_name'], model_info['model_url'])
    model_id_basename = os.path.basename(model_info['model_id']).rstrip(os.sep)
    review_path = f"{eval_info['output_path']}/{model_id_basename}"
    gen_review_excel(data_set_name, 'default', result_data, review_path)
    gen_review_jsonl(result_data, review_path, data_set_name, 'default', False)
    report_path = f"{eval_info['output_path']}/{model_id_basename}"
    gen_report_json(model_info['model_name'], report_path, suc_count, total_count, data_set_name)
