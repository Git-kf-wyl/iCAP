# Private iCAP Yellow business implementation. Do not publish.
from services.aisf.Constants import BERT_API_URL
from services.aisf.box.auto_run import run_box_check
from services.aisf.function_call.auto_run import run_all_scenes_fc
from services.aisf.intent_category.auto_run import run_all_scenes_ic
from services.aisf.memory.auto_run import run_all_scenes_mem
from services.aisf.perception_plan.auto_run import run_all_scenes_pp
from services.aisf.clarify.auto_run import run_all_scenes

def run_aisf_32b_dataset(api_url, model_name, task_id, user_req):
    """执行32b数据集

    Args:
        api_url: 模型API地址
        model_name: 模型名称
        task_id: 任务ID
        user_req: 用户请求数据，需包含datasets和model_id字段
    """
    task_mapping = {'aisf_clarify_32b': (run_all_scenes, []), 'aisf_functioncall_32b': (run_all_scenes_fc, []), 'aisf_intentcategory_32b': (run_all_scenes_ic, []), 'aisf_perceptionplan_32b': (run_all_scenes_pp, []), 'aisf_memory_forever_32b': (run_all_scenes_mem, ['aisf_memory_forever_32b']), 'aisf_box_param_extract_32b': (run_box_check, ['box_params'])}
    if not all((key in user_req for key in ['datasets', 'model_id'])):
        raise ValueError("Missing required fields in user_req: 'datasets' and 'model_id'")
    datasets = user_req['datasets']
    model_id = user_req['model_id']
    for dataset in datasets:
        if dataset in task_mapping:
            func, extra_args = task_mapping[dataset]
            args = [task_id, model_name, api_url]
            if extra_args:
                args.extend(extra_args)
            elif dataset == 'aisf_box_param_extract_32b':
                input_params = {'bert_url': '', 'fast_url': '', 'fast_model_name': '', 'fast_scene': '', 'slow_url': api_url, 'slow_model_name': model_name, 'task_id': task_id, 'model_id': model_id}
                args = [input_params]
            func(*args)

def run_aisf_8b_dataset(api_url, model_name, task_id, user_req):
    """
    运行8b的5个测试集，包括出行Agent记忆、记忆-属性萃取、记忆-主题记忆决策、记忆-事实记忆决策、决策意图分类。
    aisf_memory_travel_agent_8b
    /aisf_memory_attribute_extract_8b
    /aisf_memory_topic_8b
    /aisf_memory_fact_8b
    /aisf_memory_intent_classify_8b
    Args:
        api_url (str): API。
        model_name (str): 模型名称。
        task_id (str): 任务ID。
        user_req (dict): 用户请求，包含数据集列表。
    """
    prefix = 'aisf_memory'
    suffix = '8b'
    if 'datasets' not in user_req:
        raise ValueError("user_req must contain 'datasets' key")
    for dataset in user_req['datasets']:
        if not isinstance(dataset, str):
            continue
        if dataset.startswith(prefix) and dataset.endswith(suffix):
            run_all_scenes_mem(task_id, model_name, api_url, dataset)

def run_aisf_4b_dataset(api_url, model_name, task_id, user_req):
    """
    处理4b的2个测试集 算力主机模型提参（快路径） 算力主机场景分类

    Args:
        api_url (str): 模型API地址
        model_name (str): 模型名称
        task_id (str): 任务ID
        user_req (dict): 用户请求数据，包含datasets字段
    """
    scene_mapping = {'aisf_box_scene_classify_4b': 'scene_classify', 'aisf_box_param_extract_4b': 'param_extract'}
    for dataset in user_req.get('datasets', []):
        if dataset in scene_mapping:
            input_params = {'bert_url': '', 'fast_url': api_url, 'fast_model_name': model_name, 'fast_scene': scene_mapping[dataset], 'slow_url': '', 'slow_model_name': '', 'task_id': task_id}
            run_box_check(input_params)

def run_aisf_no_chart(api_url, model_name, task_id, user_req):
    """
    执行AISF非榜单相关任务。

    Args:
        api_url (str): 模型API。
        model_name (str): 模型名称。
        task_id (str): 任务ID。
        user_req (dict): 用户请求数据，包含数据集信息。
    """
    if 'aisf_box_bert' in user_req.get('datasets', []):
        input_params = {'bert_url': BERT_API_URL, 'fast_url': api_url, 'fast_model_name': model_name, 'fast_scene': '', 'slow_url': '', 'slow_model_name': '', 'task_id': task_id}
        run_box_check(input_params)
    open_memory_datasets = ['aisf_memory_8b_open', 'aisf_memory_32b_open']
    for dataset in open_memory_datasets:
        if dataset in user_req.get('datasets', []):
            run_all_scenes_mem(task_id, model_name, api_url, dataset)
