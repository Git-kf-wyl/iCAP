# Private iCAP Yellow implementation. Do not publish.
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.aisf_release.utils import process_results
from typing import List, Any
import os
import json
import pandas as pd
import base64
from PIL import Image
import csv
from eval.benchmarks.aisf_release.qwen_resize import smart_resize
SYS_PROMPT = 'You are a helpful assistant.\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\nYou are provided with function signatures within <tools></tools> XML tags:\n<tools>\n{"type": "function", "function": {"name_for_human": "mobile_use", "name": "mobile_use", "description": "Use a touchscreen to interact with a mobile device, and take screenshots.\n* This is an interface to a mobile device with touchscreen. You can perform actions like clicking, typing, swiping, etc.\n* Some applications may take time to start or process actions, so you may need to wait and take successive screenshots to see the results of your actions.\n* The screen\'s resolution is %dx%d.", "parameters": {"properties": {"action": {"description": "The action to perform. The available actions are:\n* `key`: Perform a key event on the mobile device.\n    - This supports adb\'s `keyevent` syntax.\n    - Examples: "volume_up", "volume_down", "power", "camera", "clear".\n* `click`: Click the point on the screen with coordinate (x, y).\n* `long_press`: Press the point on the screen with coordinate (x, y) for specified seconds.\n* `swipe`: Swipe from the starting point with coordinate (x, y) to the end point with coordinates2 (x2, y2).\n* `type`: Input the specified text into the activated input box.\n* `system_button`: Press the system button.\n* `open`: Open an app on the device.\n* `wait`: Wait specified seconds for the change to happen.\n* `handle_exception`: Click the point on the screen with coordinate (x, y) to handle the exception such as ads and floating windows affecting normal operations.\n* `call_user`: Request human intervention, and specify the scene of intervention using the call_user_type (i.e., \'verify\' vs. \'login\'). \n* `terminate`: Terminate the current task and report its completion status.", "enum": ["key", "click", "long_press", "swipe", "type", "system_button", "open", "wait", "handle_exception", "call_user", "terminate"], "type": "string"}, "coordinate": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=click`, `action=long_press`, `action=swipe`, and `action=handle_exception`.", "type": "array"}, "coordinate2": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=swipe`.", "type": "array"}, "text": {"description": "Required only by `action=key`, `action=type`, and `action=open`.", "type": "string"}, "call_user_type": {"description": "Specify the scene of intervention. Use verify for scenarios involving human verification, and use login for scenarios involving human login. Required only by `action=call_user`.", "enum": ["verify", "login"], "type": "string"}, "time": {"description": "The seconds to wait. Required only by `action=long_press` and `action=wait`.", "type": "number"}, "button": {"description": "Back means returning to the previous interface, Home means returning to the desktop, Menu means opening the application background menu, and Enter means pressing the enter. Required only by `action=system_button`", "enum": ["Back", "Home", "Menu", "Enter"], "type": "string"}, "status": {"description": "The status of the task. Required only by `action=terminate`.", "type": "string", "enum": ["success", "failure"]}}, "required": ["action"], "type": "object"}, "args_format": "Format the arguments as a JSON object."}}\n</tools>\n\nFor each function call, return a json object with function name and arguments:\n{"name": <function-name>, "arguments": <args-json-object>}'
USR_PROMPT = 'You are a GUI agent capable of analyzing interface states and performing operational reasoning.\n\n# Output Format\nTool Call: {"name": <function-name>, "arguments": <args-json-object>}\n\n# User Instruction\n'

