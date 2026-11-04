# Private iCAP Yellow implementation. Do not publish.
import openai
from inspect import signature
from typing import List, Optional
from .base_adapter import BaseModelAdapter
from evalscope.utils.logger import get_logger
import httpx
import concurrent.futures
import copy
from collections import defaultdict
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice, CompletionUsage
import time
import os
import sys
try:
    from CCNRuler1EvalScope.non_openai_api.base_ultils import get_non_openai_response, get_modelarts_response
except:
    from non_openai_api.base_ultils import get_non_openai_response, get_modelarts_response
logger = get_logger()

class ServerModelAdapter(BaseModelAdapter):
    """
    Server model adapter to request remote API model and generate results.
    """

    def __init__(self, api_url: str, model_id: str, api_key: str='EMPTY', **kwargs):
        """
        Args:
            api_url: The URL of the remote API model.
            model_id: The ID of the remote API model.
            api_key: The API key of the remote API model.
        """
        self.api_url = api_url.rstrip('/').rsplit('/chat/completions', 1)[0]
        self.model_id = model_id
        self.api_key = api_key
        if self.api_key == 'EMPTY':
            transport = httpx.HTTPTransport(retries=3, verify=True)
        else:
            transport = httpx.HTTPTransport(retries=3, verify=True)
        http_client = httpx.Client(transport=transport, timeout=3000)
        self.client = openai.OpenAI(api_key=api_key, base_url=self.api_url, http_client=http_client)
        self.supported_params = self._get_supported_params()
        self.seed = kwargs.get('seed', None)
        self.timeout = kwargs.get('timeout', 60)
        self.stream = kwargs.get('stream', False)
        self.non_openai_format = kwargs.get('non_openai_format', False)
        self.model_cfg = {'api_url': api_url, 'model_id': model_id, 'api_key': api_key}
        super().__init__(model=None, model_cfg=self.model_cfg, **kwargs)

    def _get_supported_params(self):
        sig = signature(self.client.chat.completions.create)
        return list(sig.parameters.keys())

    def predict(self, inputs: List[dict], infer_cfg: dict=None, **kwargs) -> List[dict]:
        """
        Model prediction func.

        Args:
            inputs (List[dict]): The input data.
            infer_cfg (dict): Inference configuration.

        Returns:
            res (List[dict]): The model prediction results.
        """
        infer_cfg = infer_cfg or {}
        results = []
        for input_item in inputs:
            response = self.process_single_input(input_item, infer_cfg, **kwargs)
            results.append(response)
        return results

    def process_single_input(self, input_item: dict, infer_cfg: dict, **kwargs) -> dict:
        """Process a single input item."""
        request_json = self.make_request(input_item, infer_cfg)
        response = self.send_request(request_json, **kwargs)
        return response

    def make_request_content(self, query: str, system_prompt: Optional[str]=None) -> list:
        """
        Make request content for OpenAI API.
        """
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': query})
        return messages

    def make_request_messages(self, input_item: dict) -> list:
        """
        Make request messages for OpenAI API.
        """
        ministral_system_prompt = {'role': 'system', 'content': [{'type': 'text', 'text': '# HOW YOU SHOULD THINK AND ANSWER\n\nFirst draft your thinking process (inner monologue) until you arrive at a response. Format your response using Markdown, and use LaTeX for any mathematical equations. Write both your thoughts and the response in the same language as the input.\n\nYour thinking process must follow the template below:'}, {'type': 'thinking', 'thinking': 'Your thoughts or/and draft, like working through an exercise on scratch paper. Be as casual and as long as you want until you are confident to generate the response to the user.', 'closed': True}, {'type': 'text', 'text': 'Here, provide a self-contained response.'}]}
        if input_item.get('messages', None):
            if 'ministral' in self.model_id.lower():
                input_item['messages'].insert(0, ministral_system_prompt)
            return input_item['messages']
        data: list = input_item['data']
        if isinstance(data[0], tuple):
            query = '\n'.join((''.join(item) for item in data))
            system_prompt = input_item.get('system_prompt', None)
        else:
            query = data[0]
            system_prompt = input_item.get('system_prompt', None)
        messages = []
        if 'ministral' in self.model_id.lower():
            messages.append(ministral_system_prompt)
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': query})
        return messages

    def make_request(self, input_item: dict, infer_cfg: dict) -> dict:
        """Make request to remote API."""
        messages = self.make_request_messages(input_item)
        request_json = {'model': self.model_id, 'messages': messages, **infer_cfg}
        if self.timeout:
            request_json['timeout'] = self.timeout
        if self.model_id.startswith('gemma'):
            request_json['chat_template_kwargs'] = {'enable_thinking': True}
        request_json['stream'] = self.stream
        if self.stream:
            request_json['stream_options'] = {'include_usage': True}
        if input_item.get('tools', None):
            tools_copy = copy.deepcopy(input_item.get('tools'))
            for tool in tools_copy:
                if 'function' in tool and 'response' in tool['function']:
                    del tool['function']['response']
            request_json['tools'] = tools_copy
        logger.debug(f'Request to remote API: {request_json}')
        return request_json

    def create_default_chat_completion(self):
        return ChatCompletion(id='0', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content='', refusal=None, role='assistant', annotations=None, audio=None, model_extra={'reasoning_content': ''}, function_call=None, tool_calls=None))], created=0, model='ds', object='chat.completion', usage=CompletionUsage(completion_tokens=0, prompt_tokens=0, total_tokens=0, completion_tokens_details=None, prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=0))

    def _parse_extra_params(self, request_json):
        api_params = {}
        extra_body = {}
        for key, value in request_json.items():
            if key in self.supported_params:
                api_params[key] = value
            else:
                extra_body[key] = value
        if extra_body:
            api_params['extra_body'] = extra_body
        return api_params

    def _process_single_request(self, parsed_request: dict, **kwargs):
        """
        处理单个API请求的辅助函数，非openai格式请求

        Author: {} ,w60034501
        Date: 2025-05
        """
        single_request = copy.deepcopy(parsed_request)
        max_retries = 1
        task_config = kwargs.get('task_config')
        model_pool = kwargs.get('model_pool')
        model = kwargs.get('model')
        request_retry = False
        if task_config:
            request_retry = task_config.request_retry
        for retry in range(max_retries + 1 if request_retry else 1):
            start = time.time()
            try:
                if kwargs.get('llmjudge', False):
                    response = self.client.chat.completions.create(**single_request)
                    if response and self.stream:
                        response = self.client.chat.completions.create(**single_request)
                    return (response, time.time() - start)
                model_name = single_request.get('model', None)
                if model_name == None:
                    raise KeyError('未找到model, 请设置model!!!')
                if self.non_openai_format:
                    response = get_non_openai_response(self.model_cfg['api_url'], model_name, single_request.get('messages'))
                elif 'api.modelarts-maas.com' in self.model_cfg['api_url']:
                    response = get_modelarts_response(self.model_cfg, single_request)
                else:
                    response = self.client.chat.completions.create(**single_request)
                if response and self.stream:
                    response = self._collect_stream_response(response)
                model_pool.reset_error_count(model)
                return (response, time.time() - start)
            except ConnectionError or ConnectionResetError or ConnectionAbortedError or ConnectionRefusedError as e:
                logger.error(f'模型连接失败: {str(e)} \n')
                if not kwargs.get('llmjudge', False):
                    model_pool.increment_error_count(model)
                if retry == (max_retries if request_retry else 0):
                    logger.error(f'任务执行失败, 失败信息: {str(e)} \n')
                    return (self.create_default_chat_completion(), time.time() - start)
                logger.error(f'与服务器第{retry + 1}次链接失败: {(str(e),)}，2s后重试...', exc_info=True)
                time.sleep(2)
            except Exception as e:
                if not kwargs.get('llmjudge', False) and 'Error code' in str(e):
                    model_pool.increment_error_count(model)
                if retry == (max_retries if request_retry else 0):
                    logger.error(f'任务执行失败, 失败信息: {str(e)} \n')
                    return (self.create_default_chat_completion(), time.time() - start)
                logger.error(f'与服务器第{retry + 1}次连接失败: {(str(e),)}，2s后重试...', exc_info=True)
                time.sleep(2)

    def send_request(self, request_json: dict, **kwargs) -> dict:
        """
        发送请求，修改多个返回的时候

        Args:
            request_json (dict): 输入数据

        Returns:
            float: 计算后的成本

        Author: 赵六
        Date: 2023-10-05
        """
        try:
            parsed_request = self._parse_extra_params(request_json)
            if kwargs.get('llmjudge', False):
                request_nums = 1
            else:
                request_nums = request_json.get('request_nums', 1)
            all_choices = []
            base_response = None
            all_usage = CompletionUsage(completion_tokens=0, prompt_tokens=0, total_tokens=0, prompt_tokens_details=None)
            total_execution = 0
            model_pool = kwargs.get('model_pool')
            pool_adapters = self._get_model_pool_adapters(model_pool)
            if self not in pool_adapters:
                pool_adapters.append(self)
            for req_idx in range(request_nums):
                adapter = pool_adapters[req_idx % len(pool_adapters)]
                response, execution_time = self._make_request_to_model(adapter, parsed_request, **kwargs)
                if not base_response and response:
                    base_response = response
                if response and response.choices:
                    start_idx = len(all_choices)
                    for ch_idx, choice in enumerate(response.choices):
                        choice.index = start_idx + ch_idx
                    all_choices.extend(response.choices)
                if response and response.usage:
                    all_usage.prompt_tokens += response.usage.prompt_tokens if response.usage.prompt_tokens else 0
                    all_usage.completion_tokens += response.usage.completion_tokens if response.usage.completion_tokens else 0
                    all_usage.total_tokens += response.usage.total_tokens if response.usage.total_tokens else 0
                    all_usage.completion_tokens_details = response.usage.completion_tokens_details if response.usage.completion_tokens_details else None
                total_execution += execution_time
            if not base_response:
                raise ValueError('所有API请求均未返回有效响应')
            final_response = base_response.model_dump(exclude_unset=True)
            final_response['choices'] = [choice.model_dump() for choice in all_choices]
            final_response['usage'] = all_usage.model_dump()
            final_response['response_time'] = total_execution
            final_response['parsed_request'] = parsed_request
            return final_response
        except Exception as e:
            logger.error(f'API调用失败: {str(e)}', exc_info=True)
            raise

    def _collect_stream_response(self, response_stream: List[ChatCompletionChunk]) -> ChatCompletion:
        try:
            collected_chunks = []
            collected_messages = defaultdict(list)
            collected_reasoning = defaultdict(list)
            for chunk in response_stream:
                collected_chunks.append(chunk)
                for choice in chunk.choices:
                    if hasattr(choice.delta, 'reasoning_content') and choice.delta.reasoning_content is not None:
                        collected_reasoning[choice.index].append(choice.delta.reasoning_content)
                    if choice.delta.content is not None:
                        collected_messages[choice.index].append(choice.delta.content)
            choices = []
            for index, messages in collected_messages.items():
                full_reply_content = ''.join(messages)
                reasoning = ''.join(collected_reasoning[index])
                finish_reason = None
                for chunk in reversed(collected_chunks):
                    if chunk.choices and chunk.choices[0].index == index:
                        finish_reason = chunk.choices[0].finish_reason
                        break
                choice = Choice(finish_reason=finish_reason or 'stop', index=index, message=ChatCompletionMessage(role='assistant', content=full_reply_content, reasoning_content=reasoning))
                choices.append(choice)
            return ChatCompletion(id=collected_chunks[0].id, choices=choices, created=collected_chunks[0].created, model=collected_chunks[0].model, object='chat.completion', usage=collected_chunks[-1].usage)
        except Exception as e:
            logger.error(f'流式传输调用失败: {str(e)}', exc_info=True)
            return ChatCompletion(id='0', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content='', refusal=None, role='assistant', annotations=None, audio=None, function_call=None, tool_calls=None))], created=0, model='ds', object='chat.completion', usage=CompletionUsage(completion_tokens=5, prompt_tokens=21, total_tokens=26, completion_tokens_details=None, prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=21))
