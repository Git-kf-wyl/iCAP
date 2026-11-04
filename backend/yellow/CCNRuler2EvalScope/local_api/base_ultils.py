# Private iCAP Yellow implementation. Do not publish.
import os
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice, CompletionUsage
from local_api.model_lib.qwen_lib import qwen_qwq_32b
from local_api.model_lib.qwen_lib import qwen3_30b_a3b
from local_api.model_lib.qwen_lib import qwen3_32b
from local_api.model_lib.qwen_lib import qwen3_30b_a3b_zs
from local_api.model_lib.qwen_lib import qwen3_32b_zs
from local_api.model_lib.qwen_lib import qwen3_8b_zs
from local_api.model_lib.qwen_lib import qwen34b
from local_api.model_lib.qwen_lib import pangu

def split_response(full_content):
    """
        从模型回答中提取并移除 <思考过程>...</思考过程> 和 <think>... 部分。

        参数:
            text (str): 模型输出的原始文本

        返回:
            tuple: (思考过程合并文本, 清理后文本)
        """
    thinking_process_str = ''
    if '<思考过程>' in full_content:
        thinking_process_str = full_content.split('<思考过程>')[1].strip()
        cleaned_text = full_content.split('<思考过程>')[-1].strip()
    elif '</think>' in full_content:
        thinking_process_str = full_content.split('</think>')[1].strip()
        cleaned_text = full_content.split('</think>')[-1].strip()
    else:
        cleaned_text = full_content.strip()
    return (thinking_process_str, cleaned_text)

def get_non_openai_response(model_name, query):
    os.environ['HTTP_PROXY'] = ''
    os.environ['HTTPS_PROXY'] = ''
    print('=== ruler ===')
    full_content = ''
    model_function = globals().get(model_name)
    if callable(model_function):
        full_content = model_function(query)
    else:
        raise ValueError(f"Model '{model_name}' not found or is not callable.1111")
    reasoning_content, content = split_response(full_content)
    return ChatCompletion(id='0', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content=content, refusal=None, role='assistant', annotations=None, audio=None, reasoning_content=reasoning_content, model_extra={'reasoning_content': reasoning_content}, function_call=None, tool_calls=None))], created=0, model=model_name, object='chat.completion', usage=CompletionUsage(completion_tokens=5, prompt_tokens=21, total_tokens=26, completion_tokens_details=None, prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=21))
