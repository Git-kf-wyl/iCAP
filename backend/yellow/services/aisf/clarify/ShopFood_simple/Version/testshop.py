# Private iCAP Yellow business implementation. Do not publish.
import multiprocessing
import os
from datetime import datetime
import pandas as pd
dirs_name = './' + str(datetime.now().strftime('%Y-%m-%d_%H'))

def run_script(script_path):
    os.system(f'python3 {script_path}')

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
