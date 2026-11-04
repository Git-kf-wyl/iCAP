# Private iCAP Yellow business implementation. Do not publish.
import json
import os
import re
import numpy as np
import requests
import urllib3
import httpx
from openai import OpenAI
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_proxy_url = ''
proxy = None
_HTTP_TRANSPORT = httpx.HTTPTransport(retries=3, verify=True)
http_client = httpx.Client(transport=_HTTP_TRANSPORT, timeout=10)
_MEMORY_BASE_DIR = os.path.join(current_dir, 'services', 'aisf_memory')
_MEMORY_DATASET_SUBDIRS = {'画像记忆topic_subtopic提取': '画像记忆topic_subtopic提取', '情景记忆独立信息点topic_treepath提取': '情景记忆独立信息点topic_treepath提取', '画像记忆更新': '画像记忆更新', '查询扩写': '查询扩写', '总结过滤': '总结过滤', '记忆删除具体实现': '记忆删除具体实现', '记忆删除意图识别': '记忆删除意图识别'}
_MEMORY_TASK_DIRS = {'画像记忆topic_subtopic提取': '1. 画像记忆独立信息点topic_subtopic提取', '情景记忆独立信息点topic_treepath提取': '2.情景记忆独立信息点topic_treepath提取', '画像记忆更新': '3.画像记忆更新', '查询扩写': '4.查询扩写', '总结过滤': '5.总结过滤', '记忆删除具体实现': os.path.join('6.记忆删除', '记忆删除具体实现'), '记忆删除意图识别': os.path.join('6.记忆删除', '记忆删除意图识别')}
_MEMORY_PROMPT_FILES = {'画像记忆topic_subtopic提取': {'v4.0': '画像记忆独立信息点topic_subtopic提取_v4.0_究极简化版.txt', 'v3.0': '画像记忆独立信息点topic_subtopic提取_v3.0_修改输出格式.txt', 'v2.0': '画像记忆独立信息点topic_subtopic提取_v2.0.txt', 'v1.0': '画像记忆独立信息点topic_subtopic提取_v1.0.txt'}, '情景记忆独立信息点topic_treepath提取': {'v1.0': '情景记忆独立信息点topic_treepath提取.txt', 'v2.0': '情景记忆独立信息点topic_treepath提取_v2.0.txt'}, '画像记忆更新': {'v1.0': '画像记忆更新.txt'}, '查询扩写': {'fewshot': '查询扩写_fewshot.txt', '原版': '查询扩写_原版.txt'}, '总结过滤': {'v1.0': '总结过滤_v1.0.txt', 'v2.0': '总结过滤_v2.0_若曦修改版.txt', 'v3.0': '总结过滤_v3.0_伪思考长思考.txt', 'v3.1': '总结过滤_v3.1_伪思考短思考.txt'}, '记忆删除具体实现': {'v1.0': '记忆删除具体实现.txt'}, '记忆删除意图识别': {'v1.0': '记忆删除意图识别.txt'}}
_MEMORY_EVAL_TYPES = {'画像记忆topic_subtopic提取': 'llm_judge', '画像记忆更新': 'llm_judge', '查询扩写': 'llm_judge', '总结过滤': 'parse_based'}
_MEMORY_EVAL_PROMPT_TOPIC_SUBTOPIC = '你是画像记忆提取的评测专家。你的任务是检查模型输出是否违反以下**原则性规则**。\n\n## 重要：ground_truth 仅供参考\nground_truth 是一个正确示例，但**不是唯一标准答案**。只要模型输出不违反原则性规则，即使与 ground_truth 不完全一致（条目数不同、topic措辞不同等），也应判对。\n\n## 原则性错误（任一命中即判错）\n\n1. **问句反推**：将用户的查询问句当作事实提取。如用户问"我喜欢什么运动？"→ 输出包含"用户喜欢XX运动"即判错。输出中出现"用户不知道/不确定/询问/需要确认"等也判错。\n2. **凭空捏造**：detail 中包含用户输入中未出现的信息。\n3. **关系人错归**：detail 中描述关系人属性的信息，其主语被错误写成"用户"。**判断标准是 detail 的主语归属**：如果 topic 和 detail 的主语指向同一主体（如 topic="母亲"、detail 主语是"用户母亲"）则不是错归。只有当 topic 指向关系人，但 detail 主语却写成"用户"时（如 topic="母亲"但 detail="用户的手机号是..."），才是错归。\n4. **提取任务指令**：提取了任务请求、工具调用、推荐请求、定时提醒等即时需求。\n5. **提取一次性事件**：提取了普通日常事件而非长期画像。如"昨天买了衣服""今天跑了5公里"。但人生里程碑（毕业、入职、结婚等）可以提取。\n6. **输出格式不合法**：输出不是合法的 JSON 数组，或元素缺少 topic/detail 字段。\n\n## 不算错误的情况（判对）\n- 模型多提取/少提取了一条，但提取的内容本身不违反上述原则 → 判对\n- topic 措辞不完全相同但语义合理（如"饮食偏好" vs "食物偏好"）→ 判对\n- detail 措辞不同但核心事实一致 → 判对\n- ground_truth 是 [] 但模型输出了一些看起来合理的条目，只要不违反原则 → 判对（反之亦然）\n\n## 输出格式\n{"原因": "如果错误，指出具体违反了哪条原则及哪条记忆有问题；如果正确，简要说明", "正确": true/false}'
_MEMORY_EVAL_PROMPT_UPDATE = '你是画像记忆更新的评测专家。你的任务是检查模型输出是否违反以下**原则性规则**。\n\n## 背景\n输入包含"新提取的记忆"和"相似记忆"（已有记忆库）。模型需要判断关系，输出 update、insert 或 []。\n\n## 重要：ground_truth 仅供参考\nground_truth 是一个正确示例，但**不是唯一标准答案**。insert 和 update 的选择存在主观空间——同一个case，insert 合理，update 也可能合理。只要模型不违反以下原则性规则，即使与 ground_truth 的 opType 不同或操作数量不同，也应判对。\n\n## 原则性错误（任一命中即判错）\n\n1. **同时输出 update 和 insert**：核心规则禁止。只要模型输出中同时出现 opType="update" 和 opType="insert"，即判错。\n2. **完全重复未识别**：新记忆与某条已有记忆的 topic、subtopic、detail 核心语义完全等同，模型应输出 [] 却做了 update/insert。\n3. **唯一属性合并错误**：生日、手机号、年龄等唯一属性，新旧值不同时应用新值替换，不应把两个不同值合并（如"生日是1990.1.1和1995.5.5"）。\n4. **排除性词语未识别**：旧记忆有"只""从不""只喜欢"等排除词，且新记忆落入被排除范围，此时应用新值完全替换旧记忆，而非合并。\n5. **detail 有明显逻辑矛盾**：合并/替换后的 detail 出现自相矛盾（如"用户已婚又未婚""用户喜欢猫又不喜欢猫"）。\n6. **输出格式不合法**：输出不是合法的 JSON 数组，或元素缺少 id/opType/topic/subtopic/detail 字段。\n7. **同一新信息分散到多条已有记忆**：新记忆的核心信息只应合并到最匹配的一条已有记忆（做一次 update），或做一次 insert。如果模型输出了多条 update，且不同的 update 的 detail 中都融入了同一新记忆的核心内容（如新记忆"喜欢草莓"同时出现在了 update id:1 和 update id:3 的 detail 中），属于冗余/重复操作，判错。\n\n## 不算错误的情况（判对）\n- insert vs update 选择不同：模型选 insert，ground_truth 是 update（或反之），只要操作本身不违反上述原则 → 判对\n- 操作数量不同：模型只 update 了1条，ground_truth update 了2条，只要不违反原则 → 判对\n- detail 措辞不同但核心信息一致 → 判对\n- 模型输出 [] 但 ground_truth 有操作（或反之），只要不违反完全重复/原则性错误 → 判对\n\n## 输出格式\n{"原因": "如果错误，指出具体违反了哪条原则；如果正确，简要说明", "正确": true/false}'
_MEMORY_EVAL_PROMPT_QUERY_EXPAND = '你是查询扩写（记忆召回）的评测专家。你的任务是检查模型输出是否违反以下**原则性规则**。\n\n## 背景\n查询扩写模块根据用户 query 判断是否需要召回用户专属信息。输出格式为 JSON 字符串数组：\n- `["短语1", ...]`：需要召回\n- `[]`：无需召回\n- `["all"]`：召回全部记忆\n\n## 重要：ground_truth 仅供参考\nground_truth 是一个正确示例，但**不是唯一标准答案**。对于纯陈述类 query（如"我喜欢吃草莓"），召回或不召回都有道理；召回短语措辞不同但方向一致也算对。只要模型不违反以下原则性规则，即判对。\n\n## 原则性错误（任一命中即判错）\n\n1. **不该召回却召回**：query 明显是纯外部信息查询（天气、新闻、股票、通用知识）、实时系统状态（现在几点）、通用寒暄/闲聊（你好、讲个笑话），不需要任何个性化信息，模型却输出召回短语。\n2. **该召回却不召回**：query 明显需要用户个性化信息才能回答（如"帮我推荐电影""我的手机号是什么""我的生日""我明天有什么安排"），模型却输出 []。\n3. **`["all"]` 严重误用**：query 明确请求所有记忆（如"帮我做个自我介绍""你都记住了什么""你了解我吗"）→ 应输出 `["all"]` 却输出其他；或 query 明显只需要特定信息 → 应输出具体短语却输出 `["all"]`。\n4. **召回方向完全错误**：模型输出的召回短语与 query 的信息缺口方向毫无关系。如 query 问"推荐餐厅"却召回"用户的运动偏好"。\n5. **输出格式不合法**：输出不是合法的 JSON 数组。\n\n## 不算错误的情况（判对）\n- 纯陈述类 query（如"我喜欢吃草莓""我每天喝咖啡"）：召回或不召回都可 → 判对\n- 召回短语措辞不同但方向正确（如"用户的电影偏好" vs "用户喜欢看的电影类型"）→ 判对\n- 多召回/少召回了一条（边界模糊的情况）→ 判对\n\n## 输出格式\n{"原因": "如果错误，指出具体违反了哪条原则；如果正确，简要说明", "正确": true/false}'
_MEMORY_EVAL_PROMPT_TOPIC_TREEPATH = '你是情景记忆提取的评测专家。你的任务是判断模型从用户对话中提取的情景记忆是否正确。\n\n## 评测标准\n情景记忆是与用户绑定的具体事件、经历、活动、计划、阶段性进展或行为结果，需要有时间/场景关联。\n\n**错误类型（任一命中即判错）：**\n\n1. 误提问句：把用户的查询问句当作事件提取。如"我上次去哪旅游了？"→ 不能包装成情景记忆。输出中出现"用户询问/想知道/不确定"等即判错。\n2. 误提指令：提取了任务请求、工具调用、推荐、搜索、播放、导航、提醒等即时需求。\n3. 误提单次音乐/观影/搜索：提取了单次播放音乐、单次观影、单次搜索行为。但阶段性、重复性的文化娱乐活动可以提取。\n4. 误提画像信息：提取了脱离具体事件的长期偏好、身份属性、稳定关系、重要日期、物品静态位置等画像级信息。如"我喜欢科幻片""妈妈生日是12月15日""车钥匙放在鞋柜上"。\n5. 误提无行为抽象状态：如"我最近很忙""我有点饿""我想出去玩"等无具体行为的状态描述。\n6. 误提通用知识/语义记忆：提取了算法定义、公开事实、概念解释等。\n7. 输出格式错误：输出不是合法的 JSON 数组，或数组中元素缺少 topic/detail 字段。\n8. 凭空捏造：detail 中包含用户输入中未出现的信息。\n\n**正确示例的特征：**\n- 提取的内容有明确行为主体 + 具体行为 + 时间/地点/对象/结果中的至少两项\n- 问句、指令、单次音乐/观影正确跳过\n- 画像级长期信息正确跳过\n- topic 简短概括事件类型，detail 是完整的第三人称陈述句\n\n## 输出格式\n{"正确": true/false, "原因": "一句话说明判定依据，指出具体哪条记忆有问题"}\n\n注意：如果输出是空数组 []，且输入确实只有问句/指令/画像信息/单次观影音乐，则判定为正确。'
_MEMORY_EVAL_PROMPTS = {'画像记忆独立信息点topic_subtopic提取': _MEMORY_EVAL_PROMPT_TOPIC_SUBTOPIC, '情景记忆独立信息点topic_treepath提取': _MEMORY_EVAL_PROMPT_TOPIC_TREEPATH, '画像记忆更新': _MEMORY_EVAL_PROMPT_UPDATE, '查询扩写': _MEMORY_EVAL_PROMPT_QUERY_EXPAND}
_MEMORY_JUDGE_MODEL = 'qwen3.7-plus'
_MEMORY_EXTERNAL_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
_MEMORY_EXTERNAL_API_KEY = ''

