# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_develop.utils import *
from eval.benchmarks.aisf_develop.prompt import SingleIntentIdentDevPrompt

@Benchmark.register(name='aisf_intent_dev', pretty_name='AISF', dataset_id='aisf_intent_dev', subset_list=['FoodieAgent', 'AnyShoppingAgent', 'LifeAssistantAgent', 'SystemAgent', 'APP提取'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFIntentDevAdapter(DataAdapter):

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
            data = read_from_excel_aisf_intent(file_path)
            for i in range(len(data)):
                if data[i]['任务类型'] == 'FoodieAgent':
                    res_dict['FoodieAgent'].append(data[i])
                elif data[i]['任务类型'] == 'AnyShoppingAgent':
                    res_dict['AnyShoppingAgent'].append(data[i])
                elif data[i]['任务类型'] == 'LifeAssistantAgent':
                    res_dict['LifeAssistantAgent'].append(data[i])
                elif data[i]['任务类型'] == 'SystemAgent':
                    res_dict['SystemAgent'].append(data[i])
                elif data[i]['任务类型'] == 'APP提取':
                    res_dict['APP提取'].append(data[i])
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
        full_prompt = self.prompt_template.format(query=problem) + '\n\n/no_think'
        if self.system_prompt:
            system_prompt = self.system_prompt
        else:
            system_prompt = SingleIntentIdentDevPrompt
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['任务类型']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        try:
            if not pred or pred.strip() == '':
                return 0
            pred_json = json.loads(pred)
            if not isinstance(pred_json, list) or len(pred_json) != 1:
                return 0
            answer_data = pred_json[0]
            current_task_type = raw_input_d['任务类型']
            if current_task_type == 'APP提取':
                app_value = raw_input_d['app']
                extracted_app = answer_data.get('APP', '')
                app_empty = not app_value or str(app_value).strip() == ''
                extracted_empty = extracted_app is None or str(extracted_app).strip() == ''
                if app_empty and extracted_empty:
                    return 1
                elif not app_empty and (not extracted_empty):
                    return 1 if str(app_value).strip() == str(extracted_app).strip() else 0
                else:
                    return 0
            agent_name = answer_data.get('agent_name')
            if agent_name is None:
                return 0
            return 1 if agent_name == current_task_type else 0
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            return 0
        return 0

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
