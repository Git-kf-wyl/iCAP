# Private iCAP Yellow business implementation. Do not publish.
import os
import threading
from services.aisf.perception_plan.constants import BASE_DIR, BASE_DIR_OUTPUT
from services.aisf.thread_util import run_script
from services.aisf.zip_util import zip_directory
test_model_name = 'Qwen3-32B'
test_model_url = 'http://127.0.0.1:1/unconfigured'

def run_all_scenes_pp(task_id, model_name: str, model_url: str):
    print(f'run_travel_Ident: {task_id}, {model_name}, {model_url}')
    python_files = [f for f in os.listdir(BASE_DIR) if f.endswith('Intent.py')]
    threads = []
    for file in python_files:
        thread = threading.Thread(target=run_script, args=(os.path.join(BASE_DIR, file), task_id, model_name, model_url))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    try:
        zip_directory(BASE_DIR_OUTPUT + task_id, BASE_DIR_OUTPUT + task_id + '/result.zip')
    except BaseException as e:
        print(f'合并表格或者压缩失败！{e}')
