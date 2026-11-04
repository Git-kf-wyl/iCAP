# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_release.utils import read_from_excel_general_memory_determine
from eval.benchmarks.aisf_release.prompt import MEMORY_DETERMINE_PROMPT
import logging

@Benchmark.register(name='aisf_general_memory_determine', pretty_name='AISF', dataset_id='aisf_general_memory_determine', subset_list=['default'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFGeneralMemoryDetermineAdapter(DataAdapter):

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
            data = read_from_excel_general_memory_determine(file_path)
            res_dict['default'] = data
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        input_d['hist'] = input_d['hist'].replace("'", '"')
        full_prompt = f"\n### 用户输入\n{input_d['UserInput']}\n### 用户历史信息\n{input_d['hist']}"
        system_prompt = MEMORY_DETERMINE_PROMPT
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return None

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        return True

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
