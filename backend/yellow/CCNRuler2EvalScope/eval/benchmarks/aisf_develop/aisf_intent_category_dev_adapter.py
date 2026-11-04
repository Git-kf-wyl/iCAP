# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_develop.utils import read_from_excel_aisf_intent_category
from eval.benchmarks.aisf_develop.prompt import TRAVEL_INTENT_PROMPT
import logging

@Benchmark.register(name='aisf_intent_category_dev', pretty_name='AISF', dataset_id='aisf_intent_category_dev', subset_list=['行程预定', '订机票', '订酒店', '打车'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFIntentCategoryDevAdapter(DataAdapter):

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
            data = read_from_excel_aisf_intent_category(file_path)
            for i in range(len(data)):
                if '行程预定' in data[i]['任务类型']:
                    res_dict['行程预定'].append(data[i])
                elif '订机票' in data[i]['任务类型']:
                    res_dict['订机票'].append(data[i])
                elif '订酒店' in data[i]['任务类型']:
                    res_dict['订酒店'].append(data[i])
                elif '打车' in data[i]['任务类型']:
                    res_dict['打车'].append(data[i])
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = str(input_d['query'])
        full_prompt = self.prompt_template.format(query=problem) + '\n\n/nothink'
        if self.system_prompt:
            system_prompt = self.system_prompt
        else:
            system_prompt = TRAVEL_INTENT_PROMPT
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['correct answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        try:
            correct_answer_str = str(gold).strip()
            llm_answer_str = str(pred).strip()
            if correct_answer_str == llm_answer_str:
                return True
            else:
                return False
        except Exception as e:
            print(f'Error: {e}')
            return False

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
