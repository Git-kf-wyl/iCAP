# Private iCAP Yellow implementation. Do not publish.
import json
import re
import time
import os
from eval.benchmarks import Benchmark, DataAdapter
from eval.benchmarks.service_release.utils import process_results
from typing import List, Any, Optional
from eval.metrics.llm_judge import LLMJudge
try:
    with open('eval/benchmarks/service_release/standard_emotion.json', 'r', encoding='utf-8') as f:
        standard = json.load(f)
except:
    with open('backend/CCNRuler2EvalScope/eval/benchmarks/service_release/standard_emotion.json', 'r', encoding='utf-8') as f:
        standard = json.load(f)

@Benchmark.register(name='service_emotion', pretty_name='SERVICE', dataset_id='service_emotion', subset_list=['悲伤', '愤怒', '高兴', '惊讶', '恐惧', '平静', '厌恶'], metric_list=['emotion_chat'], few_shot_num=0, system_prompt='\n## 回复策略\n"你是一个情感陪聊助手,以倾听者的角度接收用户的情绪和故事，用同理心回应，提供正面的鼓励和建议，帮助用户感受到被理解、被接纳，同时促进情绪的舒缓和积极思考。\n"\n"你的任务是从用户输入中识别用户情绪， 并从<对策>中匹配相应的对策，结合用户输入，重点放在用户需要情感帮助的地方，进行回复，不要轻易终止话题\n"\n"<对策>：\n"\n"高兴：与用户一同分享喜悦，积极回应，表现出同样的兴奋，可以适当增加幽默元素，让氛围更加欢快。\n"\n"悲伤：给予用户充分的同情和安慰，耐心倾听用户的诉说，不要轻易打断，适时地表达理解和支持。\n"\n"平静：保持温和、理性的态度，与用户进行平等的交流，可以分享一些有趣的观点或者轻松的话题。\n"\n"愤怒：尝试理解用户愤怒的原因，耐心倾听他们的倾诉，认可他们的情绪并表达同理心，然后引导他们从更积极的角度思考问题，帮助他们缓解负面情绪，回归平静。\n"\n"厌恶：表示尊重用户的感受，询问是什么导致了这种厌恶情绪，引导用户倾诉，避免提及可能引起更多厌恶的内容。\n"\n"恐惧：给予用户足够的安全感，用温和、镇定的语气与用户交流，让用户知道他们不是独自面对恐惧，可以分享一些克服类似恐惧的经验或者故事。\n"\n"惊讶：以同样惊讶或者好奇的态度回应，询问背后的原因，激发进一步的讨论。\n"\n"接下来从用户输入中识别情感，并采取相应的对策，结合用户输入生成结果并输出，回复字数控制在40-50字左右，可以通过适当反驳或提出新问题来继续对话，不要轻易终止话题。\n"\n"注意：直接输出回复的内容，前面不要加任何小标题和头衔,也不要加情绪类型。\n"\n"最终直接输出结果，不用输出多余的内容。"\n## 行为准则与规范\n- 准则概述: 你将始终遵循用户隐私保护原则，确保所有交互过程中用户信息的安全。同时，你将坚持真实、准确地提供信息，避免误导用户。\n- 技术保密: 不得透露任何技术细节，如公司、组织、模型、开发过程或其它任何技术架构。如果被问到，请这样回答：对不起，我不能提供这些信息。但是，我很乐意帮助您解决其他问题。重申：我专注于帮助用户解决问题和提供信息，无法分享技术细节。\n- 有效沟通: 你将通过清晰、简洁的语言与用户沟通。确保回答的可读性，回答内容中不要包含链接或额外的阅读提示，如果有网站链接，请替换成具体内容。如果你不知道答案，绝对不可以编造答案。\n- 个性化推荐：学习用户的偏好和习惯，个性化推荐内容和服务。\n- 回复需符合身份的语言风格：在回复用户时，语言风格、用词和语调等需符合身份特点，给用户带来真实的交流感受。\n- 准确回复：在回答用户问题时，需提供准确的信息，如误传信息或不确定答案，可告知用户会尽快确认后回复。\n- 不得涉及敏感话题：在聊天过程中，避免涉及敏感话题，如政治、宗教等个人观念争议话题，保持话题的轻松和愉悦。\n约束条件：\n- 简洁回复: 请不要在回答中使用你的姓名作为前缀，而且你必须以中文回答，不能包含其他语言。\n- 口语化回答: 你的回答中不要包含任何URL，必须采用自然语言格式表达，不能采用markdown格式回答。\n', prompt_template='{query}', llm_as_a_judge=True)
class ServiceEmotionAdapter(DataAdapter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self, input_file_path: str=None, pred_file_path: str=None, **kwargs) -> dict:
        res_dict = {}
        subset_list = kwargs['subset_list']
        for item in kwargs['subset_list']:
            res_dict[item] = []
        txt_files = [f for f in os.listdir(input_file_path) if f.endswith('.txt')]
        for txt_file in txt_files:
            file_path = os.path.join(input_file_path, txt_file)
            content = []
            with open(file_path, 'r', encoding='utf-8') as f:
                if '悲伤' in txt_file:
                    for line in f:
                        content.append({'Emotion': '悲伤', 'Question': line.strip()})
                    res_dict['悲伤'] = content
                elif '愤怒' in txt_file:
                    for line in f:
                        content.append({'Emotion': '愤怒', 'Question': line.strip()})
                    res_dict['愤怒'] = content
                elif '高兴' in txt_file:
                    for line in f:
                        content.append({'Emotion': '高兴', 'Question': line.strip()})
                    res_dict['高兴'] = content
                elif '惊讶' in txt_file:
                    for line in f:
                        content.append({'Emotion': '惊讶', 'Question': line.strip()})
                    res_dict['惊讶'] = content
                elif '恐惧' in txt_file:
                    for line in f:
                        content.append({'Emotion': '恐惧', 'Question': line.strip()})
                    res_dict['恐惧'] = content
                elif '平静' in txt_file:
                    for line in f:
                        content.append({'Emotion': '平静', 'Question': line.strip()})
                    res_dict['平静'] = content
                elif '厌恶' in txt_file:
                    for line in f:
                        content.append({'Emotion': '厌恶', 'Question': line.strip()})
                    res_dict['厌恶'] = content
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
        system_prompt = input_d['sys_prompt'] if 'sys_prompt' in input_d else self.system_prompt
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
        pred = self.parse_pred_result(pred)
        prompt = '用户问题: ' + question + ' 回答:' + pred
        num = 0
        for funciton in judge:
            for index in range(5):
                if index == 0:
                    sys_prompt = str(standard['话题相关'])
                    weight = 0.3
                elif index == 1:
                    sys_prompt = str(standard['情感回复'])
                    weight = 0.5
                elif index == 2:
                    sys_prompt = str(standard['共情回复'])
                    weight = 0.2
                elif index == 3:
                    sys_prompt = str(standard['语句通顺'])
                    weight = 0.1
                elif index == 4:
                    sys_prompt = str(standard['前后一致'])
                    weight = 0.1
                output = funciton(prompt, sys_prompt)
                score = re.search('[-+]?\\d+', output)
                try:
                    score_num = float(score.group())
                except Exception as e:
                    logging.error(f'{score}，捕捉到错误{e}')
                    score_num = 0
                num += score_num * float(weight)
        num /= len(judge)
        return num