def _call_model_direct(api_url, api_key, model_name, system_prompt, user_prompt, generation_config, non_openai_format=False):
    """直接调用模型 API（OpenAI 兼容格式）"""
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}]
    payload = {'model': model_name, 'messages': messages, 'thinking': {'type': 'disabled'}, 'chat_template_kwargs': {'thinking': False}}
    if generation_config:
        for k, v in generation_config.items():
            if k not in ('model', 'messages'):
                payload[k] = v
    headers = {'Content-Type': 'application/json'}
    if api_key and api_key != 'EMPTY':
        headers['Authorization'] = f'Bearer {api_key}'
    try:
        r = requests.post(url=api_url, json=payload, headers=headers, timeout=300, verify=True)
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            if content is None:
                content = r.json()['choices'][0]['message'].get('reasoning_content', '') or ''
            return {'status': 'success', 'content': content, 'message': ''}
        else:
            msg = f'HTTP {r.status_code}: {r.text[:500]}'
            print(f'  [API Error] {msg}')
            return {'status': 'error', 'content': None, 'message': f"模型调用报错: 'payload: {payload}'; {msg}"}
    except requests.exceptions.Timeout as e:
        msg = f'模型调用超时: {str(e)[:200]}'
        print(f'  [API Timeout] {e}')
        return {'status': 'timeout', 'content': None, 'message': msg}
    except Exception as e:
        msg = f'模型调用异常: {str(e)[:200]}'
        print(f'  [API Exception] {e}')
        return {'status': 'error', 'content': None, 'message': msg}

