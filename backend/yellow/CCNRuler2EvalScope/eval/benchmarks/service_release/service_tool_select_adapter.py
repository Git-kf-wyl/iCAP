# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.service_release.utils import process_results_tool_select
from eval.benchmarks.service_release.utils import remove_think
from eval.benchmarks.service_release.utils import remove_question
from typing import List, Any
import os
import json

@Benchmark.register(name='service_tool_select', pretty_name='SERVICE', dataset_id='service_tool_select', subset_list=['check_schedule_default', 'check_schedule_tool', 'delete_schedule_default', 'delete_schedule_tool', 'set_schedule_default', 'set_schedule_tool', 'update_schedule_default', 'update_schedule_tool', 'chat'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt='\n你是一个擅长语义理解并抽取有效信息的机器人，需要精准完成：场景识别、意图识别、参数提取。\n\n**场景识别**\n有下面多种场景，需要你根据“当前场景”和“用户输入”进行判断，只答选项\n1. set_schedule(为用户设置日程) - 请回复1\n2. check_schedule(查询用户现有日程) - 请回复2\n    - 关键词：查看、显示、查询、有没有、什么安排、查一下、有空\n3. delete_schedule(删除用户现有日程) - 请回复3\n4. update_schedule(更改用户现有日程) - 请回复4\n0. default(其他场景) - 请回复0\n\n**意图识别**\n在“当前场景”是set_schedule/check_schedule/delete_schedule/update_schedule的情况下：\n    - 用户确认信息无误，回复CALL。\n    - 用户表示退出，跳转到默认场景0。\n    - 用户查询日程，跳转到2\n    - 用户闲聊（不含日程管理的用意），识别结果与“当前场景”一致。\n\n**参数提取**\n确定场景后，需要根据场景模板提取参数, 场景对应的参数模板如下：\nset_schedule: [{\'name\': \'title\', \'desc\': \'日程的标题\', \'value\': \'\'}, \n              {\'name\': \'location\', \'desc\': \'日程的地点\', \'value\': \'\'}, \n              {\'name\': \'time\', \'desc\': \'日程的时间\', \'value\': \'\'},\n              {\'name\': \'partners\', \'desc\': \'参与日程的人员名单，可以是JSON或逗号分隔的字符串\', \'value\': \'\'}                             \n              ]\ncheck_schedule: []\ndelete_schedule: [{\'name\': \'index\', \'desc\': \'需要删除的日程条目索引列表，正向计数从1开始，反向计数从-1开始\', \'value\': \'\'}]\nupdate_schedule: [{\'name\': \'index\', \'desc\': \'需要删除的日程条目索引列表，数据类型为整型，正向计数从1开始，反向计数从-1开始\', \'value\': \'\'},\n                  {\'name\': \'title\', \'desc\': \'日程的标题\', \'value\': \'\'}, \n                  {\'name\': \'location\', \'desc\': \'日程的地点\', \'value\': \'\'}, \n                  {\'name\': \'time\', \'desc\': \'日程的时间\', \'value\': \'\'}, \n                  {"name": "partners", "desc": "日程涉及的人员，可以是JSON或逗号分隔的字符串", \'value\': \'\'} ]\n上面的JSON中每个元素代表一个参数信息：\n\'\'\'\nname是参数名称\ndesc是参数注释，可以做为参数信息的补充\n\'\'\'\n\n需求：\n#01 根据用户输入内容提取有用的信息到value值，严格提取，没有提及就丢弃该元素\n#02 返回JSON结果，只需要name和value\n#03 关于时间信息抽取不需要计算。如：明天中午12点，只需要提取到明天中午12点，不需要计算\n返回样例：\n```\n输入：“当前场景: default；用户输入：有个社区服务活动，准备在最近去市民中心参加，提醒我一下。”\n输出：1:[{\'name\': \'title\', \'value\': \'社区服务活动\'}, {\'name\': \'location\', \'value\': \'市民中心\'}]\n\n输入：“当前场景: set_schedule；用户输入：在湘之源餐厅吧。”\n输出：1:[’name‘: ’location‘, ’value‘: ’湘之源餐厅‘}]\n\n输入：“当前场景: default；用户输入：在湘之源餐厅吧。”\n输出：0:[]\n\n输入：“当前场景: set_schedule；用户输入：准确。”\n输出：CALL\n\n输入：“当前场景: default；用户输入：准确。”\n输出：0:[]\n\n输入：“当前场景：set_schedule；用户输入：退出设置。”\n输出：0:[]\n\n输入：“当前场景: set_schedule；用户输入：今天天气如何？”\n输出：1:[]\n```\n', prompt_template='{query}')
class ServiceToolSelectAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        subset_list = kwargs['subset_list']
        json_files = [f for f in os.listdir(input_file_path) if f.endswith('.json')]
        for json_file in json_files:
            file_path = os.path.join(input_file_path, json_file)
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if 'check' in json_file and 'default' in json_file:
                    res_dict['check_schedule_default'] = data
                elif 'check' in json_file and 'tool' in json_file:
                    res_dict['check_schedule_tool'] = data
                elif 'delete' in json_file and 'default' in json_file:
                    res_dict['delete_schedule_default'] = data
                elif 'delete' in json_file and 'tool' in json_file:
                    res_dict['delete_schedule_tool'] = data
                elif 'set' in json_file and 'default' in json_file:
                    res_dict['set_schedule_default'] = data
                elif 'set' in json_file and 'tool' in json_file:
                    res_dict['set_schedule_tool'] = data
                elif 'update' in json_file and 'default' in json_file:
                    res_dict['update_schedule_default'] = data
                elif 'update' in json_file and 'tool' in json_file:
                    res_dict['update_schedule_tool'] = data
                elif 'chat' in json_file:
                    res_dict['chat'] = data
        if subset_list:
            for key in list(res_dict.keys()):
                if key not in subset_list:
                    res_dict.pop(key)
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        for message in input_d['messages']:
            if message['role'] == 'user':
                problem = message['content']
                full_prompt = self.prompt_template.format(query=problem)
        system_prompt = self.system_prompt
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        for message in input_d['messages']:
            if message['role'] == 'assistant':
                gold_answer = message['content']
        return gold_answer

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        ans = remove_think(result)
        ans = remove_question(ans)
        return ans

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        return process_results_tool_select(gold, pred, raw_input_d, subset_name)

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        return super().compute_metric(review_res_list, **kwargs)
