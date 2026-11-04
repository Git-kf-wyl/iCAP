# Private iCAP Yellow business implementation. Do not publish.
import os
import pandas as pd
import requests
import json
import re
import time
import logger
import prompt
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from services.aisf.perception_plan.constants import BASE_DIR, BASE_DIR_OUTPUT
from services.aisf.thread_util import parse
url = '1'
model_name = '2'
is_think = False
Slow_Intent_Prompt = '\n你是运行在智能机顶盒上的的意图感知助手，你的任务是根据用户输入，结合历史对话记录，识别用户问题，排除背景信息干扰，并准确感知用户真正的意图，选择对应的agent。根据输入感知用户的意图并进行任务分解规划。\n按照以下规则处理用户输入：\n1. **任务分解**：将复合请求分解为独立子任务，每个子任务必须包含：\n    -智能体名称（根据任务类型选择agent类型）\n    -任务内容（结合历史对话，精确完整提取用户需求，不要模糊）\n2. **意图识别**：判断输入对应的任务类型（可选：公共类、通话类、健身类、观影类、闲聊类）\n3. **按规定格式输出**：JSON列表格式输出，输出格式如下：\n[{"agent_name": "xxxAgent","context": "任务描述"}]\n\n## 所有输出结果必须完全符合输出格式，不允许省略字段或变更结构，引号为双引号，遵循下列规则\n\n**感知规则**  \n- 公共类(CommonAgent):音量调节、播放操作（续播、重播、快进快退、上一集下一集、选集、倍速设置、清晰度设置）、收藏操作、查看详情、账号操作、内容更换、打开关闭APP、弹窗操作、屏幕操作、点赞评价、摄像头操作、关机等电视操作\n- 通话类(AVCallAgent):仅涉及来电操作、拨打接听电话、添加修改删除联系人操作、黑/白名单操作、自动回复、勿扰模式操作、通话记录操作、打开拨号盘、查看拦截电话这些通话场景\n- 健身类(FitnessAgent):健身课程搜索或推荐、打开或播放具体健身课程、健身计划操作、健身日程操作、查看历史上课记录、查看历史锻炼时间场景\n- 观影类(MovieAgent):仅涉及影视推荐与搜索场景，包括电视剧、电影、综艺等；其他影视播放相关操作归属到公共类。打开/调到具体电视频道属于观影类\n- 闲聊类(ChatAgent): 不符合以上的场景，如百科问答、闲聊\n\n**多意图任务分解规则**\n- 多个不同的任务要单独拆分开，分解为不同的子任务，即使Agent相同\n- 搜索健身课程属于一个完整性任务，禁止分解,其中课程时长、练习时长、锻炼部位、锻炼器材等为补充性描述，禁止划分为子任务\n- 健身类场景设置背景音乐禁止分解为子任务\n- 搜索或推荐不同类型的健身课程必须合并为一个任务，禁止拆分\n- 搜索影视也属于一个完整性任务，指定导演、演员等为补充性描述，禁止划分为子任务\n\n## 注意\n- 播放具体影视电影，涉及两个子任务：搜索节目，对应MovieAgent;播放节目,对应CommonAgent。播放具体集数，对应CommonAgent\n- 打开/播放具体健身课程是一个任务，无须分解\n- 查看当前页面电视剧、电影详情，查看当前页面课程详情都属于CommonAgent\n- 查看/查找具体联系人的联系方式、信息、号码属于CommonAgent;添加/保存/修改/编辑/删除具体联系人、信息、号码属于AVCallAgent\n- 类似"想看xxx"、"要看xxx"、"练习xxx"等描述为搜索课程或影视，不涉及播放\n- 遇到"算了"、"还是"等意图变更的关键词，以用户最后一句的明确指令为准\n- 打开或关闭任何APP属于CommonAgent\n- 重播为从头开始播放，快退重看某一情节不属于重播\n- 搜索视频需根据视频内容判断具体场景\n- 添加/取消/查看收藏联系人、电影、电视剧、健身课程等收藏操作属于CommonAgent\n\n## 示例1\n输入：\n刚才的打斗画面太精彩了，帮我快退3分钟，我要再看一遍\n输出：\n[{"agent_name": "CommonAgent", "context": "快退3分钟"}]\n\n## 示例2\n输入：\n帮我搜一下莫莫的普拉提课程，今天浅练个30分钟，背景音乐选林俊杰的江南\n输出：\n[{"agent_name": "FitnessAgent", "context": "搜索莫莫的普拉提课程，30分钟，背景音乐选林俊杰的江南"}]\n\n## 示例3\n输入：\n给我搜索Coco老师半小时左右的瑜伽课，莫莫老师也不错，都推荐一下\n输出：\n[{"agent_name": "FitnessAgent", "context": "搜索Coco老师和莫莫老师的的瑜伽课，半小时左右"}]\n\n'