def _call_judge_model(eval_prompt, user_input, model_output, ground_truth=''):
    """调用裁判模型（外部 qwen3.7-plus）进行 LLM-as-Judge 评测"""
    output_text = _strip_json_wrapper(str(model_output)) if model_output else ''
    gt_text = _strip_json_wrapper(str(ground_truth)) if ground_truth else ''
    user_msg = f'用户输入：\n{str(user_input)[:3000]}\n\n模型输出：\n{output_text[:3000]}\n\nground_truth（仅供参考，非唯一标准答案）：\n{gt_text[:3000]}\n\n请检查模型输出是否违反原则性规则。'
    try:
        client = OpenAI(api_key=_MEMORY_EXTERNAL_API_KEY, base_url=_MEMORY_EXTERNAL_BASE_URL, http_client=http_client)
        response = client.chat.completions.create(model=_MEMORY_JUDGE_MODEL, messages=[{'role': 'system', 'content': eval_prompt}, {'role': 'user', 'content': user_msg}], extra_body={'enable_thinking': False}, temperature=0)
        result = response.choices[0].message.content
        if result:
            result = result.strip()
            if result.startswith('```'):
                result = result.split('\n', 1)[1].rsplit('```', 1)[0]
            return json.loads(result)
        return {'正确': False, '原因': '裁判模型返回空'}
    except Exception as e:
        print(f'  [Judge Error] {e}')
        return {'正确': False, '原因': f'评测解析失败: {str(e)[:200]}'}

