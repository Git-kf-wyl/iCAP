# Private iCAP Yellow implementation. Do not publish.
import re
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_develop.utils import read_multicolums_from_excel, read_from_excel_aisf_toolcall, eval_toolcall
from eval.benchmarks.aisf_develop.prompt import FC_PROMPT
from datetime import datetime
today = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
now = datetime.now()
week_day = now.weekday()
week_day_cn = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

@Benchmark.register(name='aisf_function_call_dev', pretty_name='AISF', dataset_id='aisf_function_call_dev', subset_list=['default'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFFunctionCalldevAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        subset_list = kwargs['subset_list']
        for item in kwargs['subset_list']:
            res_dict[item] = []
        excel_files = [f for f in os.listdir(input_file_path) if f.endswith(('.xlsx', '.xls'))]
        for excel_file in excel_files:
            file_path = os.path.join(input_file_path, excel_file)
            res_dict['default'] = read_from_excel_aisf_toolcall(file_path)
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = str(input_d['query']) + '/nothink'
        full_prompt = self.prompt_template.format(query=problem)
        if self.system_prompt:
            prompt = self.system_prompt
        else:
            prompt = FC_PROMPT
        system_prompt = prompt.replace('{{0}}', today + week_day_cn[week_day])
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        if input_d['field'] == 'CHAT':
            return 'CHAT'
        return input_d['answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        result_no_tool = re.sub('<tool>.*?</tool>', '', result, flags=re.DOTALL)
        return result_no_tool

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        if gold is not None and gold == 'CHAT':
            return True
        if gold is not None and pred is not None:
            result = eval_toolcall(pred, gold)
            return True if result == 1 else False
        else:
            return False

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
