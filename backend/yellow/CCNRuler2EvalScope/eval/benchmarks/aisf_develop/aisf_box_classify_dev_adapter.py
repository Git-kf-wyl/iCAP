# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.aisf_develop.utils import box_classify_process_results
from typing import List, Any
import os
import json
import pandas as pd
import base64
from PIL import Image
import csv
from eval.benchmarks.aisf_release.qwen_resize import smart_resize
CLASSIFY_PROMPT2 = '\n你是一个专业的意图感知助手，你的任务是根据用户输入识别用户问题，排除背景信息干扰，并准确感知用户真正的意图，选择对应的agent。根据输入感知用户的意图并进行任务分解规划。\n按照以下规则处理用户输入：\n1.**意图识别**：判断输入涉及的任务类型（可选：公共类、通话类、健身类、观影类、闲聊类）\n2.**任务分解**：将复合请求分解为独立子任务，每个子任务必须包含：\n    -智能体名称（根据任务类型选择agent类型）\n    -任务内容（精确提取用户需求）\n3.**输出格式**：JSON列表格式输出，输出格式如下：\n[{"agent_name": "xxxAgent","context": "任务描述"}]\n\n## 所有输出结果必须完全符合输出格式，不允许省略字段或变更结构\n\n**感知规则**  \n- 公共类(CommonAgent):音量调节、播放操作（续播、重播、快进快退、上一集下一集、选集、倍速设置、清晰度设置）、收藏操作、查看详情、账号操作、内容更换、打开关闭APP、弹窗操作、屏幕操作、点赞评价、摄像头操作等操作\n- 通话类(AVCallAgent):如来电操作、拨打接听电话、添加修改删除联系人操作、黑/白名单操作、自动回复、勿扰模式操作、通话记录操作、打开拨号盘等相关通话场景\n- 健身类(FitnessAgent):健身课程搜索或推荐、健身计划操作、健身日程操作、查看历史上课记录、查看历史锻炼时间场景\n- 观影类(MovieAgent):仅涉及影视推荐与搜索场景，其他影视相关的操作归属到公共类\n- 闲聊类(ChatAgent): 不符合以上的场景，默认为闲聊\n\n**多意图任务分解规则**\n- 多个不同的任务要单独拆分开，分解为不同的子任务，即使Agent相同\n- 搜索健身课程与影视属于一个完整性任务，禁止分解，课程时长、练习时长、锻炼部位、指定导演演员等为补充性描述，不需要再划分为子任务\n\n## 注意\n- 播放具体影视节目，涉及两个子任务：搜索节目，对应MovieAgent;播放节目,对应CommonAgent。播放具体集数，对应CommonAgent\n- 查看联系人信息，查看当前页面电视剧、电影详情，查看当前页面课程详情都属于CommonAgent\n- 类似"我想看xxx"、"我要看xxx"等描述为搜索课程或影视，不涉及播放\n- 遇到"算了"、"还是"等意图变更的关键词，以用户最后一句的明确指令为准\n'

@Benchmark.register(name='aisf_box_classify_dev', pretty_name='SERVICE', dataset_id='aisf_box_classify_dev', subset_list=['default'], metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFBoxClassifyDevAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        excel_files = [f for f in os.listdir(input_file_path) if f.endswith(('.xlsx', '.xls'))]
        for excel_file in excel_files:
            file_path = os.path.join(input_file_path, excel_file)
            content = []
            df = pd.read_excel(file_path, sheet_name=0, keep_default_na=False)
            for index, row in df.iterrows():
                content.append({'query': row['query'], 'task_type': row['任务类型']})
        res_dict['default'] = content
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        problem = str(input_d['query']) + '\n\n/no_think'
        full_prompt = self.prompt_template.format(query=problem)
        if self.system_prompt:
            system_prompt = self.system_prompt
        else:
            system_prompt = CLASSIFY_PROMPT2
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        gold_answer = input_d['task_type']
        return gold_answer

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, answer: str, pred: str, raw_input_d: str, subset_name) -> float:
        pred = pred.lstrip('\n')
        res = box_classify_process_results(answer, pred)
        return res

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        res_dict = super().compute_dict_metric(review_res_list, **kwargs)
        return super().compute_metric(res_dict, **kwargs)