def _strip_json_wrapper(text):
    """剥离 ```json ... ``` 包裹"""
    if text is None:
        return text
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()

def _memory_parse_id_list(raw):
    """从模型输出中提取 ID 列表，同 模型选型Gemma4.py 的 parse_id_list"""
    if raw is None or not isinstance(raw, str):
        return (None, False)
    text = raw.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            if all((isinstance(x, (int, float)) for x in obj)):
                return ([int(x) for x in obj], True)
            return (None, False)
        if isinstance(obj, dict):
            for key in ['输出', 'output', 'answer', 'ids']:
                if key in obj:
                    val = obj[key]
                    if isinstance(val, list) and all((isinstance(x, (int, float)) for x in val)):
                        return ([int(x) for x in val], True)
                    if isinstance(val, str):
                        parsed = _memory_extract_array_from_str(val)
                        if parsed is not None:
                            return (parsed, True)
            if 'memory_list' in obj:
                ids = [item['id'] for item in obj['memory_list'] if isinstance(item, dict) and 'id' in item]
                if ids:
                    return (ids, True)
        return (None, False)
    except (json.JSONDecodeError, ValueError):
        pass
    lines = text.strip().split('\n')
    for line in reversed(lines):
        parsed = _memory_extract_array_from_str(line.strip())
        if parsed is not None:
            return (parsed, True)
    parsed = _memory_extract_array_from_str(text)
    if parsed is not None:
        return (parsed, True)
    return (None, False)

