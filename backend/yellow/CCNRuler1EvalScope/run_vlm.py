# Private iCAP Yellow implementation. Do not publish.
import time
import nltk
import os
from datetime import datetime
from evalscope import TaskConfig, run_task
from evalscope.constants import EvalBackend
if __name__ == '__main__':
    print('start')
    public_conf = [{'api_url': 'http://127.0.0.1:1/unconfigured', 'api_key': '', 'model': 'Qwen3-VL-4B-Instruct', 'non_openai_format': False}]
    task_config = TaskConfig(models=public_conf, model=public_conf[0]['model'], eval_backend=EvalBackend.VLM_EVAL_KIT, eval_config={'data': ['WorldSense'], 'local_path': {'WorldSense': 'data/WorldSense'}, 'limit': 1, 'mode': 'all', 'model_name': 'Qwen2.5-Omni-7B', 'model': [{'api_base': 'http://127.0.0.1:1/unconfigured', 'key': 'EMPTY', 'name': 'CustomAPIModel', 'type': 'Qwen2.5-Omni-7B', 'video_llm': False, 'temperature': 0}], 'nproc': 1, 'reuse': False, 'verbose': True}, eval_type='checkpoint', datasets=[], dataset_args={}, eval_batch_size=1, generation_config={'max_tokens': 4096, 'temperature': 0.6, 'top_p': 0.95, 'top_k': 40, 'request_nums': 1}, limit=1, task_id='123', request_retry=False, retry_content_none=False, judge_worker_num=1, judge_model_args=[{'model_id': 'Qwen3-32B', 'api_url': 'http://127.0.0.1:1/unconfigured', 'api_key': '', 'generation_config': {'temperature': 0.01, 'request_nums': 1, 'enable_thinking': False}, 'system_prompt': '我给你一个问题和对这个问题的回答，你给我这个回答的结果，只用回答正确或错误', 'prompt_template': '我的问题是{question}，给出的回答是{pred}'}])
    start_time = time.time()
    run_task(task_config)
    end_time = time.time()
    duration = end_time - start_time
    print(duration)
