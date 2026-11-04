# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_release.utils import read_from_excel
from eval.benchmarks.aisf_release.utils import parse_think_response_clean
from eval.benchmarks.aisf_release.prompt import SingleIntentIdentPrompt
from eval.benchmarks.aisf_release.utils import get_json_structure

@Benchmark.register(name='aisf_intent', pretty_name='AISF', dataset_id='aisf_intent', subset_list=['出行', '工具调用', '购物', '美食'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFIntentAdapter(DataAdapter):

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
            data = read_from_excel(file_path)
            if '出行' in excel_file:
                res_dict['出行'] = data
            elif '工具调用' in excel_file:
                res_dict['工具调用'] = data
            elif '购物' in excel_file:
                res_dict['购物'] = data
            elif '美食' in excel_file:
                res_dict['美食'] = data
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = str(input_d['Input'])
        full_prompt = self.prompt_template.format(query=problem)
        system_prompt = SingleIntentIdentPrompt
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['Test answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        pred = get_json_structure(result)
        return pred

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        try:
            if isinstance(pred, list):
                if pred[0]['agent_name'] == gold:
                    return True
                else:
                    return False
            elif isinstance(pred, dict):
                if pred['agent_name'] == gold:
                    return True
                else:
                    return False
        except Exception as e:
            print(f'发生了一个错误：{e}')
            print(pred)
            return False

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
