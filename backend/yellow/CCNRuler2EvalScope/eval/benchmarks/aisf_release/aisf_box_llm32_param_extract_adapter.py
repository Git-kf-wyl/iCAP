# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_release.utils import read_from_excel_box_scene_classify, compare_dicts_aisf_box_llm32
from eval.benchmarks.aisf_release.prompt import AisfBoxLlm32CommonPrompt, AisfBoxLlm32AvcallPrompt, AisfBoxLlm32FitnessPrompt
import logging

@Benchmark.register(name='aisf_box_llm32_param_extract', pretty_name='AISF', dataset_id='aisf_box_llm32_param_extract', subset_list=['公共场景', '亲情通话', '健身'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFBoxLlm32ParamAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        subset_list = kwargs['subset_list']
        for item in kwargs['subset_list']:
            res_dict[item] = []
        excel_files = [f for f in os.listdir(input_file_path) if f.endswith(('.xlsx', '.xls')) and f != 'intent_params.xlsx']
        for excel_file in excel_files:
            file_path = os.path.join(input_file_path, excel_file)
            data = read_from_excel_box_scene_classify(file_path)
            if 'public' in excel_file:
                res_dict['公共场景'] = data
            elif 'AVCALL' in excel_file:
                res_dict['亲情通话'] = data
            elif 'fitness' in excel_file:
                res_dict['健身'] = data
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, subset_name: str, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = str(input_d['input'])
        full_prompt = self.prompt_template.format(query=problem) + '\n\n/nothink'
        if subset_name in ['公共场景']:
            system_prompt = AisfBoxLlm32CommonPrompt
        elif subset_name in ['亲情通话']:
            system_prompt = AisfBoxLlm32AvcallPrompt
        elif subset_name in ['健身']:
            system_prompt = AisfBoxLlm32FitnessPrompt
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['param_answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        result = False
        function_answer = json.loads(pred)['function']
        params_llm_answer = json.loads(pred)['arguments']
        if function_answer == raw_input_d['intent_answer']:
            result = compare_dicts_aisf_box_llm32(gold, params_llm_answer)
        else:
            result = False
        return result

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
