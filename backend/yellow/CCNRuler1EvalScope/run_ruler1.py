# Private iCAP Yellow implementation. Do not publish.
import time
import os
import sys
import json
import platform
from evalscope import TaskConfig, run_task
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
if platform.system() != 'Windows':
    sys.stdout = open('/dev/null', 'w')
    sys.stderr = open('/dev/null', 'w')
if __name__ == '__main__':
    if platform.system() == 'Windows' and len(sys.argv) > 2 and (sys.argv[1] == '--config'):
        config_file = sys.argv[2]
        with open(config_file, 'r', encoding='utf-8') as f:
            input_json = f.read()
    else:
        input_json = sys.stdin.read()
    print('input: ', input_json)
    task_config = json.loads(input_json)
    print('task_config: ', input_json)
    run_task(task_config)
