# Private iCAP Yellow implementation. Do not publish.
import csv
from datetime import datetime
from typing import List, Any
import json
import os
from pathlib import Path
import re
import pandas as pd
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.aisf_release.utils import read_from_excel_food_1, read_from_excel_food_2, read_from_excel_food_3, read_from_excel_food_4, read_from_excel_food_5, check_hist_pre, check_add_more_clarify
from typing import Any, Optional
from eval.benchmarks.aisf_release.prompt import ShopPrompt
from eval.metrics.llm_judge import LLMJudge
from eval.benchmarks.aisf_release.judge_step_sys_prompt import Food_Replay_Agent_Para_Check, Food_Reply_Agent2_No_Use_His_Preference, Food_Reply_Agent3_Use_His_Preference, Food_Reply_Agent4_More, Food_Replay_Agent_More_Food_Name
from eval.benchmarks.aisf_release.judge_step_sys_prompt_2 import Product_Check_Agent_Food

@Benchmark.register(name='aisf_clarify_shop', pretty_name='AISF Clarify Test', dataset_id='aisf_clarify_shop', subset_list=['参数校验', '不使用历史偏好', '使用历史偏好', '追加', '追问商品名称'], metric_list=['AverageAccuracy'], model_adapter='aisf_clarify_shopfood_server', few_shot_num=0, system_prompt=None, prompt_template='{query}', extra_params={'need_step_judge': True})
class AISFClarifyShopDataAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        extra_params = kwargs.get('extra_params', {})
        self.need_step_judge = extra_params.get('need_step_judge', False)
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        excel_files = [f for f in os.listdir(input_file_path) if f.endswith(('.xlsx', '.xls'))]
        for excel_file in excel_files:
            file_path = os.path.join(input_file_path, excel_file)
            if 'shop_para_check' in excel_file:
                res_dict['参数校验'] = read_from_excel_food_1(file_path)
            elif 'shop_not_dependhis' in excel_file:
                res_dict['不使用历史偏好'] = read_from_excel_food_2(file_path)
            elif 'shop_dependhis' in excel_file:
                res_dict['使用历史偏好'] = read_from_excel_food_3(file_path)
            elif 'shop_clarifymore' in excel_file:
                res_dict['追加'] = read_from_excel_food_4(file_path)
            elif 'shop_no_store' in excel_file:
                res_dict['追问商品名称'] = read_from_excel_food_5(file_path)
        return res_dict
    '\n    input_d = res_dict[subset_name]\n    '

    def gen_prompt(self, input_d: dict, subset_name: str, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        input_d['turns'] = []
        input_d['need_step_judge'] = True if self.need_step_judge else False
        input_d['step_system_prompt'] = ''
        input_d['step_system_prompt_2'] = ''
        input_d['no_need_judge'] = False
        d = datetime.now()
        messages = []
        messages.append({'role': 'system', 'content': ShopPrompt})
        input = ''
        if subset_name in ['参数校验']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input_d['step_system_prompt'] = Food_Replay_Agent_Para_Check.replace('{0}', str(input_d['Input']))
            input_d['no_need_judge'] = True
        elif subset_name in ['不使用历史偏好']:
            input += f"## 历史偏好\n{input_d.get('hist_Pre', '{}')}\n\n"
            system_prompt = Food_Reply_Agent2_No_Use_His_Preference.replace('{0}', str(input_d['Input']))
            system_prompt = system_prompt.replace('{2}', str(input_d['Must answer']))
            input_d['step_system_prompt'] = system_prompt
        elif subset_name in ['使用历史偏好']:
            input += f"## 历史偏好\n{input_d.get('hist_Pre', '{}')}\n\n"
            input_d['step_system_prompt'] = Food_Reply_Agent3_Use_His_Preference.replace('{0}', str(input_d['Input']))
        elif subset_name in ['追加']:
            input += f"## 历史偏好\n{'{}'}\n\n"
            input_d['step_system_prompt'] = Food_Reply_Agent4_More.replace('{0}', str(input_d['Input']))
        elif subset_name in ['追问商品名称']:
            input += f"## 历史偏好\n{'{}'}\n\n"
            input_d['step_system_prompt'] = Food_Replay_Agent_More_Food_Name.replace('{0}', str(input_d['Input']))
            input_d['step_system_prompt_2'] = Product_Check_Agent_Food
        input += f"## 用户输入 {input_d['Input']}"
        messages.append({'role': 'user', 'content': f'{input}\n\n/nothink'})
        input_d['turns'].append(messages)
        return self.gen_prompt_data(prompt='', index=0, messages=input_d)

    def get_gold_answer(self, input_d: dict) -> str:
        if 'clarify_ans' in input_d:
            return input_d['clarify_ans']
        elif 'hist_ans' in input_d:
            return input_d['hist_ans']
        elif 'my_testAnswer' in input_d:
            return input_d['my_testAnswer']
        else:
            return None

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        return result

    def match(self, gold: str, pred: str, question: str, subset_name) -> float:
        if subset_name == '参数校验' or subset_name == '不使用历史偏好' or subset_name == '使用历史偏好':
            isSatisfied = check_hist_pre(pred, gold)
            if isSatisfied['满意度'] == '非常满意':
                return True
            else:
                return False
        elif subset_name == '追加':
            isSatisfied = check_add_more_clarify(pred, gold)
            if isSatisfied['满意度'] == '非常满意':
                return True
            else:
                return False
        elif str(pred) == '1':
            result = True
        else:
            result = False
        print(result)
        return result
    '\n    pred : [\n        [ans_str_turn0],\n        [ans_str_ans_str_turn1],\n    ]\n    kwargs={\n        raw_input: res_dict[subset_name]\n        subset_name: str\n    }\n    '
