# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from typing import List, Any
import os
import json
from eval.benchmarks.aisf_release.utils import read_from_excel, is_valid
from eval.benchmarks.aisf_release.utils import parse_think_response_clean
from eval.benchmarks.aisf_release.prompt import SingleIntentIdentPrompt
from eval.benchmarks.aisf_release.utils import get_json_structure
import logging

@Benchmark.register(name='aisf_perception_planning', pretty_name='AISF', dataset_id='aisf_perception_planning', subset_list=['出行', '工具调用', '购物', '美食', '多意图'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFPerceptionIntentAdapter(DataAdapter):

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
            elif '感知规划多意图' in excel_file:
                res_dict['多意图'] = data
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
        full_prompt = self.prompt_template.format(query=problem) + '\n/nothink'
        system_prompt = SingleIntentIdentPrompt
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return input_d['Test answer']

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        pred = result.replace('```', '')
        pred = pred.replace('json', '')
        try:
            pred = json.loads(pred)
        except Exception as e:
            print('字符串转化为JSON错误' + str(e))
        return pred

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        try:
            app = raw_input_d['APP']
            if is_valid(app) is False:
                app = ''
            if subset_name != '多意图':
                if len(pred) != 1:
                    logging.info('单意图被识别为多意图')
                    return False
                if gold == 'FoodieAgent':
                    if app != pred[0]['APP']:
                        logging.info('App提取错误')
                        return False
                    if pred[0]['APP'] == '美团':
                        logging.info('success')
                        return True
                    elif pred[0]['agent_name'] == 'FoodieAgent':
                        logging.info('success')
                        return True
                    else:
                        logging.info('Agent识别错误')
                        return False
                elif gold == 'AnyShoppingAgent':
                    if app != pred[0]['APP']:
                        logging.info('App提取错误')
                        return False
                    if pred[0]['APP'] == '淘宝':
                        logging.info('success')
                        return True
                    elif pred[0]['agent_name'] == 'AnyShoppingAgent' and pred[0]['APP'] == '京东':
                        logging.info('success')
                        return True
                    elif pred[0]['agent_name'] == 'AnyShoppingAgent' and pred[0]['APP'] == '':
                        logging.info('success')
                        return True
                    else:
                        logging.info('Agent识别错误')
                        return False
                elif gold == 'AnyShoppingAgent':
                    if app != pred[0]['APP']:
                        logging.info('App提取错误')
                        return False
                    if pred[0]['APP'] == '携程':
                        logging.info('success')
                        return True
                    elif pred[0]['APP'] == '高德':
                        logging.info('success')
                        return True
                    elif pred[0]['agent_name'] == 'LifeAssistantAgent' and pred[0]['APP'] == '':
                        logging.info('success')
                        return True
                    else:
                        logging.info('Agent识别错误')
                        return False
                elif gold == pred[0]['agent_name']:
                    logging.info('success')
                    return True
                else:
                    logging.info('Agent识别错误')
                    return False
            else:
                answer_json = get_json_structure(raw_input_d['Test answer'])
                if len(answer_json) != len(pred):
                    print('Agent数量匹配错误')
                    return False
                for test_answer_item, data_item in zip(answer_json, pred):
                    if test_answer_item['agent_name'] != data_item['agent_name']:
                        print('LLM模型返回的agent_name与测试答案不一致')
                        return False
                    if test_answer_item['agent_name'] == 'LifeAssistantAgent' and test_answer_item['APP'] == '':
                        continue
                    if test_answer_item['APP'] != data_item['APP']:
                        print('LLM模型返回的APP与测试答案不一致')
                        return False
                return True
        except Exception as e:
            logging.error(f'发生了一个错误：{e}')
            logging.info(pred)
            return False

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
