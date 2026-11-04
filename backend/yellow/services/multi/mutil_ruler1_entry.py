# Private iCAP Yellow business implementation. Do not publish.
import os.path
from services.multi.utils.eval_utils import *
DATASET_SCRIPT_MAPPING = {'MMAR': MLLM_ROOT_PATH + '/mmar_mmau', 'MMAU': MLLM_ROOT_PATH + '/mmar_mmau', 'Fleurs': MLLM_ROOT_PATH + '/fleurs', 'librispeech_asr': MLLM_ROOT_PATH + '/librispeech_asr', 'MELD': MLLM_ROOT_PATH + '/meld', 'DailyOmni': MLLM_ROOT_PATH + '/daily_omni'}

def evaluate_model(dataset, cur_model_info, eval_info):
    script_path = DATASET_SCRIPT_MAPPING.get(dataset, None)
    if script_path is None:
        print(f'dataset is not supported, {dataset}.')
        return
    python_files = [f for f in os.listdir(script_path) if f.endswith('.py') and f.startswith('run')]
    if len(python_files) < 1:
        print(f'dataset script not exist, {dataset}, {script_path}.')
        return
    print(f'pyfile: {python_files}')
    run_mllm_script(os.path.join(script_path, python_files[0]), cur_model_info, eval_info)
