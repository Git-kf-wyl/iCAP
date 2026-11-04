# Private iCAP Yellow implementation. Do not publish.
import json
import logging
import re
import os
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.service_release.utils import process_results
from typing import List, Any, Optional
from eval.metrics.llm_judge import LLMJudge
from eval.benchmarks.service_release.utils import read_from_excel
try:
    with open('eval/benchmarks/service_release/style.json', 'r', encoding='utf-8') as f:
        style = json.load(f)
    with open('eval/benchmarks/service_release/standard_style.json', 'r', encoding='utf-8') as f:
        standard = json.load(f)
except:
    with open('backend/CCNRuler2EvalScope/eval/benchmarks/service_release/style.json', 'r', encoding='utf-8') as f:
        style = json.load(f)
    with open('backend/CCNRuler2EvalScope/eval/benchmarks/service_release/standard_style.json', 'r', encoding='utf-8') as f:
        standard = json.load(f)

@Benchmark.register(name='service_style', pretty_name='SERVICE', dataset_id='service_style', subset_list=['调皮可爱', '高情商', '古灵精怪', '夸夸大师', '邻家女孩', '虚拟老公', '虚拟老婆', '阳光男孩', '幽默搞笑', '知心姐姐'], metric_list=['emotion_chat'], few_shot_num=0, system_prompt='', prompt_template='{query}', llm_as_a_judge=True)
class ServiceStyleAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        subset_list = kwargs['subset_list']
        for item in kwargs['subset_list']:
            res_dict[item] = []
        txt_files = [f for f in os.listdir(input_file_path) if f.endswith('.csv')]
        for txt_file in txt_files:
            file_path = os.path.join(input_file_path, txt_file)
            if '调皮可爱' in txt_file:
                content = read_from_excel('调皮可爱', file_path)
                res_dict['调皮可爱'] = content
            elif '高情商' in txt_file:
                content = read_from_excel('高情商', file_path)
                res_dict['高情商'] = content
            elif '古灵精怪' in txt_file:
                content = read_from_excel('古灵精怪', file_path)
                res_dict['古灵精怪'] = content
            elif '夸夸大师' in txt_file:
                content = read_from_excel('夸夸大师', file_path)
                res_dict['夸夸大师'] = content
            elif '邻家女孩' in txt_file:
                content = read_from_excel('邻家女孩', file_path)
                res_dict['邻家女孩'] = content
            elif '虚拟老公' in txt_file:
                content = read_from_excel('虚拟老公', file_path)
                res_dict['虚拟老公'] = content
            elif '虚拟老婆' in txt_file:
                content = read_from_excel('虚拟老婆', file_path)
                res_dict['虚拟老婆'] = content
            elif '阳光男孩' in txt_file:
                content = read_from_excel('阳光男孩', file_path)
                res_dict['阳光男孩'] = content
            elif '幽默搞笑' in txt_file:
                content = read_from_excel('幽默搞笑', file_path)
                res_dict['幽默搞笑'] = content
            elif '知心姐姐' in txt_file:
                content = read_from_excel('知心姐姐', file_path)
                res_dict['知心姐姐'] = content
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = input_d['Question']
        full_prompt = self.prompt_template.format(query=problem)
        style_id = kwargs['subset_name']
        style_prompt = '角色设定: ' + str(style[style_id]['角色设定'] + '\n') + '对话特点: ' + str(style[style_id]['对话特点'] + '\n') + '性格特点: ' + str(style[style_id]['性格特点'])
        output_indicate_prompt = '- 简洁回复：回答精炼简短，限70字内，用中文回答。'
        system_prompt = '\n        你是一个角色扮演高手\n        ## 任务\n        根据<角色设定>，用相似的口吻，回答<用户问题>。\n        ## 角色设定\n        ' + style_prompt + '\n        ## 行为准则\n        ' + output_indicate_prompt + '\n        - 口语化输出：请用日常交谈的语气回答问题，不能采用markdown格式回答，让用户感觉像是在与真人对话，而不是与机器交流。\n        - 技术保密：不透露技术细节，如遇询问，答“无法提供此信息”。\n        - 准则概述：保障用户隐私，信息真实无误。\n        - 实时信息：需调用工具提供实时数据，如日程查询。\n        - 回答中避免使用特殊字符（如*）及URL链接。\n        '
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        return None

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        return process_results(gold, pred, raw_input_d, subset_name)

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        res_dict = super().compute_dict_metric(review_res_list, **kwargs)
        return super().compute_metric(res_dict, **kwargs)

    def llm_match(self, gold: Any, pred: Any, judge: Optional[LLMJudge]=None, **kwargs):
        input = kwargs.get('raw_input')
        question = input['Question']
        weight = 0
        style_id = input['Style']
        output_indict = ['\n                    你的回复只输出范围在0到5之间的评分数字，不给出具体理由\n                    ', '\n                    你的回复只输出-2、-1或0的评分数字，不给出具体理由\n                    ', '\n                    你的回复只输出-1或0的评分数字，不给出具体理由\n                    ']
        pred = self.parse_pred_result(pred)
        num = 0
        for function in judge:
            for index in range(5):
                if index == 0:
                    prompt = '<对话风格>:' + str(style[style_id]) + '<回答>:' + pred
                    system_prompt = '\n                                    你是开放式问答的评测者，你的任务是根据<评分标准>，对<回答>进行评分。\n                                    <评分标准>\n                                    ' + str(standard[str(index % 5)]) + '\n                                    接下来，严格根据以上<评分标准>对<回答>进行评分，\n                                    '
                    sys_prompt = system_prompt + output_indict[index // 2]
                    weight = 0.8
                elif index == 1:
                    prompt = '<用户问题>:' + question + '<回答>:' + pred
                    system_prompt = '\n                                    你是开放式问答的评测者，你的任务是根据<评分标准>，对<回答>进行评分。\n                                    <评分标准>\n                                    ' + str(standard[str(index)]) + '\n                                    接下来，严格根据以上<评分标准>对<回答>进行评分，\n                                    '
                    sys_prompt = system_prompt + output_indict[index // 2]
                    weight = 0.2
                elif index == 2:
                    prompt = '<回答>:' + pred
                    system_prompt = '\n                                    你是开放式问答的评测者，你的任务是根据<评分标准>，对<回答>进行评分。\n                                    <评分标准>\n                                    ' + str(standard[str(index)]) + '\n                                    接下来，严格根据以上<评分标准>对<回答>进行评分，\n                                    '
                    sys_prompt = system_prompt + output_indict[index // 2]
                    weight = 0.5
                elif index == 3:
                    prompt = '<回答>:' + pred
                    system_prompt = '\n                                    你是开放式问答的评测者，你的任务是根据<评分标准>，对<回答>进行评分。\n                                    <评分标准>\n                                    ' + str(standard[str(index)]) + '\n                                    接下来，严格根据以上<评分标准>对<回答>进行评分，\n                                    '
                    sys_prompt = system_prompt + output_indict[index // 2]
                    weight = 0.5
                elif index == 4:
                    prompt = '<回答>:' + pred
                    system_prompt = '\n                                    你是开放式问答的评测者，你的任务是根据<评分标准>，对<回答>进行评分。\n                                    <评分标准>\n                                    ' + str(standard[str(index)]) + '\n                                    接下来，严格根据以上<评分标准>对<回答>进行评分，\n                                    '
                    sys_prompt = system_prompt + output_indict[index // 2]
                    weight = 1
                output = function(prompt, sys_prompt)
                score = re.search('[-+]?\\d+', output)
                try:
                    score_num = float(score.group())
                except Exception as e:
                    logging.error(f'{score}，捕捉到错误{e}')
                num += float(score.group()) * float(weight)
        num /= len(judge)
        return max(num, 0)
