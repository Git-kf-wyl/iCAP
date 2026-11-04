# Private iCAP Yellow implementation. Do not publish.
import os
import pandas as pd
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.service_release.utils import process_results
from typing import Any, Optional
from eval.metrics.llm_judge import LLMJudge

@Benchmark.register(name='test', pretty_name='TEST', dataset_id='test', subset_list=['default'], metric_list=['AverageAccuracy'], model_adapter='aisf_server', few_shot_num=0, system_prompt='直接给出你的答案，不要显示你的分析', prompt_template='{query}', llm_as_a_judge=True, extra_params={'need_step_judge': False})
class TestAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        extra_params = kwargs.get('extra_params', {})
        self.need_step_judge = extra_params.get('need_step_judge', False)
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        """
        Args:
            input_file_path: The path is the storage location for the dataset.
            pred_file_path: None.
            kwargs: subset_list is included here.
        Return: for example
            [
                [{
                    role
                }]
            ]
        """
        res_dict = {}
        txt_files = [f for f in os.listdir(input_file_path) if f.endswith('.xlsx') and (not f.startswith('~'))]
        for txt_file in txt_files:
            file_path = os.path.join(input_file_path, txt_file)
            df = pd.read_excel(file_path)
            question_temp = {}
            for row in df.values:
                if row[1] in question_temp:
                    question_temp[row[1]]['question'].append(row[2])
                    question_temp[row[1]]['answer'].append(row[3])
                else:
                    question_temp[row[1]] = {'question_num': row[1], 'question': [row[2]], 'answer': [row[3]]}
            res_dict['default'] = question_temp.values()
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        input_d['turns'] = []
        input_d['need_step_judge'] = True if self.need_step_judge else False
        for index, step in enumerate(input_d['question']):
            messages = []
            if index == 0:
                messages.append({'role': 'system', 'content': self.system_prompt})
                messages.append({'role': 'user', 'content': step})
            else:
                messages.append({'role': 'user', 'content': step})
            input_d['turns'].append(messages)
        return self.gen_prompt_data(prompt='', index=0, messages=input_d)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        return process_results(gold, pred, raw_input_d, subset_name)

    def llm_match(self, gold: Any, pred: Any, judge: Optional[LLMJudge]=None, **kwargs):
        input = kwargs.get('raw_input')
        score = 0
        for jg in judge:
            prompt = jg.build_aisf_final_message(pred, input['question'])
            outputs = jg(prompt, jg.system_prompt)
            if '正确' in outputs:
                score += 1
            else:
                score -= 1
        if score >= len(judge) / 2:
            return True
        else:
            return False
