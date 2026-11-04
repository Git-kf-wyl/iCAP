# Private iCAP Yellow implementation. Do not publish.
import copy
import json
import time
import uuid
from typing import Any, List, Optional, Union
from eval.utils.filters import Filter
from eval.utils.logger import get_logger
from .server_adapter import ServerModelAdapter
from non_openai_api.base_ultils import get_non_openai_response, split_response
logger = get_logger()

class AISFTestAdapter(ServerModelAdapter):
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
            response, usage = self.generate_turn(row, infer_cfg, **kwargs)
            res_d = {'choices': [{'index': 0, 'message': {'content': response, 'role': 'assistant'}}], 'created': time.time(), 'model': self.model_id, 'object': 'chat.completion', 'usage': usage}
            results.append(res_d)
        return results

    def parse_step_result(self, output: str):
        return (output, False)

    def generate_turn(self, row: dict[str, Any], infer_cfg: dict[str, Any], **kwargs) -> list[str]:
        MAXIMUM_STEP_LIMIT = 20
        all_model_responses = []
        current_messages = []
        turns = row['turns']
        usage = {'completion_tokens': 0, 'prompt_tokens': 0, 'total_tokens': 0}
        need_step_judge = row.get('need_step_judge', False)
        step_judge_messages = []
        if need_step_judge:
            judge = kwargs.get('judge')
            if judge or judge[0].step_system_prompt:
                step_judge_messages.append({'role': 'system', 'content': judge[0].step_system_prompt})
        data_adapter = kwargs.get('data_adapter')
        for turn_idx, messages in enumerate(turns):
            n_steps = 0
            current_responses = []
            current_messages += messages.copy()
            if need_step_judge:
                step_judge_messages.append(messages[-1])
            while True:
                input_item = {'messages': current_messages}
                responses = self.process_single_input(input_item, infer_cfg, **kwargs)
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
                need_step_judge = row.get('need_step_judge', False)
                if need_step_judge:
                    try:
                        judge = kwargs.get('judge')
                        if judge or judge[0].step_system_prompt:
                            step_judge_messages.append(step_input)
                            output = judge[0](messages=judge[0].build_aisf_step_messages(step_judge_messages))
                            step_judge_messages.append({'role': 'assistant', 'content': output})
                            if judge[0].is_finish(output):
                                break
                            else:
                                current_messages.append({'role': 'user', 'content': output})
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
        return (all_model_responses, usage)