@Benchmark.register(name='aisf_vla', pretty_name='SERVICE', dataset_id='aisf_vla', subset_list=['ads', 'call_user', 'dd_gd_out', 'jd_buy', 'jd_food', 'mt_food', 'tb_buy', 'tb_food', 'xc_out', 'jd_buy_filter', 'jd_food_filter', 'mt_food_filter', 'tb_buy_filter', 'tb_food_filter', 'xc_out_filter'], model_adapter='vla_server', metric_list=['AverageAccuracy'], few_shot_num=0, system_prompt=None, prompt_template='{query}')
class AISFVlaAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        for item in kwargs['subset_list']:
            res_dict[item] = []
        excel_files = [f for f in os.listdir(input_file_path) if f.endswith(('.xlsx', '.xls'))]
        for excel_file in excel_files:
            file_path = os.path.join(input_file_path, excel_file)
            content = []
            df = pd.read_excel(file_path, sheet_name=0)
            for index, row in df.iterrows():
                content.append({'tasks': row['任务'], 'instructions': row['Sop'], 'img': row['Image Path'], 'order': row['执行指令']})
            if 'jd_buy_filter' in file_path:
                res_dict['jd_buy_filter'] = content
            elif 'jd_food_filter' in file_path:
                res_dict['jd_food_filter'] = content
            elif 'mt_food_filter' in file_path:
                res_dict['mt_food_filter'] = content
            elif 'tb_buy_filter' in file_path:
                res_dict['tb_buy_filter'] = content
            elif 'tb_food_filter' in file_path:
                res_dict['tb_food_filter'] = content
            elif 'xc_out_filter' in file_path:
                res_dict['xc_out_filter'] = content
            elif 'ads' in file_path:
                res_dict['ads'] = content
            elif 'call_user' in file_path:
                res_dict['call_user'] = content
            elif 'dd_gd_out' in file_path:
                res_dict['dd_gd_out'] = content
            elif 'jd_buy' in file_path:
                res_dict['jd_buy'] = content
            elif 'jd_food' in file_path:
                res_dict['jd_food'] = content
            elif 'mt_food' in file_path:
                res_dict['mt_food'] = content
            elif 'tb_buy' in file_path:
                res_dict['tb_buy'] = content
            elif 'tb_food' in file_path:
                res_dict['tb_food'] = content
            elif 'xc_out' in file_path:
                res_dict['xc_out'] = content
        try:
            with open('eval/benchmarks/aisf_release/result.csv', 'w+', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(['任务', '指令', '图片位置', '参考答案', '模型输出', '结果'])
        except:
            with open('backend/CCNRuler2EvalScope/eval/benchmarks/aisf_release/result.csv', 'w+', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(['任务', '指令', '图片位置', '参考答案', '模型输出', '结果'])
        return res_dict

    def gen_prompt(self, input_d: dict, few_shot_list: list, **kwargs) -> dict:
        """
        Generate the prompt for the model input.
        """
        base_dir = self.input_path
        file_path = input_d['img'].replace('\\', '/')
        img_path = os.path.join(base_dir, file_path)
        img_path = img_path.replace('\n', '')
        width, height = Image.open(img_path).size
        new_height, new_width = smart_resize(height, width)
        with open(img_path, mode='rb') as infile:
            img_str = base64.b64encode(infile.read()).decode()
        instruction = input_d['instructions']
        full_prompt = [{'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{img_str}'}}, {'type': 'text', 'text': USR_PROMPT + instruction}]
        sysprompt = SYS_PROMPT % (new_width, new_height)
        system_prompt = [{'type': 'text', 'text': sysprompt}]
        return self.gen_prompt_data(full_prompt, system_prompt=system_prompt)

    def get_gold_answer(self, input_d: dict) -> str:
        gold_answer = input_d['order']
        return gold_answer

    def parse_pred_result(self, result: str, raw_input_d: dict=None, eval_type: str='checkpoint') -> str:
        """
        Parse the model output to get the answer. Could be the best choice index.
        """
        return result

    def match(self, gold: str, pred: str, raw_input_d: str, subset_name) -> float:
        resp_type = {'num': 2, 'regex': '(\\d+), *(\\d+)', 'isMillile': False, 'resize': True}
        base_dir = self.input_path
        res = process_results(gold, pred, raw_input_d, resp_type, base_dir)
        new_rows = [raw_input_d['tasks'], raw_input_d['instructions'], raw_input_d['img'], raw_input_d['order'], pred, 'T' if res == 1 else 'F']
        try:
            with open('eval/benchmarks/aisf_release/result.csv', mode='a+', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(new_rows)
        except:
            with open('backend/CCNRuler2EvalScope/eval/benchmarks/aisf_release/result.csv', mode='a+', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(new_rows)
        return res

    def compute_metric(self, review_res_list: List[dict], **kwargs) -> Any:
        res_dict = super().compute_dict_metric(review_res_list, **kwargs)
        return super().compute_metric(res_dict, **kwargs)
