# Private iCAP Yellow implementation. Do not publish.
import openai
from inspect import signature
from typing import List, Optional
from eval.models.server_adapter import ServerModelAdapter
from eval.utils.logger import get_logger
import httpx
import concurrent.futures
import copy
from collections import defaultdict
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice, CompletionUsage
import time
import os
from non_openai_api.base_ultils import get_non_openai_response
from eval.benchmarks.aisf_release.tools import TOOLS
from qwen_agent.llm import get_chat_model
logger = get_logger()

class AISFFunctionCallAdapter(ServerModelAdapter):
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
        super().__init__(api_url=api_url, model_id=model_id, api_key=api_key, **kwargs)

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
        data: list = input_item['data']
        if isinstance(data[0], tuple):
            query = '\n'.join((''.join(item) for item in data))
            system_prompt = input_item.get('system_prompt', None)
        else:
            query = data[0]
            system_prompt = input_item.get('system_prompt', None)
        content = self.make_request_content(query, system_prompt)
        request_json = self.make_request(content, infer_cfg)
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

    def make_request(self, content: list, infer_cfg: dict={}) -> dict:
        """Make request to remote API."""
        from eval.config import DEFAULT_GENERATION_CONFIG
        if infer_cfg == DEFAULT_GENERATION_CONFIG:
            infer_cfg = {'max_tokens': 2048, 'temperature': 0.0}
        request_json = {'model': self.model_id, 'messages': content, 'functions': TOOLS, **infer_cfg}
        if self.timeout:
            request_json['timeout'] = self.timeout
        if self.stream:
            request_json['stream'] = self.stream
            request_json['stream_options'] = {'include_usage': True}
        logger.debug(f'Request to remote API: {request_json}')
        return request_json

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
        """处理单个API请求的辅助函数"""
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
                        response = self._collect_stream_response(response)
                    return (response, time.time() - start)
                model_name = single_request.get('model', None)
                if model_name == None:
                    raise KeyError('未找到model, 请设置model!!!')
                llm = get_chat_model({'model': model_name, 'model_server': self.api_url, 'api_key': self.api_key})
                extra_generate_cfg = {'presence_penalty': 0, 'seed': 1, 'temperature': 0.1, 'top_p': 0.1}
                result = llm.chat(messages=single_request['messages'], functions=single_request['functions'], stream=self.stream, extra_generate_cfg=extra_generate_cfg)
                content = result[1]['function_call']
                response = ChatCompletion(id='0', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content=f'{content}', refusal=None, role='assistant', annotations=None, audio=None, model_extra={'reasoning_content': ''}, function_call=None, tool_calls=None))], created=0, model=model_name, object='chat.completion', usage=CompletionUsage(completion_tokens=5, prompt_tokens=21, total_tokens=26, completion_tokens_details=None, prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=21))
                if response and self.stream:
                    response = self._collect_stream_response(response)
                model_pool.reset_error_count(model)
                return (response, time.time() - start)
            except Exception as e:
                if not kwargs.get('llmjudge', False):
                    model_pool.increment_error_count(model)
                if retry == (max_retries if request_retry else 0):
                    logger.error(f'任务执行失败, 失败信息: {str(e)} \n')
                    return (ChatCompletion(id='0', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content='', refusal=None, role='assistant', annotations=None, audio=None, model_extra={'reasoning_content': ''}, function_call=None, tool_calls=None))], created=0, model='ds', object='chat.completion', usage=CompletionUsage(completion_tokens=5, prompt_tokens=21, total_tokens=26, completion_tokens_details=None, prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=21)), time.time() - start)
                logger.error(f'与服务器第{retry + 1}次链接失败: {(str(e),)}，2s后重试...', exc_info=True)
                time.sleep(2)
