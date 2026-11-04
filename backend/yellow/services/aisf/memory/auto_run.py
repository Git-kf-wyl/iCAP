# Private iCAP Yellow business implementation. Do not publish.
import os
import threading
from services.aisf.memory.constants import BASE_DIR, BASE_DIR_OUTPUT
from services.aisf.thread_util import run_script
from services.aisf.zip_util import zip_directory
test_model_name = 'Qwen3-32B'
test_model_url = 'http://127.0.0.1:1/unconfigured'

def run_all_scenes_mem(task_id, model_name: str, model_url: str, test_case: str):
    print(f'run_memory: {task_id}, {model_name}, {model_url}, {test_case}')
    is_open = test_case.endswith('open')
    is_8b = test_case.endswith('8b') or test_case.endswith('8b_open')
    model_32b_dir = ['memory_81/forever_memory_extract']
    model_8b_travel_agent_dir = ['memory_81/travel_extract_new/travel_time', 'memory_81/travel_extract_new/travel_hotel', 'oldMemoryCall/getCityName']
    model_32b_open_dir = ['memory10/relation_memory', 'memory_81/general_memory_extract']
    model_8b_open_dir = ['memory_81/extract2', 'memory_81/general_memory_determine', 'memory_81/general_memory_recall', 'memory_81/recall2']
    python_files = []
    if not is_open:
        if is_8b:
            if test_case == 'aisf_memory_travel_agent_8b':
                for cur_dir in model_8b_travel_agent_dir:
                    for file in os.listdir(os.path.join(BASE_DIR, cur_dir)):
                        if file.endswith('8B.py'):
                            python_files.append(os.path.join(cur_dir, file))
            elif test_case == 'aisf_memory_attribute_extract_8b':
                for file in os.listdir(os.path.join(BASE_DIR, 'memoryNew/extractAttribute')):
                    if file.endswith('8B.py'):
                        python_files.append(os.path.join('memoryNew/extractAttribute', file))
            elif test_case == 'aisf_memory_topic_8b':
                for file in os.listdir(os.path.join(BASE_DIR, 'memory_81/topic_memory_determine')):
                    if file.endswith('8B.py'):
                        python_files.append(os.path.join('memory_81/topic_memory_determine', file))
            elif test_case == 'aisf_memory_fact_8b':
                for file in os.listdir(os.path.join(BASE_DIR, 'factmemory0722')):
                    if file.endswith('8B.py'):
                        python_files.append(os.path.join('factmemory0722', file))
            elif test_case == 'aisf_memory_intent_classify_8b':
                for file in os.listdir(os.path.join(BASE_DIR, 'memory_81/determine_intent_classification')):
                    if file.endswith('8B.py'):
                        python_files.append(os.path.join('memory_81/determine_intent_classification', file))
        else:
            for cur_dir in model_32b_dir:
                for file in os.listdir(os.path.join(BASE_DIR, cur_dir)):
                    if file.endswith('32B.py'):
                        python_files.append(os.path.join(cur_dir, file))
    elif is_8b:
        for cur_dir in model_8b_open_dir:
            for file in os.listdir(os.path.join(BASE_DIR, cur_dir)):
                if file.endswith('8B.py'):
                    python_files.append(os.path.join(cur_dir, file))
    else:
        for cur_dir in model_32b_open_dir:
            for file in os.listdir(os.path.join(BASE_DIR, cur_dir)):
                if file.endswith('32B.py'):
                    python_files.append(os.path.join(cur_dir, file))
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
