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
from eval.benchmarks.aisf_release.utils import read_from_excel_1, read_from_excel_2, read_from_excel_3, read_from_excel_4, read_from_excel_5, is_successful
from typing import Any, Optional
from eval.benchmarks.aisf_release.prompt import AirplanePrompt
from eval.metrics.llm_judge import LLMJudge
from eval.benchmarks.aisf_release.judge_step_sys_prompt import Travel_Reply_Prompt_Book_Para_Check, Travel_Reply_Prompt_Book_Must_Clarify, Travel_Reply_Prompt_Book_Addition_Input, Travel_Reply_Prompt_Book_Not_Use_His_Preference, Travel_Reply_Prompt_Book_Use_His_Preference
from eval.benchmarks.aisf_release.judge_step_sys_prompt_2 import Clarify_Travel_Prompt_Book

@Benchmark.register(name='aisf_clarify_book', pretty_name='AISF Clarify Test', dataset_id='aisf_clarify_book', subset_list=['参数校验', '必须澄清', '追加', '不使用历史偏好', '使用历史偏好'], metric_list=['AverageAccuracy'], model_adapter='aisf_clarify_server', few_shot_num=0, system_prompt=None, prompt_template='{query}', extra_params={'need_step_judge': True})
class AISFClarifyBookDataAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        extra_params = kwargs.get('extra_params', {})
        self.need_step_judge = extra_params.get('need_step_judge', False)
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        excel_files = [f for f in os.listdir(input_file_path) if f.endswith(('.xlsx', '.xls'))]
        for excel_file in excel_files:
            file_path = os.path.join(input_file_path, excel_file)
            if '参数校验Airplane01' in excel_file:
                res_dict['参数校验'] = read_from_excel_1(file_path)
            elif '必须澄清Airplane02' in excel_file:
                res_dict['必须澄清'] = read_from_excel_2(file_path)
            elif '追加Airplane03' in excel_file:
                res_dict['追加'] = read_from_excel_3(file_path)
            elif '不使用历史偏好Airplane_all' in excel_file:
                res_dict['不使用历史偏好'] = read_from_excel_4(file_path)
            elif '使用历史偏好Airplane_all' in excel_file:
                res_dict['使用历史偏好'] = read_from_excel_5(file_path)
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
        messages.append({'role': 'system', 'content': AirplanePrompt})
        input = ''
        if subset_name in ['参数校验']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input += f"## 当前时间\n{input_d.get('Current date', '{}')}"
            input += f'\n## 当前城市 \n\n\n'
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Book_Para_Check
        elif subset_name in ['必须澄清']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Book_Must_Clarify
            input_d['step_system_prompt_2'] = Clarify_Travel_Prompt_Book.replace('{1}', str(['出发日期', '出发地', '目的地']))
        elif subset_name in ['追加']:
            input += f"## 历史偏好\n {'{}'}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            input += f'\n## 当前城市 \n\n\n'
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Book_Addition_Input
        elif subset_name in ['不使用历史偏好']:
            input += f"## 历史偏好\n{input_d.get('User prefer', '{}')}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            input += f'\n\n## 当前城市 \n上海市\n\n'
            system_prompt = Travel_Reply_Prompt_Book_Not_Use_His_Preference.replace('{1}', input_d['Query content'])
            system_prompt = system_prompt.replace('{2}', input_d['Must answer'])
            input_d['step_system_prompt'] = system_prompt
        elif subset_name in ['使用历史偏好']:
            input += f"## 历史偏好\n{input_d.get('User prefer', '{}')}\n\n"
            input += f"## 当前时间\n{d.date()} 星期{'一二三四五六日'[d.weekday()]}\n\n"
            input += f'## 当前城市\n\n\n'
            input_d['step_system_prompt'] = Travel_Reply_Prompt_Book_Use_His_Preference
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
