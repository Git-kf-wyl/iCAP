# Private iCAP Yellow business implementation. Do not publish.
import multiprocessing
import os
import subprocess
import threading
from datetime import datetime
import pandas as pd
from services.aisf.Constants import PROJECT_ROOT_PATH
from services.aisf.clarify.Hotel.Version.constants import BASE_DIR, CURRENT_DIR
from services.aisf.thread_util import run_script
from services.aisf.clarify.constants import CLARIFY_BASE_DIR_OUTPUT

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename)
    for index, row in df.iterrows():
        success_count = row['Success_Count']
        sum_count = row['Sum_Count']
        test_cases.append({'Success_Count': success_count, 'Sum_Count': sum_count})
    return test_cases

def save_success_rate(file_path, success_rate):
    df1 = pd.DataFrame(success_rate)
    with pd.ExcelWriter(file_path) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)

def run_hotel(id, model_name, model_url):
    dirs_name = CLARIFY_BASE_DIR_OUTPUT + id + CURRENT_DIR
    python_files = [f for f in os.listdir(BASE_DIR) if f.endswith('.py') and f.startswith('para_ex')]
    threads = []
    for file in python_files:
        thread = threading.Thread(target=run_script, args=(os.path.join(BASE_DIR, file), id, model_name, model_url))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    nums = 0
    sum_rate = 0
    for file in os.listdir(dirs_name):
        if file.endswith(('.xlsx', '.xls')):
            file_path = os.path.join(dirs_name, file)
            inputData = read_from_excel(file_path)
            temp_success_count = 0
            temp_sum_count = 0
            for data in inputData:
                temp_success_count += data.get('Success_Count')
                temp_sum_count += data.get('Sum_Count')
            sum_rate += temp_success_count / temp_sum_count
            nums += 1
    successRate = sum_rate / nums
    save_success_rate(str(dirs_name + '/Summary' + '.xlsx'), {'scene': ['Hotel'], 'Success_Rate': [successRate], 'Sum_Count': [nums]})
