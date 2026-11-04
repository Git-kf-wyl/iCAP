# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.service_release.utils import process_results_intent
from typing import List, Any
import os
import json
import re

@Benchmark.register(name='service_intent', pretty_name='SERVICE', dataset_id='service_intent', subset_list=['默认域', '听写待办', '查询天气', '行程规划', '餐厅推荐', '视觉理解'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class ServiceIntentAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        subset_list = kwargs['subset_list']
        for item in kwargs['subset_list']:
            res_dict[item] = []
        res_dict_temp = {}
        json_files = [f for f in os.listdir(input_file_path) if f.endswith('.json')]
        for json_file in json_files:
            file_path = os.path.join(input_file_path, json_file)
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                subset_file = json_file.split('_')[0]
                if subset_file == '听写待办':
                    res_dict['听写待办'].extend(data)
                elif subset_file == '查询天气':
                    res_dict['查询天气'].extend(data)
                elif subset_file == '行程规划':
                    res_dict['行程规划'].extend(data)
                elif subset_file == '餐厅推荐':
                    res_dict['餐厅推荐'].extend(data)
                elif subset_file == '视觉理解':
                    res_dict['视觉理解'].extend(data)
                elif subset_file == '其他':
                    res_dict['默认域'].extend(data)
                elif subset_file == '困难用例':
                    for input_d in data:
                        if input_d['messages'][2]['content'] == '0':
                            res_dict_temp['instruction'] = input_d['messages'][0]['content']
                            res_dict_temp['input'] = input_d['messages'][1]['content']
                            res_dict_temp['output'] = input_d['messages'][2]['content']
                            res_dict['默认域'].append(res_dict_temp)
                        elif input_d['messages'][2]['content'] == '1':
                            res_dict_temp['instruction'] = input_d['messages'][0]['content']
                            res_dict_temp['input'] = input_d['messages'][1]['content']
                            res_dict_temp['output'] = input_d['messages'][2]['content']
                            res_dict['听写待办'].append(res_dict_temp)
                        elif input_d['messages'][2]['content'] == '2':
                            res_dict_temp['instruction'] = input_d['messages'][0]['content']
                            res_dict_temp['input'] = input_d['messages'][1]['content']
                            res_dict_temp['output'] = input_d['messages'][2]['content']
                            res_dict['查询天气'].append(res_dict_temp)
                        elif input_d['messages'][2]['content'] == '3':
                            res_dict_temp['instruction'] = input_d['messages'][0]['content']
                            res_dict_temp['input'] = input_d['messages'][1]['content']
                            res_dict_temp['output'] = input_d['messages'][2]['content']
                            res_dict['行程规划'].append(res_dict_temp)
                        elif input_d['messages'][2]['content'] == '4':
                            res_dict_temp['instruction'] = input_d['messages'][0]['content']
                            res_dict_temp['input'] = input_d['messages'][1]['content']
                            res_dict_temp['output'] = input_d['messages'][2]['content']
                            res_dict['餐厅推荐'].append(res_dict_temp)
                        elif input_d['messages'][2]['content'] == '5':
                            res_dict_temp['instruction'] = input_d['messages'][0]['content']
                            res_dict_temp['input'] = input_d['messages'][1]['content']
                            res_dict_temp['output'] = input_d['messages'][2]['content']
                            res_dict['视觉理解'].append(res_dict_temp)
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = input_d['input']
        full_prompt = self.prompt_template.format(query=problem)
        system_prompt = input_d['instruction']
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['output']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        res = result.strip()
        match = re.search('\\d+', res)
        if match:
            pred = match.group()
        else:
            pred = res
        return pred

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        return process_results_intent(gold, pred, raw_input_d, subset_name)

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
