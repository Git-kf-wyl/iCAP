# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.aisf_develop.utils import box_process_results
from typing import List, Any
import os
import json
import pandas as pd
import base64
from PIL import Image
import csv

@Benchmark.register(name='aisf_box', pretty_name='SERVICE', dataset_id='aisf_box', subset_list=['default'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFBoxAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        excel_files = [f for f in os.listdir(input_file_path) if f.endswith(('.xlsx', '.xls'))]
        for excel_file in excel_files:
            file_path = os.path.join(input_file_path, excel_file)
            content = []
            df = pd.read_excel(file_path, sheet_name=0)
            for index, row in df.iterrows():
                content.append({'query': row['query'], 'system_prompt': row['system_prompt'], 'user_prompt': row['user_prompt'], 'answer': row['answer'], 'field': row['field'], 'category': row['category']})
        res_dict['default'] = content
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = str(input_d['user_prompt'])
        full_prompt = self.prompt_template.format(query=problem)
        problem = str(input_d['system_prompt'])
        system_prompt = self.prompt_template.format(query=problem)
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        gold_answer = input_d['answer']
        return gold_answer

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, answer: str, pred: str, raw_input_d: str, subset_name) -> float:
        field = raw_input_d['field']
        pred = pred.lstrip('\n')
        res = box_process_results(answer, pred, field)
        return res

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        res_dict = super().compute_dict_metric(review_res_list, **kwargs)
        return super().compute_metric(res_dict, **kwargs)
