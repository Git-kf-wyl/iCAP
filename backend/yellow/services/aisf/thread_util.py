# Private iCAP Yellow business implementation. Do not publish.
import argparse
import os
import subprocess
from services.aisf.Constants import PROJECT_ROOT_PATH

def run_script(script_path, id, model_name, model_url):
    env = os.environ.copy()
    env['PYTHONPATH'] = PROJECT_ROOT_PATH
    subprocess.run(['python3', script_path, id, model_name, model_url], env=env)

def parse():
    parser = argparse.ArgumentParser(description='演示如何接收命令行参数')
    parser.add_argument('arg1', type=str, help='第一个参数')
    parser.add_argument('arg2', type=str, help='第二个参数')
    parser.add_argument('arg3', type=str, help='第三个参数')
    task_id = None
    model_name = None
    url = None
    try:
        args = parser.parse_args()
        print(f'args: {args.arg1}, {args.arg2}, {args.arg3}')
        task_id = args.arg1
        model_name = args.arg2
        url = args.arg3
    except BaseException as e:
        print(f'err: {e}')
    return (task_id, model_name, url)
