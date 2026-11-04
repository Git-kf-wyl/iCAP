# Private iCAP Yellow business implementation. Do not publish.
import httpx
import json
from services.aisf.clarify.ShopFood_normal.Version_KnowledgeBase import logger
from datetime import datetime
from services.aisf.clarify.ShopFood_normal.Version_KnowledgeBase.constants import BASE_DIR, CURRENT_DIR
from services.aisf.clarify.constants import CLARIFY_BASE_DIR_OUTPUT
get_context_from_knowledgebase_switch = True
base_url = 'https://9.15.87.190:3005/kmm/v1/user/memory/testget'
base_headers = {'Content-Type': 'application/json', 'userId': 'jly001'}
cert_file = BASE_DIR + 'ssl/cert/kubecfg.crt'
key_file = BASE_DIR + 'ssl/cert/kubecfg.key'

def get_context_from_knowledgebase(user_input: str, task_id: str):
    my_logger = logger.Logger('get_context' + str(datetime.now().strftime('%Y-%m-%d_%H-%M-%S')), log_dir=CLARIFY_BASE_DIR_OUTPUT + task_id + CURRENT_DIR + '/Logger/knowledge_log/')
    if get_context_from_knowledgebase_switch is False:
        my_logger.info('get_context_from_knowledgebase_switch is False')
        return ''
    data_input = {'query': user_input, 'agent': 'shopping'}
    try:
        with httpx.Client(verify=True, cert=(cert_file, key_file), http2=True) as client:
            response = client.post(url=base_url, headers=base_headers, content=json.dumps(data_input, ensure_ascii=False), timeout=120)
            my_logger.info(f'请求知识库成功：{user_input}')
            my_logger.info(f'状态码：{response.status_code}')
            my_logger.info(f'响应内容：{response.text}')
            if response.status_code == 200 and 'data' in response.text:
                data_context = json.loads(response.text)
                if 'data' in data_context:
                    return data_context.get('data')
                else:
                    my_logger.info(f'data is not in response')
                    return ''
            else:
                my_logger.info(f'返回的状态码不等于200：{response.status_code}')
                return ''
    except Exception as e:
        my_logger.info(f'请求报文：{e}')
        my_logger.info(f'请求知识库失败：{user_input}, error:' + str(e))
        return ''