def _memory_extract_array_from_str(s):
    """从字符串中提取 [数字,...] 或 []"""
    match = re.search('\\[([0-9,\\s]*)\\]', s)
    if match:
        inner = match.group(1).strip()
        if inner == '':
            return []
        try:
            return [int(x.strip()) for x in inner.split(',') if x.strip() != '']
        except ValueError:
            return None
    return None
_fewshot_cache = {}

def _memory_init_fewshot(task_dir):
    """加载 few-shot 库和 embedding 缓存"""
    if task_dir in _fewshot_cache:
        return _fewshot_cache[task_dir]
    lib_path = os.path.join(task_dir, 'few_shot_library.json')
    emb_path = os.path.join(task_dir, 'few_shot_embeddings.npy')
    if not os.path.exists(lib_path):
        return None
    with open(lib_path, 'r', encoding='utf-8') as f:
        library = json.load(f)
    queries = [item['query_text'] for item in library]
    if os.path.exists(emb_path):
        mat = np.load(emb_path)
        if mat.shape[0] == len(library):
            data = {'library': library, 'queries': queries, 'embeddings': mat}
            _fewshot_cache[task_dir] = data
            return data
    print(f'  生成 {len(library)} 条 few-shot embedding...')
    client = OpenAI(api_key=_MEMORY_EXTERNAL_API_KEY, base_url=_MEMORY_EXTERNAL_BASE_URL)
    all_vecs = []
    for i in range(0, len(queries), 10):
        batch = queries[i:i + 10]
        resp = client.embeddings.create(model='text-embedding-v3', input=batch, dimensions=512)
        vecs = [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]
        all_vecs.extend(vecs)
    mat = np.array(all_vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1
    mat = mat / norms
    np.save(emb_path, mat)
    print(f'  embedding 已缓存至 {emb_path}')
    data = {'library': library, 'queries': queries, 'embeddings': mat}
    _fewshot_cache[task_dir] = data
    return data

def _memory_build_fewshot_prompt(template, query, fewshot_data, top_k=5):
    """动态注入 few-shot 示例"""
    cut_marker = '// 下面是一些示例的格式'
    if cut_marker in template:
        template = template[:template.index(cut_marker)].rstrip()
    q_vec = _compute_memory_embedding(query)
    scores = fewshot_data['embeddings'] @ q_vec
    top_idx = np.argsort(scores)[::-1][:top_k]
    examples = [fewshot_data['library'][i] for i in top_idx]
    lines = []
    for i, ex in enumerate(examples, 1):
        rq = json.dumps(ex['rewrite_queries'], ensure_ascii=False)
        lines.append(f'### 示例{i}')
        lines.append(f"输入：{ex['query_text']}")
        lines.append(f'输出：{rq}')
        lines.append('')
    examples_text = '\n'.join(lines).strip()
    return template.replace('{{few_shot}}', examples_text)
_compute_memory_embedding_client = None

def _compute_memory_embedding(text):
    global _compute_memory_embedding_client
    if _compute_memory_embedding_client is None:
        _compute_memory_embedding_client = OpenAI(api_key=_MEMORY_EXTERNAL_API_KEY, base_url=_MEMORY_EXTERNAL_BASE_URL)
    resp = _compute_memory_embedding_client.embeddings.create(model='text-embedding-v3', input=[text], dimensions=512)
    vec = np.array(resp.data[0].embedding, dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec
__all__ = ['_memory_init_fewshot', '_memory_build_fewshot_prompt', '_call_model_direct', '_strip_json_wrapper', '_call_judge_model', '_memory_parse_id_list', '_MEMORY_EVAL_PROMPTS', '_MEMORY_JUDGE_MODEL']
