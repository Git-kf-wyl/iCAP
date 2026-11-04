# Private iCAP Yellow implementation. Do not publish.
import os
import random
from eval.config import TaskConfig
from eval.constants import JudgeStrategy
from eval.run import run_task
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:1/unconfigured'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:1/unconfigured'
public_conf = [{'api_url': 'http://127.0.0.1:1/unconfigured', 'api_key': '', 'model': 'qwen3_32b', 'non_openai_format': True}]
task_config = TaskConfig(models=public_conf, model='717/Qwen3-32B', eval_type='service', datasets=['aisf_intent_dev'], dataset_args={'box_tool_use': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AverageAccuracy'], 'few_shot_num': 0, 'input_path': 'data/box_tool_use'}, 'service_intent': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AverageAccuracy'], 'few_shot_num': 0, 'input_path': 'data/意图识别'}, 'service_tool_select': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AverageAccuracy'], 'few_shot_num': 0, 'input_path': 'data/20250626工具待办数据集'}, 'service_parameter_extract': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AverageAccuracy'], 'few_shot_num': 0, 'input_path': 'data/20250626工具待办数据集'}, 'service_style': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AverageAccuracy'], 'few_shot_num': 0, 'input_path': 'data/风格聊天'}, 'service_emotion': {'filters': {'remove_until': '</think>'}, 'metric_list': ['AverageAccuracy'], 'few_shot_num': 0, 'input_path': 'data/情感聊天'}, 'aisf_intent_dev': {'dataset_name': 'aisf_intent_dev', 'input_path': 'data/aisf_intent_dev', 'few_shot_num': 0, 'few_shot_file_path': [], 'default_subsets': [], 'testcase_tags': [], 'metric_list': ['AverageAccuracy'], 'status': 1, 'system_prompt': '你好'}}, limit=1, eval_batch_size=4, generation_config={'temperature': 0.01, 'top_p': 0.95, 'top_k': 40, 'request_nums': 1}, judge_strategy=JudgeStrategy.AUTO, judge_model_args={'model_id': '/cache/Qwen2.5-72B-Instruct', 'api_url': 'http://127.0.0.1:1/unconfigured', 'api_key': '', 'generation_config': {'max_tokens': 4096, 'temperature': 0.01, 'request_nums': 1, 'enable_thinking': False}}, task_id='test_0729')
res = run_task(task_config)
print(res)
