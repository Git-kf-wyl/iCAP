# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_release.utils import read_from_excel_function_call, is_sucessful, is_valid
from eval.benchmarks.aisf_release.utils import parse_think_response_clean
from eval.benchmarks.aisf_release.prompt import FunctionCallPrompt
from datetime import datetime
today = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
week_day_cn = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']

@Benchmark.register(name='aisf_function_call', pretty_name='AISF', dataset_id='aisf_function_call', subset_list=['小艺', '天气查询', '周边查询'], model_adapter='aisf_function_call_server', metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFFunctionCllAdapter(DataAdapter):

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
            data = read_from_excel_function_call(file_path)
            for i in range(len(data)):
                if data[i]['Expect name'] == 'aisf_mcp_server_huawei_ai_search':
                    res_dict['小艺'].append(data[i])
                elif data[i]['Expect name'] == 'aisf_mcp_server_query_weather':
                    res_dict['天气查询'].append(data[i])
                elif data[i]['Expect name'] == 'aisf_mcp_server_surround_search':
                    res_dict['周边查询'].append(data[i])
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = str(input_d['Input']) + '/nothink'
        full_prompt = self.prompt_template.format(query=problem)
        week_day = datetime.now().weekday()
        system_prompt = FunctionCallPrompt.replace('{{0}}', today + ' ' + week_day_cn[week_day]).replace('{{1}}', '南京')
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['Expect name']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d, subset_name) -> float:
        is_success = True
        if is_valid(raw_input_d['Expect name']):
            step_res = is_sucessful(pred, raw_input_d['Expect name'])
            is_success = step_res and is_success
        if is_valid(raw_input_d['Expect keywords1']):
            step_res = is_success and is_sucessful(pred, raw_input_d['Expect keywords1'])
            is_success = step_res and is_success
        if is_valid(raw_input_d['Expect keywords2']):
            step_res = is_sucessful(pred, raw_input_d['Expect keywords2'])
            is_success = step_res and is_success
        return is_success

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
