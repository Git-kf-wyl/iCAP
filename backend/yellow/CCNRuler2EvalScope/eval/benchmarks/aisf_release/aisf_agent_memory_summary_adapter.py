# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_release.utils import read_from_excel_agent_memory_summary, get_model_content_agent_memory_summary, is_successful_agent_memory_summary
from eval.benchmarks.aisf_release.prompt import AGENT_MRMORY_PROMPT
import logging

@Benchmark.register(name='aisf_agent_memory_summary', pretty_name='AISF', dataset_id='aisf_agent_memory_summary', subset_list=['美食', '购物'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFAgentMemorySummaryAdapter(DataAdapter):

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
            data = read_from_excel_agent_memory_summary(file_path)
            if 'food' in excel_file:
                res_dict['美食'] = data
            elif 'shop' in excel_file:
                res_dict['购物'] = data
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        input_d['Input'] = input_d['Input'].replace("'", '"')
        full_prompt = get_model_content_agent_memory_summary(input_d['Input'], input_d['subtopic']) + '/nothink'
        system_prompt = AGENT_MRMORY_PROMPT
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return str(input_d['test_answer'])

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        isSatisfied = is_successful_agent_memory_summary(pred, gold)
        if isSatisfied['满意度'] == '非常满意':
            return True
        else:
            return False

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