def read_from_excel(filename):
    test_cases = []
    df = pd.read_excel(filename, keep_default_na=False)
    for index, row in df.iterrows():
        case_id = row['ID']
        input_data = row['Input']
        expected_answer = row['TestAnswer']
        test_cases.append({'ID': case_id, 'Input': input_data, 'TestAnswer': expected_answer})
    return test_cases

def write_to_excel(filename, out_data, successCount, successesRate, average_Time, max_elapse_time, min_elapse_time):
    df1 = pd.DataFrame(out_data)
    data = {'Test Result': ['Success Rate'], str(successCount) + '/' + str(len(out_data)): [str(successesRate)], 'Average_Time': average_Time, 'Max_Elapse_Time': max_elapse_time, 'Min_Elapse_Time': min_elapse_time, 'Prompt': Slow_Intent_Prompt}
    df2 = pd.DataFrame(data)
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)
        df2.to_excel(writer, sheet_name='Test Result Summary', index=False)

def write_to_bad_case(filename, out_data):
    df1 = pd.DataFrame(out_data)
    with pd.ExcelWriter(filename) as writer:
        df1.to_excel(writer, sheet_name='LLM test result', index=False)

def connect_model(data):
    content = data.get('Input')
    if not is_think:
        content += '\n/nothink'
    headers = {'Content-Type': 'application/json'}
    body = {'model': model_name, 'messages': [{'role': 'system', 'content': Slow_Intent_Prompt}, {'role': 'user', 'content': content}], 'temperature': 0}
    start_time = time.time()
    response = requests.post(url, json=body, headers=headers)
    end_time = time.time()
    elapsed_time = end_time - start_time
    my_logger.info('花费了:' + str(elapsed_time) + '秒')
    message = json.loads(response.text)['choices'][0]['message']['content']
    my_logger.info(response.text)
    tokens = json.loads(response.text)['usage']
    return (message, elapsed_time, tokens)

def is_successful(LLM_answer, expected_answer):
    test_answer = expected_answer.get('TestAnswer').split(',')
    data = LLM_answer.replace('```', '')
    data = data.replace('json', '')
    try:
        data = json.loads(data)
    except Exception as e:
        my_logger.error('字符串转化为JSON错误' + str(e))
        return (0, str(data) + '字符串转化为JSON错误')
    if len(data) > 1:
        return (0, '单意图被识别为多意图')
    try:
        if test_answer[0] == data[0]['agent_name']:
            return (1, 'success')
        else:
            return (0, 'agent_name匹配错误')
    except Exception as e:
        return (0, '匹配失败' + str(e))

def extract_clean_text(text):
    """去除 HTML 标签并清理空白字符"""
    text = re.sub('<[^>]+>', '', text)
    text = re.sub('\\s+', ' ', text).strip()
    return text

def parse_think_response_clean(message_body):
    """
    解析消息体，分割出 think 内容和回答内容（纯文本）
    返回: (think_content, answer_content)
          如果没有 </think>，则 think_content=None
    """
    if '</think>' in message_body:
        parts = message_body.split('</think>', 1)
    else:
        parts = message_body
    if len(parts) == 2:
        answer_content = extract_clean_text(parts[1])
    else:
        answer_content = extract_clean_text(message_body)
    return answer_content
