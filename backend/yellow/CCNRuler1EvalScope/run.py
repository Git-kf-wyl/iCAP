# Private iCAP Yellow implementation. Do not publish.
import time
import nltk
import os
from datetime import datetime
from evalscope import TaskConfig, run_task
from evalscope.constants import EvalBackend
nltk.download('punkt_tab')
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
if __name__ == '__main__':
    public_conf = [{'api_url': 'http://127.0.0.1:1/unconfigured', 'api_key': '', 'model': 'Qwen3-32B', 'non_openai_format': True}]
    task_config = TaskConfig(models=public_conf, model='717/Qwen3-32B', eval_type='service', datasets=['ifeval'], dataset_args={'aime24': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AveragePass@1'], 'few_shot_num': 0}, 'math_500': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AveragePass@1'], 'few_shot_num': 0}, 'gpqa': {'subset_list': ['gpqa_diamond'], 'filters': {'remove_until': '</think>'}, 'metric_list': ['AveragePass@1'], 'few_shot_num': 0}, 'mmlu_redux': {'local_path': 'D:\\code_ailab\\CCNRulerEvalScope\\CCNModelEvalService\\testsuite\\TestSuite\\mmlu_redux', 'subset_list': ['abstract_algebra'], 'filters': {'remove_until': '</think>'}, 'metric_list': ['AverageAccuracy'], 'few_shot_num': 0}, 'live_code_bench': {'subset_list': ['v6'], 'filters': {'remove_until': '</think>'}, 'metric_list': ['AveragePass@1'], 'few_shot_num': 0}, 'humaneval': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AveragePass@1'], 'few_shot_num': 0}, 'ifeval': {'filters': {'remove_until': '</think>'}, 'metric_list': ['prompt_level_strict_acc'], 'few_shot_num': 0}, 'bfcl_v3': {'subset_list': ['simple'], 'filters': {'remove_until': '</think>'}, 'extra_params': {'underscore_to_dot': False, 'is_fc_model': False}}, 'hle': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AveragePass@1'], 'few_shot_num': 0}}, eval_batch_size=2, generation_config={'max_tokens': 4096, 'temperature': 0.6, 'top_p': 0.95, 'top_k': 40, 'request_nums': 1}, limit=1, request_retry=False, retry_content_none=False, judge_worker_num=1, task_id='24bdaaf4-489c-4141-aab2-6e0a3030841d')
    start_time = time.time()
    task_configs = [{'models': [{'api_url': 'http://127.0.0.1:1/unconfigured', 'api_key': '', 'model': 'gemma-4-31b-it', 'non_openai_format': False}], 'model': 'Qwen3.6-27B', 'stream': False, 'eval_type': 'service', 'datasets': ['mmlu_redux'], 'dataset_args': {'mmlu_redux': {'few_shot_num': 0, 'metric_list': ['AverageAccuracy'], 'local_path': 'D:\\code_ailab\\CCNRulerEvalScope\\CCNModelEvalService\\testsuite\\TestSuite\\mmlu_redux', 'testcase_tags': ['知识百科'], 'system_prompt': ''}}, 'eval_batch_size': 4, 'generation_config': {'max_tokens': 14000, 'top_p': 1, 'top_k': 40, 'temperature': 0.7, 'request_nums': 1, 'chat_template_kwargs': {'enable_thinking': False}}, 'limit': 1, 'request_retry': False, 'retry_content_none': False, 'judge_worker_num': 1, 'task_id': '20260723_161644_0001', 'use_cache': None, 'seed': None, 'judge_strategy': 'auto', 'judge_model_args': [{'model_id': 'Qwen3.6-27B', 'api_url': 'http://127.0.0.1:1/unconfigured', 'api_key': '', 'generation_config': {'max_tokens': 4096, 'temperature': 0.01, 'request_nums': 1, 'enable_thinking': False, 'chat_template_kwargs': {'enable_thinking': False}}}]}]
    res = run_task(task_configs)
    end_time = time.time()
    duration = end_time - start_time
    print(duration)
