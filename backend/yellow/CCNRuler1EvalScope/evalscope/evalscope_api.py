# Private iCAP Yellow implementation. Do not publish.
import time
import nltk
from evalscope import TaskConfig, run_task

def main():
    task_config = TaskConfig(api_url='https://api.deepseek.com', api_key='', model='deepseek-reasoner', eval_type='service', datasets=['gpqa'], dataset_args={'gpqa': {'subset_list': ['gpqa_diamond'], 'filters': {'remove_until': '</think>'}, 'metrics_list': 'AveragePass@1', 'few_shot_num': 0}}, limit=1, generation_config={'max_tokens': 8192, 'temperature': 0.6, 'top_p': 0.95, 'top_k': 40, 'request_nums': 2}, stream=True)
    start_time = time.time()
    run_task(task_config)
    end_time = time.time()
    duration = end_time - start_time
    print(duration)
if __name__ == '__main__':
    main()
