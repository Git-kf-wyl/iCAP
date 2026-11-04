# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_develop.utils import read_multicolums_from_excel
from eval.benchmarks.aisf_develop.prompt import THEME_integrated_PROMPT, THEME_RECALL_PROMPT, ATTRIBUTES_EXTRACT_PROMPT, TIME_HOTEL_PROMPT, CITY_PROMPT, FACT_DETERMINE_PROMPT, THEME_DETERMINE_PROMPT

@Benchmark.register(name='aisf_extract', pretty_name='AISF', dataset_id='aisf_extract', subset_list=['事实记忆萃取', '记忆召回', '属性萃取', '时间酒店信息提取', '城市名提取', '事实记忆决策', '主题记忆决策'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFExtractAdapter(DataAdapter):

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
            if '719extractandrecall' in excel_file:
                res_dict['事实记忆萃取'] = read_multicolums_from_excel(file_path, 0, [1])
                res_dict['记忆召回'] = read_multicolums_from_excel(file_path, 1, [1])
            elif 'testofextractandrecall_broad' in excel_file:
                res_dict['事实记忆萃取'].extend(read_multicolums_from_excel(file_path, 0, [1]))
                res_dict['事实记忆萃取'].extend(read_multicolums_from_excel(file_path, 1, [1]))
                res_dict['记忆召回'].extend(read_multicolums_from_excel(file_path, 2, [1]))
                res_dict['记忆召回'].extend(read_multicolums_from_excel(file_path, 3, [1]))
            elif 'testofattribute' in excel_file:
                res_dict['属性萃取'] = read_multicolums_from_excel(file_path, 0, [1, 3])
            elif 'timeHotel' in excel_file:
                res_dict['时间酒店信息提取'] = read_multicolums_from_excel(file_path, 0, [1, 3])
            elif 'testofcity' in excel_file:
                res_dict['城市名提取'] = read_multicolums_from_excel(file_path, 0, [1, 3])
            elif 'testoffact' in excel_file:
                res_dict['事实记忆决策'] = read_multicolums_from_excel(file_path, 0, [1, 2, 3])
            elif 'testofdetermine' in excel_file:
                res_dict['主题记忆决策'] = read_multicolums_from_excel(file_path, 0, [1, 2, 3])
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        subset_name = kwargs['subset_name']
        if subset_name == '事实记忆萃取':
            full_prompt = '##当前输入\n' + str(input_d) + '/no_think'
            if 'system_prompt_theme_integrated' in self.config_kwargs:
                system_prompt = self.config_kwargs['system_prompt_theme_integrated'] if self.config_kwargs['system_prompt_theme_integrated'] else THEME_integrated_PROMPT
            else:
                system_prompt = THEME_integrated_PROMPT
        elif subset_name == '记忆召回':
            full_prompt = '##当前输入\n' + str(input_d) + '/no_think'
            if 'system_prompt_theme_recall' in self.config_kwargs:
                system_prompt = self.config_kwargs['system_prompt_theme_recall'] if self.config_kwargs['system_prompt_theme_recall'] else THEME_RECALL_PROMPT
            else:
                system_prompt = THEME_RECALL_PROMPT
        elif subset_name == '属性萃取':
            full_prompt = '##当前输入\n' + str(input_d) + '/no_think'
            if 'system_prompt_attributes_extract' in self.config_kwargs:
                system_prompt = self.config_kwargs['system_prompt_attributes_extract'] if self.config_kwargs['system_prompt_attributes_extract'] else ATTRIBUTES_EXTRACT_PROMPT
            else:
                system_prompt = ATTRIBUTES_EXTRACT_PROMPT
        elif subset_name == '时间酒店信息提取':
            full_prompt = '##当前输入\n' + str(input_d) + '/no_think'
            if 'system_prompt_time_hotel' in self.config_kwargs:
                system_prompt = self.config_kwargs['system_prompt_time_hotel'] if self.config_kwargs['system_prompt_time_hotel'] else TIME_HOTEL_PROMPT
            else:
                system_prompt = TIME_HOTEL_PROMPT
        elif subset_name == '城市名提取':
            full_prompt = '##当前输入\n' + str(input_d) + '/no_think'
            if 'system_prompt_city' in self.config_kwargs:
                system_prompt = self.config_kwargs['system_prompt_city'] if self.config_kwargs['system_prompt_city'] else CITY_PROMPT
            else:
                system_prompt = CITY_PROMPT
        elif subset_name == '事实记忆决策':
            full_prompt = str(input_d['column1']) + '\n' + str(input_d['column2']) + '/no_think'
            if 'system_prompt_fact_determine' in self.config_kwargs:
                system_prompt = self.config_kwargs['system_prompt_fact_determine'] if self.config_kwargs['system_prompt_fact_determine'] else FACT_DETERMINE_PROMPT
            else:
                system_prompt = FACT_DETERMINE_PROMPT
        elif subset_name == '主题记忆决策':
            full_prompt = '\n用户请求：' + str(input_d['column1']) + '\n备选商品：' + str(input_d['column2']) + '/no_think'
            if 'system_prompt_theme_determine' in self.config_kwargs:
                system_prompt = self.config_kwargs['system_prompt_theme_determine'] if self.config_kwargs['system_prompt_theme_determine'] else THEME_DETERMINE_PROMPT
            else:
                system_prompt = THEME_DETERMINE_PROMPT
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        if 'column3' in input_d:
            return input_d['column3']
        else:
            return None

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        if subset_name == '记忆召回' or subset_name == '事实记忆萃取':
            return False
        elif gold is not None and pred is not None:
            if gold.replace(' ', '') == pred.replace(' ', ''):
                return True
            else:
                return False
        else:
            return False

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
