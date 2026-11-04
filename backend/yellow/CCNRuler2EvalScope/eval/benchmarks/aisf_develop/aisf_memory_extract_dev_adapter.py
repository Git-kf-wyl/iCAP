# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_develop.utils import read_multicolums_from_excel
from eval.benchmarks.aisf_develop.prompt import THEME_integrated_PROMPT

@Benchmark.register(name='aisf_memory_extract_dev', pretty_name='AISF', dataset_id='aisf_memory_extract_dev', subset_list=['default'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFMemoryExtractdevAdapter(DataAdapter):

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
            if 'testofextract' in excel_file:
                res_dict['default'] = read_multicolums_from_excel(file_path, 0, [1, 3])
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        full_prompt = '##当前输入\n' + str(input_d) + '/no_think'
        if self.system_prompt:
            system_prompt = self.system_prompt
        else:
            system_prompt = THEME_integrated_PROMPT
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        if 'column3' in input_d:
            return input_d['column3']
        else:
            return None

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        pred = pred.replace('\n', '')
        pred = pred.replace('`', '')
        pred = pred.replace('json', '')
        if gold is not None and pred is not None:
            if gold.replace(' ', '') == pred.replace(' ', ''):
                return True
            else:
                return False
        else:
            return False

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
