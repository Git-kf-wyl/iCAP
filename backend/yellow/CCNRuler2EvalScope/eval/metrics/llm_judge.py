# Private iCAP Yellow implementation. Do not publish.
import os
import re
from typing import Any, Dict, List, Optional
from eval.utils.logger import get_logger
logger = get_logger()
DEFAULT_PROMPT_TEMPLATE = 'Your job is to look at a question, a gold target, and a predicted answer, and return a letter "A" or "B" to indicate whether the predicted answer is correct or incorrect.\n\nQuestion: {question}\n\nReference Answer: {gold}\n\nModel Answer: {pred}\n\nEvaluate the model\'s answer based on correctness compared to the reference answer.\nGrade the predicted answer of this new question as one of:\nA: CORRECT\nB: INCORRECT\n\nJust return the letters "A" or "B", with no text around it.\n'

class LLMJudge:
    """
    A metric that uses LLM to judge the quality of model predictions by comparing them with reference answers.
    """

    def __init__(self, api_key: Optional[str]=None, api_url: Optional[str]=None, model_id: Optional[str]=None, system_prompt: Optional[str]=None, prompt_template: Optional[str]=None, generation_config: Optional[Dict[str, Any]]=None, **kwargs):
        """
        Initialize LLMJudge metric.

        Args:
            api_key (str, optional): API key for OpenAI or compatible service
            api_base (str, optional): API base URL
            model_id (str, optional): Model ID for LLM
            system_prompt (str, optional): System prompt for the judge
            prompt_template (str, optional): Prompt template for the judge
            generation_config (dict, optional): Generation configuration for the judge
        """
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY', 'EMPTY')
        self.api_url = api_url or os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
        self.model_id = model_id or os.environ.get('LOCAL_LLM', 'gpt-4')
        self.system_prompt = system_prompt or os.environ.get('JUDGE_SYSTEM_PROMPT', None)
        self.prompt_template = prompt_template or os.environ.get('JUDGE_PROMPT_TEMPLATE', DEFAULT_PROMPT_TEMPLATE)
        self.generation_config = generation_config
        self.step_system_prompt = kwargs.get('step_system_prompt', '')
        self.step_prompt_template = kwargs.get('step_prompt_template', '')
        from eval.models.server_adapter import ServerModelAdapter
        self.server_adapter = ServerModelAdapter(api_url=self.api_url, model_id=self.model_id, api_key=self.api_key)

    def __call__(self, prompt: str='', system_prompt: Optional[str]='', **kwargs) -> Any:
        """
        Args:
            prompt (str): The prompt to evaluate
            system_prompt (str, optional): The system prompt to use for the evaluation
        Returns:
            float: The score of the evaluation
        """
        input_data = {'data': [prompt], 'system_prompt': system_prompt or self.system_prompt, 'index': 0}
        if self.step_system_prompt and kwargs.get('messages'):
            input_data['messages'] = kwargs['messages']
        infer_cfg = {'temperature': 0.0, 'max_tokens': 1024}
        if self.generation_config:
            infer_cfg.update(self.generation_config)
        try:
            kwargs['llmjudge'] = True
            response = self.server_adapter.process_single_input(input_data, infer_cfg, **kwargs)
            llm_response = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            return llm_response
        except Exception as e:
            logger.error(f'Error during LLM evaluation: {e}')
            return None

    def build_prompt(self, pred: str, gold: str, question: Optional[str]=None):
        if question is None:
            question = 'Not provided'
        return self.prompt_template.format(question=question, pred=pred, gold=gold)

    def is_finish(self, output: str) -> bool:
        if output is None:
            return False
        if '已完成' in output:
            return True
        else:
            return False

    def build_aisf_step_messages(self, messages: List[dict]):
        messages.append({'role': 'user', 'content': self.step_prompt_template})
        return messages

    def build_aisf_final_message(self, pred: str, question: Optional[str]=None):
        return self.prompt_template.format(question=question, pred=pred)

    def get_score(self, response: str) -> float:
        if response is None:
            return 0
        match = re.search('(A|B)', response)
        if match:
            answer = match.group(0)
            if answer == 'A':
                return 1
            elif answer == 'B':
                return 0
        else:
            return 0
