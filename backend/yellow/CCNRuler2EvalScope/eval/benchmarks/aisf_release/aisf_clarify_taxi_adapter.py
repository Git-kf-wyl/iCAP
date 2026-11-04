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
from eval.benchmarks.aisf_release.utils import read_from_excel_taxi_para_check, read_from_excel_taxi_must_clarify, read_from_excel_taxi_change_user, is_successful, partial_format
from typing import Any, Optional
from eval.benchmarks.aisf_release.prompt import TaxiPrompt
from eval.metrics.llm_judge import LLMJudge
from eval.benchmarks.aisf_release.judge_step_sys_prompt import Travel_Reply_Prompt_Taxi_Para_Check, Travel_Reply_Prompt_Taxi_Must_Clarify, Travel_Reply_Prompt_Taxi_Change_User
from eval.benchmarks.aisf_release.judge_step_sys_prompt_2 import Clarify_Travel_Prompt_Taxi

@Benchmark.register(name='aisf_clarify_taxi', pretty_name='AISF Clarify Test', dataset_id='aisf_clarify_taxi', subset_list=['参数校验', '必须澄清', '更改用户原始诉求'], metric_list=['AverageAccuracy'], model_adapter='aisf_clarify_server', few_shot_num=0, system_prompt=None, prompt_template='{query}', extra_params={'need_step_judge': True})
class AISFClarifyTaxiDataAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        extra_params = kwargs.get('extra_params', {})
        self.need_step_judge = extra_params.get('need_step_judge', False)
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        excel_files = [f for f in os.listdir(input_file_path) if f.endswith(('.xlsx', '.xls'))]
        for excel_file in excel_files:
            file_path = os.path.join(input_file_path, excel_file)
            if '参数校验' in excel_file:
                res_dict['参数校验'] = read_from_excel_taxi_para_check(file_path)
            elif 'taxi_必须要澄清的参数02' in excel_file:
                res_dict['必须澄清'] = read_from_excel_taxi_must_clarify(file_path)
            elif 'taxi_更改用户原始诉求03' in excel_file:
                res_dict['更改用户原始诉求'] = read_from_excel_taxi_change_user(file_path)
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
        d = datetime.now()
        messages = []
        messages.append({'role': 'system', 'content': TaxiPrompt})
        input = ''
        if subset_name in ['参数校验']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            ans_prompt = Travel_Reply_Prompt_Taxi_Para_Check
            default_address = json.dumps(input_d['default_address'], ensure_ascii=False)
            ans_prompt = partial_format(ans_prompt, **{'1': default_address})
            input_d['step_system_prompt'] = ans_prompt
        elif subset_name in ['必须澄清']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Taxi_Must_Clarify.replace('{1}', str(input_d['default_address']))
            input_d['step_system_prompt_2'] = Clarify_Travel_Prompt_Taxi.replace('{1}', str(input_d['clarify']))
        elif subset_name in ['更改用户原始诉求']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Taxi_Change_User.replace('{1}', str(input_d['default_address']))
        input += f"## 用户输入 {input_d['Input']}"
        messages.append({'role': 'user', 'content': f'{input}\n\n/nothink'})
        input_d['turns'].append(messages)
        return self.gen_prompt_data(prompt='', index=0, messages=input_d)

    def get_gold_answer(self, input_d: dict) -> str:
        if 'Test answer' in input_d:
            return input_d['Test answer']
        else:
            return None

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        return result

    def match(self, gold: str, pred: str, question: str, subset_name) -> float:
        if subset_name != '必须澄清':
            result = is_successful(gold, pred)
        elif str(pred) == '1':
            result = True
        else:
            result = False
        print(result)
        return result
    '\n    pred : [\n        [ans_str_turn0],\n        [ans_str_ans_str_turn1],\n    ]\n    kwargs={\n        raw_input: res_dict[subset_name]\n        subset_name: str\n    }\n    '
