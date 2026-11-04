# Private iCAP Yellow implementation. Do not publish.
import glob
import json
import os.path
import sys
import chardet
import jsonlines as jsonl
from evalscope.constants import AnswerKeys, ReviewKeys
from typing import List, Union
from evalscope.metrics.named_metrics import metric_registry
from evalscope.report.generator import ReportGenerator
from evalscope.utils.io_utils import dump_jsonl_data
evalscope_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'CCNRuler1EvalScope'))
if evalscope_dir not in sys.path:
    sys.path.insert(0, evalscope_dir)

def compute_metrics(reviews_list: List[dict], metric_list, **kwargs) -> List[dict]:
    choices_lengths = [len(review_d[AnswerKeys.CHOICES]) for review_d in reviews_list if review_d.get(ReviewKeys.REVIEWED)]
    if choices_lengths:
        max_choices = max(choices_lengths)
    else:
        max_choices = 0
    review_res_list = []
    metric_score = []
    for review_d in reviews_list:
        if not review_d[ReviewKeys.REVIEWED]:
            continue
        if len(review_d[AnswerKeys.CHOICES]) == 0:
            continue
        elif len(review_d[AnswerKeys.CHOICES]) == 1 and max_choices == 1:
            review_res = review_d[AnswerKeys.CHOICES][0][ReviewKeys.REVIEW][ReviewKeys.RESULT]
        else:
            review_res = [choice[ReviewKeys.REVIEW][ReviewKeys.RESULT] for choice in review_d[AnswerKeys.CHOICES]]
        review_res_list.append(review_res)
    metric_score: List[dict] = compute_metric(metric_list=metric_list, review_res_list=review_res_list, reviews_list=reviews_list, time_difference=kwargs.get('time_difference'))
    return metric_score

def compute_metric(metric_list: Union[list], review_res_list: Union[dict, list], **kwargs) -> List[dict]:
    if len(metric_list) == 0:
        raise ValueError('No metric list found for the benchmark.')
    res_list = []
    for metric_str in metric_list:
        metric = metric_registry.get(metric_str)
        metric_name = metric.name
        metric_func = metric.object
        if isinstance(review_res_list, dict):
            review_res = review_res_list.get(metric_name, [])
        else:
            review_res = review_res_list
        res_list.append({'metric_name': metric_name, 'score': metric_func(review_res), 'num': len(review_res), 'time': 0})
    return res_list

def dump_report(metric_list, reviews_score_all, model_name, dataset):
    report_map = ReportGenerator.gen_report(reviews_score_all, f'{model_name}_{dataset}', metric_list=metric_list)
    return report_map

def re_score(old_score, new_score):
    if old_score['score'] != new_score['score']:
        old_score['score'] = new_score['score']
    for old_metric, new_metric in zip(old_score['metrics'], new_score['metrics']):
        if old_metric['score'] != new_metric['score'] or old_metric['macro_score'] != new_metric['macro_score']:
            old_metric['score'] = new_metric['score']
            old_metric['macro_score'] = new_metric['macro_score']
        for old_category, new_category in zip(old_metric['categories'], new_metric['categories']):
            if old_category['score'] != new_category['score'] or old_category['macro_score'] != new_category['macro_score']:
                old_category['score'] = new_category['score']
                old_category['macro_score'] = new_category['macro_score']
            for old_subset, new_subset in zip(old_category['subsets'], new_category['subsets']):
                if old_subset['score'] != new_subset['score']:
                    old_subset['score'] = new_subset['score']

def buffer_score(review_file, id, index, result):
    new_review_file = review_file + '_calculate'
    new_res_list = []
    res_list = []
    is_re_review = False
    if os.path.exists(new_review_file):
        with jsonl.open(new_review_file, mode='r') as reader:
            for line in reader.iter(type=dict, allow_none=True, skip_invalid=False):
                new_res_list.append(line)
                if line['answer_id'] == id:
                    is_re_review = True
    if is_re_review:
        for line in new_res_list:
            if line['answer_id'] == id:
                for choice in line['choices']:
                    if choice['index'] == index:
                        choice['review']['result'] = result
                        break
        dump_jsonl_data(new_res_list, new_review_file)
    else:
        with jsonl.open(review_file, mode='r') as reader:
            for line in reader.iter(type=dict, allow_none=True, skip_invalid=False):
                if line['answer_id'] == id:
                    for choice in line['choices']:
                        if choice['index'] == index:
                            choice['review']['result'] = result
                            res_list.append(line)
                            break
        if len(res_list) > 0:
            dump_jsonl_data(res_list, new_review_file, 'append')
        else:
            raise ValueError('No answer_id found in the review file.')

