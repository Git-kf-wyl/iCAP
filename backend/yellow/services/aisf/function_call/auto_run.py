# Private iCAP Yellow business implementation. Do not publish.
import os
import threading
from services.aisf.function_call.constants import BASE_DIR, BASE_DIR_OUTPUT
from services.aisf.thread_util import run_script
from services.aisf.zip_util import zip_directory
test_model_name = 'Qwen3-32B'
test_model_url = 'http://127.0.0.1:1/unconfigured'

def run_all_scenes_fc(task_id, model_name: str, model_url: str):
    print(f'run_function_call: {task_id}, {model_name}, {model_url}')
    thread = threading.Thread(target=run_script, args=(os.path.join(BASE_DIR, 'FunctionCall.py'), task_id, model_name, model_url))
    thread.start()
    thread.join()
    try:
        zip_directory(BASE_DIR_OUTPUT + task_id, BASE_DIR_OUTPUT + task_id + '/result.zip')
    except BaseException as e:
        print(f'合并表格或者压缩失败！{e}')
