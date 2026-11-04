# Private iCAP Yellow implementation. Do not publish.
import os
from ...smp import load_env
INTERNAL = os.environ.get('INTERNAL', 0)

def build_judge(**kwargs):
    from ...api import OpenAIWrapper, SiliconFlowAPI, HFChatModel
    model = kwargs.pop('model', None)
    kwargs.pop('nproc', None)
    load_env()
    LOCAL_LLM = os.environ.get('LOCAL_LLM', None)
    if LOCAL_LLM is None:
        model_map = {'gpt-4-turbo': 'gpt-4-1106-preview', 'gpt-4-0613': 'gpt-4-0613', 'gpt-4-0125': 'gpt-4-0125-preview', 'gpt-4-0409': 'gpt-4-turbo-2024-04-09', 'chatgpt-1106': 'gpt-3.5-turbo-1106', 'chatgpt-0125': 'gpt-3.5-turbo-0125', 'gpt-4o': 'gpt-4o-2024-05-13', 'gpt-4o-0806': 'gpt-4o-2024-08-06', 'gpt-4o-mini': 'gpt-4o-mini-2024-07-18', 'qwen-7b': 'Qwen/Qwen2.5-7B-Instruct', 'qwen-72b': 'Qwen/Qwen2.5-72B-Instruct', 'deepseek': 'deepseek-ai/DeepSeek-V2.5', 'llama31-8b': 'meta-llama/Llama-3.1-8B-Instruct'}
        model_version = model_map[model]
    else:
        model_version = LOCAL_LLM
    if model in ['qwen-7b', 'qwen-72b', 'deepseek']:
        model = SiliconFlowAPI(model_version, **kwargs)
    elif model == 'llama31-8b':
        model = HFChatModel(model_version, **kwargs)
    else:
        model = OpenAIWrapper(model_version, **kwargs)
    return model
DEBUG_MESSAGE = "\nTo debug the OpenAI API, you can try the following scripts in python:\n```python\nfrom vlmeval.api import OpenAIWrapper\nmodel = OpenAIWrapper('gpt-4o', verbose=True)\nmsgs = [dict(type='text', value='Hello!')]\ncode, answer, resp = model.generate_inner(msgs)\nprint(code, answer, resp)\n```\nYou cam see the specific error if the API call fails.\n"