def merge_score(review_file, new_review_file):
    res_list = []
    id_to_line = {}
    with jsonl.open(new_review_file, mode='r') as reader1:
        for line1 in reader1.iter(type=dict, allow_none=True, skip_invalid=False):
            id_to_line[line1['answer_id']] = line1
    with jsonl.open(review_file, mode='r') as reader2:
        for line2 in reader2.iter(type=dict, allow_none=True, skip_invalid=False):
            answer_id = line2['answer_id']
            if answer_id in id_to_line:
                res_list.append(id_to_line[answer_id])
            else:
                res_list.append(line2)
    return res_list

def get_encoding(file_path):
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read(10000))
    encoding = result['encoding']
    return encoding

def flesh_score(review_file, dataset, sub_dataset, report_file, all_file, metric_list, model_name):
    new_review_file = review_file + '_calculate'
    if not os.path.exists(new_review_file):
        raise ValueError('没有分数需要更新.')
    reviews_score_all = {}
    encoding = get_encoding(report_file)
    with open(report_file, 'r', encoding=encoding) as f:
        report = json.load(f)
    for file in all_file:
        if os.path.basename(file) != os.path.basename(review_file):
            res_list = []
            sub = os.path.basename(file).split('.')[0].split(dataset)[1].strip('_')
            with jsonl.open(file, mode='r') as reader:
                for line in reader.iter(type=dict, allow_none=True, skip_invalid=False):
                    res_list.append(line)
            score = compute_metrics(res_list, metric_list)
            reviews_score_all.update({sub: score})
    res_list = merge_score(review_file, new_review_file)
    score = compute_metrics(res_list, metric_list)
    reviews_score_all.update({sub_dataset: score})
    report_di = dump_report(metric_list, reviews_score_all, model_name, dataset)
    re_score(report, report_di.to_dict())
    with open(report_file, 'w', encoding=encoding) as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=4))
    dump_jsonl_data(res_list, review_file)
    os.remove(new_review_file)

def format_result(result):
    if isinstance(result, str):
        if 'true' in result.lower():
            return True
        else:
            return False
    elif isinstance(result, int):
        if result == 1:
            return 1
        else:
            return 0
    elif isinstance(result, bool):
        return result
    else:
        raise ValueError('result is not in the correct format.')

def update_score(output_name, model_id_basename, dataset, sub_dataset, answer_id, index, result, **kwargs):
    review_file = f'{output_name}/reviews/{model_id_basename}/{dataset}_{sub_dataset}.jsonl'
    try:
        result = format_result(result)
        buffer_score(review_file, answer_id, index, result)
    except Exception as e:
        raise ValueError(f'分数修改失败: {e}')

def async_score(output_name, model_id_basename, dataset, sub_dataset, metric_list, model_name, **kwargs):
    review_file = f'{output_name}/reviews/{model_id_basename}/{dataset}_{sub_dataset}.jsonl'
    report_file = f'{output_name}/reports/{model_id_basename}/{dataset}.json'
    all_file = glob.glob(f'{output_name}/reviews/{model_id_basename}/{dataset}*.jsonl')
    try:
        flesh_score(review_file, dataset, sub_dataset, report_file, all_file, metric_list, model_name)
    except Exception as e:
        raise ValueError(f'刷新分数失败： {e}')
if __name__ == '__main__':
    input_json = sys.stdin.read()
    config = json.loads(input_json)
    use_cache = config.get('use_cache', '')
    model_id_basename = config.get('model_id_basename', '')
    dataset = config.get('dataset', '')
    sub_dataset = config.get('sub_dataset', '')
    if config['type'] == 'update':
        answer_id = config.get('answer_id', '')
        index = config.get('index', None)
        result = config.get('result', None)
        update_score(use_cache, model_id_basename, dataset, sub_dataset, answer_id, index, result)
    elif config['type'] == 'async':
        metric_list = config.get('metric_list', [])
        model_name = config.get('model_name', [])
        async_score(use_cache, model_id_basename, dataset, sub_dataset, metric_list, model_name)
