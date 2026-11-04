# Private iCAP Yellow business implementation. Do not publish.
import glob
import os.path
import re
import string
from string import punctuation
import jieba
from jiwer import wer
from services.multi.utils.eval_utils import *
from utils.io_utils import *
language_dict = {'af': 'Afrikaans', 'am': 'Amharic', 'ar': 'Arabic', 'hy': 'Armenian', 'as': 'Assamese', 'ast': 'Asturian', 'az': 'Azerbaijani', 'be': 'Belarusian', 'bn': 'Bengali', 'bs': 'Bosnian', 'bg': 'Bulgarian', 'my': 'Burmese', 'ca': 'Catalan', 'ceb': 'Cebuano', 'cmn_hans': 'Mandarin Chinese', 'yue_hant': 'Cantonese Chinese', 'hr': 'Croatian', 'cs': 'Czech', 'da': 'Danish', 'nl': 'Dutch', 'en': 'English', 'et': 'Estonian', 'fil': 'Filipino', 'fi': 'Finnish', 'fr': 'French', 'ff': 'Fula', 'gl': 'Galician', 'lg': 'Ganda', 'ka': 'Georgian', 'de': 'German', 'el': 'Greek', 'gu': 'Gujarati', 'ha': 'Hausa', 'he': 'Hebrew', 'hi': 'Hindi', 'hu': 'Hungarian', 'is': 'Icelandic', 'ig': 'Igbo', 'id': 'Indonesian', 'ga': 'Irish', 'it': 'Italian', 'ja': 'Japanese', 'jv': 'Javanese', 'kea': 'Kabuverdianu', 'kam': 'Kamba', 'kn': 'Kannada', 'kk': 'Kazakh', 'km': 'Khmer', 'ko': 'Korean', 'ky': 'Kyrgyz', 'lo': 'Lao', 'lv': 'Latvian', 'ln': 'Lingala', 'lt': 'Lithuanian', 'luo': 'Luo', 'lb': 'Luxembourgish', 'mk': 'Macedonian', 'ms': 'Malay', 'ml': 'Malayalam', 'mt': 'Maltese', 'mi': 'Maori', 'mr': 'Marathi', 'mn': 'Mongolian', 'ne': 'Nepali', 'nso': 'Northern-Sotho', 'nb': 'Norwegian', 'ny': 'Nyanja', 'oc': 'Occitan', 'or': 'Oriya', 'om': 'Oromo', 'ps': 'Pashto', 'fa': 'Persian', 'pl': 'Polish', 'pt': 'Portuguese', 'pa': 'Punjabi', 'ro': 'Romanian', 'ru': 'Russian', 'sr': 'Serbian', 'sn': 'Shona', 'sd': 'Sindhi', 'sk': 'Slovak', 'sl': 'Slovenian', 'so': 'Somali', 'ckb': 'Sorani-Kurdish', 'es': 'Spanish', 'sw': 'Swahili', 'sv': 'Swedish', 'tg': 'Tajik', 'ta': 'Tamil', 'te': 'Telugu', 'th': 'Thai', 'tr': 'Turkish', 'uk': 'Ukrainian', 'umb': 'Umbundu', 'ur': 'Urdu', 'uz': 'Uzbek', 'vi': 'Vietnamese', 'cy': 'Welsh', 'wo': 'Wolof', 'xh': 'Xhosa', 'yo': 'Yoruba', 'zu': 'Zulu'}

