# Private iCAP Yellow implementation. Do not publish.
import copy
import json
import re
import time
import uuid
from typing import Any, List, Optional, Union
from eval.utils.filters import Filter
from eval.utils.logger import get_logger
from .server_adapter import ServerModelAdapter
from non_openai_api.base_ultils import get_non_openai_response, split_response
logger = get_logger()

class AISFClarifyModelAdapter(ServerModelAdapter):
    """
    BFCL model adapter to request remote API model and generate results for BFCL evaluation.
    Support multi-turn and single-turn function calling tasks.
    """

    def __init__(self, api_url: str, model_id: str, api_key: str='EMPTY', **kwargs):
        """
        Args:
            api_url: The URL of the remote API model.
            model_id: The ID of the remote API model.
            api_key: The API key of the remote API model.
        """
        super().__init__(api_url=api_url, model_id=model_id, api_key=api_key, **kwargs)

    def predict(self, inputs: List[dict], infer_cfg: Optional[dict]=None, **kwargs) -> List[dict]:
        """
        Model prediction func. For multi-turn evals, we pass a list[list[message]] to the model
        where each list is a follow up turn in the conversation
        each turn is a List[List[Message]]

        Args:
            inputs (List[dict]): The input data.
            infer_cfg (dict): Inference configuration.

        Returns:
            res (List[dict]): The model prediction results.
        """
        infer_cfg = infer_cfg or {}
        results = []
        for input_item in inputs:
            row = input_item.get('messages')
            response, usage, execution_time, current_messages, source_response = self.generate_turn(row, infer_cfg, **kwargs)
            res_d = {'choices': [{'index': 0, 'message': {'content': response, 'role': 'assistant'}}], 'created': time.time(), 'model': self.model_id, 'object': 'chat.completion', 'usage': {k: round(v / len(response if response else 1), 0) for k, v in usage.items()}, 'response_time': round(execution_time / len(response if response else 1), 6), 'current_messages': current_messages, 'source_response': source_response}
            results.append(res_d)
        return results

    def parse_step_result(self, output: str):
        return (output, False)

    def generate_turn(self, row: dict[str, Any], infer_cfg: dict[str, Any], **kwargs):
        MAXIMUM_STEP_LIMIT = 20
        all_model_responses = []
        current_messages = []
        source_response = []
        turns = row['turns']
        usage = {'completion_tokens': 0, 'prompt_tokens': 0, 'total_tokens': 0}
        pattern = re.compile('^(?:(?:<think>)?(?P<think>.*)</think>)?[^\\{]*(?P<result>\\{.*\\})[^\\}]*$', flags=re.DOTALL)
        need_step_judge = row.get('need_step_judge', False)
        lastAnswer = ''
        judgeInput = []
        is_used_addition_input = False
        step_judge_messages = []
        if need_step_judge:
            hisQuery = [row['Input']]
            hisClarify = []
            hisClarify.append('用户输入:' + row['Input'])
            judge = kwargs.get('judge')
            if judge or judge[0].step_system_prompt:
                step_judge_messages.append({'role': 'system', 'content': judge[0].step_system_prompt})
        data_adapter = kwargs.get('data_adapter')
        finished = False
        start = time.time()
        for turn_idx, messages in enumerate(turns):
            if finished:
                break
            n_steps = 0
            current_responses = []
            current_messages += messages.copy()
            if need_step_judge:
                step_judge_messages.append(messages[-1])
            while True:
                input_item = {'messages': current_messages}
                responses = self.process_single_input(input_item, infer_cfg, **kwargs)
                source_response.append(responses['choices'][0]['message']['content'])
                filters = data_adapter.config_kwargs.get('filters', None)
                if filters:
                    result = ''
                    for filter_name, filter_value in filters.items():
                        result = Filter.apply(filter_name, responses['choices'][0]['message']['content'], filter_value).strip('\n')
                else:
                    result = responses['choices'][0]['message']['content']
                usage['completion_tokens'] += responses['usage']['completion_tokens'] if responses['usage']['completion_tokens'] else 0
                usage['prompt_tokens'] += responses['usage']['prompt_tokens'] if responses['usage']['prompt_tokens'] else 0
                usage['total_tokens'] += responses['usage']['total_tokens'] if responses['usage']['total_tokens'] else 0
                logger.debug(f'Turn:{turn_idx} Step:{n_steps} Result: {result}')
                step_input = {'role': 'assistant', 'content': result}
                current_messages.append(step_input)
                current_responses.append(result)
                match = pattern.match(result)
                if not match or not match.groupdict():
                    finished = True
                else:
                    content = json.loads(match.groupdict().get('result', '{}'))
                    if content.get('澄清状态', '') == '完成' or content.get('Type', '') == 'result':
                        finished = True
                need_step_judge = row.get('need_step_judge', False)
                if need_step_judge:
                    try:
                        try:
                            clarifyResult = self.getClarifyAnswer(result)
                        except Exception as e:
                            clarifyResult = {'Desc': '', 'Type': 'result', 'Data': '模型回答出错'}
                            clarifyResult = json.dumps(clarifyResult, ensure_ascii=False)
                        finally:
                            question_for_judge = json.loads(clarifyResult)['Desc']
                        if json.loads(clarifyResult)['Type'] == 'result':
                            if row['step_system_prompt_2'] != '':
                                try:
                                    test_prompt = row['step_system_prompt_2'].replace('{0}', str(hisClarify))
                                    judgeInput2 = [{'role': 'system', 'content': test_prompt}, {'role': 'user', 'content': '\n<用户输入>\n' + str(json.loads(clarifyResult)['Data'])}]
                                    judge = kwargs.get('judge')
                                    if judge:
                                        output = judge[0](messages=judgeInput2)
                                        output = self.parse_think_response_clean(output)
                                        isSatisfied = self.getIsSatisfied(output)
                                except (KeyError, ValueError, IndexError) as e:
                                    isSatisfied = {'满意度': '不满意', '评测依据': '模型回答失败!'}
                                    isSatisfied = json.dumps(isSatisfied, ensure_ascii=False)
                                if json.loads(isSatisfied)['满意度'] == '非常满意':
                                    return ('1', usage, time.time() - start, current_messages, source_response)
                                return ('0', usage, time.time() - start, current_messages, source_response)
                            else:
                                return (str(json.loads(clarifyResult)['Data']), usage, time.time() - start, current_messages, source_response)
                        judge = kwargs.get('judge')
                        if judge or judge[0].step_system_prompt:
                            if not len(lastAnswer):
                                judgeInput.append({'role': 'system', 'content': row['step_system_prompt']})
                                judgeInput.append({'role': 'user', 'content': '\n<历史对话>\n' + str(hisQuery) + '\n <本次输入>\n' + question_for_judge})
                            else:
                                judgeInput.append({'role': 'assistant', 'content': lastAnswer})
                                judgeInput.append({'role': 'user', 'content': question_for_judge})
                            output = judge[0](messages=judgeInput)
                            output = self.parse_think_response_clean(output)
                            step_judge_messages.append({'role': 'assistant', 'content': output})
                            lastAnswer = output
                            try:
                                result = self.getAnswer(output)
                                hisQuery.append(question_for_judge)
                                hisQuery.append(json.loads(result)['问答回应'])
                            except Exception as e:
                                result = {'问答回应': '模型回答失败!'}
                                result = json.dumps(result, ensure_ascii=False)
                                return (str(result), usage, time.time() - start, current_messages, source_response)
                            finally:
                                if 'Addition input' in row:
                                    if not is_used_addition_input:
                                        question_for_clarify = json.loads(result)['问答回应'] + '，算了' + row['Addition input']
                                        is_used_addition_input = True
                                    else:
                                        question_for_clarify = json.loads(result)['问答回应']
                                else:
                                    question_for_clarify = json.loads(result)['问答回应']
                                hisClarify.append('澄清问题:' + question_for_judge)
                                hisClarify.append('问答回应:' + question_for_clarify)
                            if judge[0].is_finish(output):
                                break
                            else:
                                current_messages.append({'role': 'user', 'content': question_for_clarify + '\n\n/nothink'})
                        else:
                            raise Exception('No judge provided, please setup tep_system_prompt')
                    except Exception:
                        output = None
                    if output is None:
                        break
                else:
                    break
                n_steps += 1
                if n_steps > MAXIMUM_STEP_LIMIT:
                    logger.error(f'INFERENCE_ERROR: Exceeded max inference steps ({MAXIMUM_STEP_LIMIT})')
                    break
            all_model_responses.append(current_responses)
        return (all_model_responses, usage, time.time() - start, current_messages, source_response)

    def getClarifyAnswer(self, data):
        data = data.replace('```', '')
        data = data.replace('json', '')
        try:
            res = json.loads(data)
            status = res['Type']
            text = res['Data']
            question = res['Desc']
        except Exception as e:
            logger.error('被测模型返回结果' + data + '非标准JSON格式')
            status = 'result'
            text = ''
            question = '被测模型返回结果非标准JSON格式'
        result = {'Type': str(status), 'Data': str(text), 'Desc': str(question)}
        return json.dumps(result, ensure_ascii=False)

    def getAnswer(self, data):
        data = data.replace('```', '')
        data = data.replace('json', '')
        try:
            res = json.loads(data)
            Content = res['问答回应']
        except Exception as e:
            logger.error('问答助手返回结果' + data + '非标准JSON格式')
            Content = ''
        result = {'问答回应': str(Content)}
        return json.dumps(result, ensure_ascii=False)
        return result

    def extract_clean_text(self, text):
        """去除 HTML 标签并清理空白字符"""
        text = re.sub('<[^>]+>', '', text)
        text = re.sub('\\s+', ' ', text).strip()
        return text

    def parse_think_response_clean(self, message_body):
        """
        解析消息体，分割出 think 内容和回答内容（纯文本）
        返回: (think_content, answer_content)
              如果没有 </think>，则 think_content=None
        """
        parts = message_body.split('</think>', 1)
        if len(parts) == 2:
            answer_content = parts[1]
        else:
            answer_content = self.extract_clean_text(message_body)
        return answer_content

    def getIsSatisfied(self, data):
        data = data.replace('[', '')
        data = data.replace(']', '')
        try:
            res = json.loads(data)
            answer = res['满意度']
            content = res['评测依据']
        except Exception as e:
            logger.error('评判模型返回结果' + data + '非标准JSON格式')
            answer = ''
            content = '评判模型返回结果非标准JSON格式'
        result = {'满意度': str(answer), '评测依据': str(content)}
        return json.dumps(result, ensure_ascii=False)
