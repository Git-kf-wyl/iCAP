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
logger = get_logger()

class VLAAdapter(ServerModelAdapter):
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
            query = data
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
        request_json = {'model': self.model_id, 'messages': content, **infer_cfg}
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