def run_subset(eval_info, model_info, subset_name: str):
    my_custom_logger.info(f'cur_subset_name: {subset_name}')
    data_set_path = eval_info['input_path']
    data_set_name = eval_info['dataset_name']
    model_id_basename = os.path.basename(model_info['model_id']).rstrip(os.sep)
    review_path = f"{eval_info['output_path']}/{model_id_basename}"
    limit = eval_info['limit']
    model_name = model_info['model_name']
    model_url = model_info['model_url']
    tsv_files = glob.glob(os.path.join(data_set_path, f'data/{subset_name}*/test.tsv'))
    column_names = ['id', 'file_path', 'text_raw', 'text_clean', 'text_tokenized', 'number', 'gender']
    all_dfs = []
    for f in tsv_files:
        temp_df = pd.read_csv(f, sep='\t', header=None, names=column_names, quoting=3)
        temp_df['base_path'] = os.path.dirname(f)
        all_dfs.append(temp_df)
    test_df = pd.concat(all_dfs, ignore_index=True)

    def fix_path(row):
        audio_file_path = os.path.join(row['base_path'], 'audio', 'test', row['file_path'])
        if not os.path.exists(audio_file_path):
            my_custom_logger.error(f'Warning: {audio_file_path} not found')
            raise FileNotFoundError(f'{audio_file_path} audio in test meta data file not found')
        return audio_file_path

    def chinese_tokenizer(text):
        return ' '.join(jieba.cut(text, cut_all=False))

    def calculate_chinese_wer(reference, hypothesis):
        ref_tokens = chinese_tokenizer(reference)
        hyp_tokens = chinese_tokenizer(hypothesis)
        return wer(ref_tokens, hyp_tokens)

    def new_wer(reference: str, hypothesis: str, lang: str='zh'):
        punctuation_all = punctuation + string.punctuation
        pattern = '[\\s\\u200b\\u200c\\u200d\\u200e\\u200f\\u202a-\\u202e\\u2060\\ufeff]+'
        for x in punctuation_all:
            if x == "'":
                continue
            reference = reference.replace(x, '')
            hypothesis = hypothesis.replace(x, '')
        reference = reference.replace('  ', ' ')
        hypothesis = hypothesis.replace('  ', ' ')
        if lang == 'zh':
            reference = re.sub(pattern, '', reference).strip()
            hypothesis = re.sub(pattern, '', hypothesis).strip()
            truth = ' '.join([x for x in reference])
            hypo = ' '.join([x for x in hypothesis])
        elif lang == 'en':
            truth = reference.lower()
            hypo = hypothesis.lower()
        else:
            raise NotImplementedError
        wer_res = wer(truth, hypo)
        return wer_res
    test_df['file_path'] = test_df.apply(fix_path, axis=1)
    eval_data = test_df.drop(columns=['base_path'])
    result_data = []
    eval_data['model_answer'] = ''
    if limit is None or limit == 0:
        limit = len(test_df)
    average_score = 0
    total_count = 0
    CHINESE_SUBSETS = {'cmn_hans', 'yue_hant'}
    for idx, item in eval_data.iterrows():
        if idx > limit - 1:
            break
        audio_file = item['file_path']
        base64_audio = encode_audio_base64_from_file(audio_file)
        target_lang = language_dict.get(subset_name, 'English')
        prompt = f'Transcribe the speech into {target_lang} text.'
        try:
            model_answer = request_audio(model_name, model_url, '', base64_audio, prompt)
        except Exception as e:
            my_custom_logger.error(f'model:{model_name} req err {e}')
            model_answer = ''
        eval_data.loc[idx, 'model_answer'] = model_answer
        if MLLM_CUSTOM_DATASETS_DEBUG_FLAG:
            my_custom_logger.info(f"gold_answer:{item['text_raw']}")
            my_custom_logger.info(f'model_answer:{model_answer}')
        if subset_name in CHINESE_SUBSETS:
            wer_score = new_wer(item['text_raw'], model_answer, 'zh')
        else:
            wer_score = new_wer(item['text_raw'], model_answer, 'en')
        my_custom_logger.info(f'question index: {idx}, wer: {wer_score}')
        score = wer_score
        result_data.append({'音频路径': audio_file, '问题': prompt, '标准答案': item['text_raw'], '模型答案': model_answer, 'WER': score})
        total_count += 1
        average_score += score
    average_score = round(average_score / total_count, 4)
    if subset_name in CHINESE_SUBSETS:
        real_score = calculate_chinese_wer(eval_data['text_raw'].tolist(), eval_data['model_answer'].tolist())
    else:
        real_score = wer(eval_data['text_raw'].tolist(), eval_data['model_answer'].tolist())
    my_custom_logger.info(f'取均值WER: {average_score}, 整体list计算WER: {real_score}')
    gen_review_excel(data_set_name, subset_name, result_data, review_path)
    gen_review_jsonl(result_data, review_path, data_set_name, subset_name, True)
    return (total_count, average_score)

def run_fleurs_eval(model_info, eval_info):
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
