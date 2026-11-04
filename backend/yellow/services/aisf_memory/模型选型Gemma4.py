# Private iCAP Yellow business implementation. Do not publish.
"""
模型选型脚本 — 对比多个模型在4个任务上的表现

流程：
  1. run_all_tests()  → 调模型生成答案，写入各任务的 测试用例.xlsx
  2. run_all_evals()  → LLM-as-judge / 解析比对，计算准确率
  3. print_summary()  → 打印汇总表 + 保存 模型选型结果.xlsx

用法：
  python 模型选型Gemma4.py

配置项（在下方 CONFIG 区修改）：
  - SOURCE_MODE: "external"(外部平台) / "internal"(内部部署) / "auto"(自动)
  - SKIP_EXISTING: True 跳过已有结果
"""
import os, sys, json, re
import numpy as np
import pandas as pd
from openai import OpenAI
import llm_client
SOURCE_MODE = 'auto'
JUDGE_MODEL = 'qwen3.7-plus'
SKIP_EXISTING = True
EXTERNAL_MODEL_NAMES = {'Qwen3-32B': 'qwen3-32b', 'Qwen3.5-27B': 'qwen3.5-27b', 'Qwen3-8B': 'qwen3-8b', 'Qwen3.5-9B': 'qwen3.5-9b'}
llm_client._INTERNAL_MODEL_URLS.update({'Qwen3-32B': 'http://127.0.0.1:1/unconfigured', 'Qwen3.5-27B': 'http://127.0.0.1:1/unconfigured', 'Qwen3-8B': 'http://127.0.0.1:1/unconfigured', 'Qwen3.5-9B': 'http://127.0.0.1:1/unconfigured', 'gemma-4-12B': 'http://127.0.0.1:1/unconfigured', 'Qwen3.5-122B-A10B': 'http://127.0.0.1:1/unconfigured', 'openpangu-2.0-flash': 'https://api.modelarts-maas.com/v2/chat/completions'})
llm_client._INTERNAL_MODEL_NAMES['Qwen3.5-122B-A10B'] = 'dsv4'
llm_client._INTERNAL_MODEL_OPTIONS.update({'openpangu-2.0-flash': {'thinking_format': 'thinking_dict', 'enable_thinking': False, 'auth_token': 'kaT4R3Op1VP5r5aDGrECYemf-lh2YIOoad3ibd0IB9NEIowaLwVxMnvkJ7mjLCH00J5uQ2Z8FiAilts95I5kCA', 'strip_thinking_tags': False, 'verify_ssl': False}})
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def strip_json_wrapper(text):
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

def call_model(model_name, system_prompt, user_prompt):
    """统一的模型调用，根据 SOURCE_MODE 选择 external/internal"""
    if SOURCE_MODE == 'internal':
        source, api_model = ('internal', model_name)
    elif SOURCE_MODE == 'external':
        if model_name not in EXTERNAL_MODEL_NAMES:
            raise ValueError(f'{model_name} 在外部平台不可用，请切换 SOURCE_MODE 为 internal 或 auto')
        source, api_model = ('external', EXTERNAL_MODEL_NAMES[model_name])
    elif model_name in EXTERNAL_MODEL_NAMES:
        source, api_model = ('external', EXTERNAL_MODEL_NAMES[model_name])
    else:
        source, api_model = ('internal', model_name)
    print(f'    [调用] {model_name} via {source} ({api_model})')
    return llm_client.invoke_model(system_prompt, user_prompt, api_model, source)
_fewshot_cache = {}

def _get_embedding_client():
    return OpenAI(api_key=llm_client._EXTERNAL_API_KEY, base_url='https://dashscope.aliyuncs.com/compatible-mode/v1')

def _compute_embeddings(texts: list) -> np.ndarray:
    client = _get_embedding_client()
    all_vecs = []
    for i in range(0, len(texts), 10):
        batch = texts[i:i + 10]
        resp = client.embeddings.create(model='text-embedding-v3', input=batch, dimensions=512)
        vecs = [d.embedding for d in sorted(resp.data, key=lambda x: x.index)]
        all_vecs.extend(vecs)
    mat = np.array(all_vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return mat / norms

def _init_fewshot(task_dir):
    """加载 few-shot 库和 embedding 缓存"""
    if task_dir in _fewshot_cache:
        return _fewshot_cache[task_dir]
    lib_path = os.path.join(BASE_DIR, task_dir, 'few_shot_library.json')
    emb_path = os.path.join(BASE_DIR, task_dir, 'few_shot_embeddings.npy')
    with open(lib_path, 'r', encoding='utf-8') as f:
        library = json.load(f)
    queries = [item['query_text'] for item in library]
    if os.path.exists(emb_path):
        mat = np.load(emb_path)
        if mat.shape[0] == len(library):
            print(f'  已加载 few-shot embedding 缓存：{mat.shape}')
            data = {'library': library, 'queries': queries, 'embeddings': mat}
            _fewshot_cache[task_dir] = data
            return data
    print(f'  生成 {len(library)} 条 few-shot embedding...')
    mat = _compute_embeddings(queries)
    np.save(emb_path, mat)
    print(f'  embedding 已缓存至 {emb_path}')
    data = {'library': library, 'queries': queries, 'embeddings': mat}
    _fewshot_cache[task_dir] = data
    return data

def _build_fewshot_prompt(template, query, fewshot_data, top_k=5):
    """动态注入 few-shot 示例"""
    cut_marker = '// 下面是一些示例的格式'
    if cut_marker in template:
        template = template[:template.index(cut_marker)].rstrip()
    q_vec = _compute_embeddings([query])[0]
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
TASK_CONFIGS = [{'name': '画像记忆topic_subtopic提取', 'dir': '1. 画像记忆独立信息点topic_subtopic提取', 'models': ['Qwen3-32B', 'Qwen3.5-27B', 'gemma-4-12B', 'Qwen3.5-122B-A10B', 'openpangu-2.0-flash'], 'prompt_file': '画像记忆独立信息点topic_subtopic提取_v4.0_究极简化版.txt', 'prompt_version': 'v4.0', 'eval_type': 'llm_judge', 'use_fewshot': False}, {'name': '画像记忆更新', 'dir': '3.画像记忆更新', 'models': ['Qwen3-32B', 'Qwen3.5-27B', 'gemma-4-12B', 'Qwen3.5-122B-A10B', 'openpangu-2.0-flash'], 'prompt_file': '画像记忆更新.txt', 'prompt_version': 'v1.0', 'eval_type': 'llm_judge', 'use_fewshot': False}, {'name': '查询扩写', 'dir': '4.查询扩写', 'models': ['Qwen3-8B', 'Qwen3.5-9B', 'gemma-4-12B', 'Qwen3.5-122B-A10B', 'openpangu-2.0-flash'], 'prompt_file': '查询扩写_fewshot.txt', 'prompt_version': 'fewshot', 'eval_type': 'llm_judge', 'use_fewshot': True}, {'name': '总结过滤', 'dir': '5.总结过滤', 'models': ['Qwen3-8B', 'Qwen3.5-9B', 'gemma-4-12B', 'Qwen3.5-122B-A10B', 'openpangu-2.0-flash'], 'prompt_file': '总结过滤_v1.0.txt', 'prompt_version': 'v1.0', 'eval_type': 'parse_based', 'use_fewshot': False}]

def run_all_tests():
    """Phase 1: 对全部任务跑测试"""
    for task in TASK_CONFIGS:
        print(f"\n{'#' * 70}")
        print(f"# 测试: {task['name']} ({task['prompt_version']})")
        print(f"# 模型: {', '.join(task['models'])}")
        print(f"{'#' * 70}")
        xlsx_path = os.path.join(BASE_DIR, task['dir'], '测试用例.xlsx')
        df = pd.read_excel(xlsx_path, sheet_name='Sheet1')
        prompt_path = os.path.join(BASE_DIR, task['dir'], task['prompt_file'])
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
        fewshot_data = None
        if task['use_fewshot']:
            fewshot_data = _init_fewshot(task['dir'])
        col_names = []
        for model in task['models']:
            col = f"answer_{model}_{task['prompt_version']}"
            col_names.append(col)
            if col not in df.columns:
                df[col] = pd.Series(dtype='object')
        total = len(df)
        for idx in df.index:
            user_query = df.at[idx, 'user_query']
            if pd.isna(user_query):
                continue
            source_info = df.at[idx, '用例来源'] if '用例来源' in df.columns else ''
            print(f'\n[{idx + 1}/{total}] 来源={source_info} | {str(user_query)[:80]}...')
            for model, col in zip(task['models'], col_names):
                if SKIP_EXISTING and pd.notna(df.at[idx, col]):
                    print(f'  [{model}] 已有结果，跳过')
                    continue
                if task['use_fewshot']:
                    system_prompt = _build_fewshot_prompt(prompt_template, str(user_query), fewshot_data)
                else:
                    system_prompt = prompt_template
                result = call_model(model, system_prompt, str(user_query))
                result = strip_json_wrapper(result)
                if result is not None:
                    df.at[idx, col] = result
                print(f'  [{model}] -> {str(result)[:120]}')
            df.to_excel(xlsx_path, index=False, engine='openpyxl')
        print(f"\n测试完成：{task['name']}，结果已写回 {xlsx_path}")
EVAL_PROMPT_TOPIC_SUBTOPIC = '你是画像记忆提取的评测专家。你的任务是判断模型从用户对话中提取的画像记忆是否正确。\n\n## 评测标准\n画像记忆是长期描述用户身份、偏好、习惯、关系、配置、物品、人生事件的信息。\n\n**错误类型（任一命中即判错）：**\n\n1. 误提问句：把用户的查询问句当作事实提取。如"我喜欢什么运动？"→ 不能反向推断出任何事实。输出中出现"用户不知道/不确定/询问/需要确认"等即判错。\n2. 误提指令：提取了任务请求、工具调用、推荐请求、定时提醒等即时需求。\n3. 误提一次性事件：提取了普通日常事件而非长期画像。如"昨天买了一件衣服""今天跑了5公里""上周和朋友吃饭"。但人生里程碑（毕业、入职、结婚等）可以提取。\n4. 话题错误：topic 明显不匹配 detail 内容。\n5. 关系人错归：将关系人（家人、朋友等）的信息错误归为用户本人。如"我妈妈手机号是136xxx"提取为"用户的手机号是136xxx"。\n6. 输出格式错误：输出不是合法的 JSON 数组，或数组中元素缺少 topic/detail 字段。\n7. 凭空捏造：detail 中包含用户输入中未出现的信息。\n8. 问句包装：将问句包装为陈述事实，如用户问"我抽烟吗？"→ 输出"用户不确定自己是否抽烟"。\n\n**正确示例的特征：**\n- 只提取长期稳定的事实、偏好、习惯、关系、配置\n- 问句和指令正确跳过\n- topic 简短准确，detail 是完整的第三人称陈述句\n- 关系人信息正确归属\n\n## 输出格式\n{"正确": true/false, "原因": "一句话说明判定依据，指出具体哪条记忆有问题"}\n\n注意：如果输出是空数组 []，且输入确实只有问句/指令/一次性事件，则判定为正确。'
EVAL_PROMPT_UPDATE = '你是画像记忆更新的评测专家。你的任务是判断模型对新记忆与已有记忆的处理是否正确。\n\n## 背景\n输入包含"新提取的记忆"和"相似记忆"（已有记忆库）。模型需要判断新记忆与已有记忆的关系，输出 update（合并/替换已有记忆）、insert（新增）或 []（完全重复，无需操作）。\n\n## 评测标准\n\n**正确情况的判定：**\n\n1. 完全重复 → 输出 []：新记忆与某条已有记忆 topic、subtopic、detail 完全相同或语义等同。\n2. 可共存合并 → 输出 update，detail 包含新旧信息：新旧记忆 topic/subtopic 相同，描述同一属性维度的不同表现（如"喜欢苹果"和"喜欢香蕉"），合并后 detail 应包含两者。\n3. 冲突替换 → 输出 update，用新 detail 替换旧：新旧记忆对同一事物有对立态度，或唯一属性（生日、手机号等）值不同，应完全替换。\n4. 无关新增 → 输出 insert（id="new"）：新记忆与所有已有记忆的 topic 不同，或不满足关联条件。\n5. 有 update 就不能有 insert：这是核心规则，违反即判错。\n\n**错误类型（任一命中即判错）：**\n\n1. 操作类型错误：该 update 却 insert，该 insert 却 update，该 [] 却处理了。\n2. 同时输出 update 和 insert：违反核心规则。\n3. 完全重复未识别：新记忆与已有记忆语义完全等同，应输出 [] 但未识别。\n4. 合并结果错误：update 的 detail 遗漏了旧记忆或新记忆中的有效信息，或产生逻辑矛盾。\n5. 唯一属性合并错误：生日、手机号等唯一属性新旧值不同时，应用新值替换，不应合并。\n6. 有排除性词语未识别：旧记忆有"只""从不""只喜欢"等，新记忆落入排除范围时应视为冲突。\n7. 格式错误：输出不是合法 JSON 数组，或缺少 id/opType/topic/subtopic/detail 字段。\n\n## 输出格式\n{"正确": true/false, "原因": "一句话说明判定依据"}\n\n注意：如果模型输出 [] 且确实完全重复，判正确。如果模型输出 update 且合并结果合理，判正确。'
EVAL_PROMPT_QUERY_EXPAND = '你是查询扩写（记忆召回）的评测专家。你的任务是判断模型输出的召回短语是否正确。\n\n## 背景\n查询扩写模块根据用户 query 判断是否需要从长期记忆中召回用户专属信息。输出格式为 JSON 字符串数组：\n- `["短语1", "短语2"]`：需要召回，短语是对记忆系统的查询\n- `[]`：无需召回\n- `["all"]`：召回全部记忆\n\n## 评测标准\n\n**无需召回的场景（模型应输出 `[]`）：**\n- **纯事实陈述/知识输入**：用户纯粹在陈述事实或输入知识，没有提出任何需要个性化信息才能回答的问题。如"今天天气真好""二加二等于四""昨天买了一件衣服"。这类输入不构成召回需求，模型输出召回短语即为严重错误。\n- 纯外部事实查询（天气、新闻、股票、通用教程等）\n- 实时系统状态查询（现在几点、手机电量等）\n- 通用公开服务（导航、景点介绍、公共交通等）\n- 通用寒暄/闲聊（你好、讲个笑话等）\n- 用户已在 query 中提供了完成意图所需的全部个人信息\n\n**需要召回的场景（模型应输出召回短语）：**\n- 推荐/建议类（帮我推荐电影、餐厅、鞋子等），需召回偏好\n- 涉及用户个人关联实体（人名、地名、物品等）\n- 涉及用户自身状态、计划、关系、历史经历\n- 隐含个性化需求（需要用户习惯、偏好才能完成）\n- 询问用户个人属性（如"我的名字是什么""我的职业是什么"）→ 需要召回\n- 明确请求个人所有记忆（如"帮我做个自我介绍"）→ 输出 `["all"]`\n\n**错误判定：**\n1. **不该召回却召回**：query 属于无需召回场景（尤其是纯事实陈述、知识输入），模型却输出召回短语，导致噪声记忆污染下游回答。\n2. 该召回但未召回：query 明显需要个性化信息，模型却输出 `[]`\n3. 召回方向错误：输出的短语与 query 的信息缺口完全无关\n4. 格式错误：输出不是合法的 JSON 数组\n\n## 输出格式\n{"正确": true/false, "原因": "一句话说明判定依据"}'
EVAL_PROMPTS = {'画像记忆topic_subtopic提取': EVAL_PROMPT_TOPIC_SUBTOPIC, '画像记忆更新': EVAL_PROMPT_UPDATE, '查询扩写': EVAL_PROMPT_QUERY_EXPAND}

def call_judge(eval_prompt, user_input, model_output):
    """调用裁判模型"""
    output_text = strip_json_wrapper(str(model_output)) if model_output else ''
    user_msg = f'用户输入：\n{str(user_input)[:3000]}\n\n模型输出：\n{output_text[:3000]}\n\n请评测以上模型输出是否正确。'
    result = llm_client.invoke_model(eval_prompt, user_msg, JUDGE_MODEL)
    try:
        result = result.strip()
        if result.startswith('```'):
            result = result.split('\n', 1)[1].rsplit('```', 1)[0]
        return json.loads(result)
    except (json.JSONDecodeError, ValueError, AttributeError):
        return {'正确': False, '原因': f'评测解析失败: {str(result)[:200]}'}

def parse_id_list(raw):
    """从模型输出中提取 ID 列表。返回 (id_list, is_valid)"""
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
                        parsed = _extract_array_from_str(val)
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
        parsed = _extract_array_from_str(line.strip())
        if parsed is not None:
            return (parsed, True)
    parsed = _extract_array_from_str(text)
    if parsed is not None:
        return (parsed, True)
    return (None, False)

def _extract_array_from_str(s):
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

def run_all_evals():
    """Phase 2: 对全部任务跑评测，返回各模型准确率数据"""
    all_results = {}
    for task in TASK_CONFIGS:
        print(f"\n{'#' * 70}")
        print(f"# 评测: {task['name']} ({task['prompt_version']})")
        print(f"{'#' * 70}")
        xlsx_path = os.path.join(BASE_DIR, task['dir'], '测试用例.xlsx')
        df = pd.read_excel(xlsx_path, sheet_name='Sheet1')
        col_names = [f"answer_{m}_{task['prompt_version']}" for m in task['models']]
        task_results = {}
        for model, col in zip(task['models'], col_names):
            if col not in df.columns:
                print(f'[跳过] 列 {col} 不存在')
                task_results[model] = {'total': 0, 'correct': 0, 'accuracy': 0}
                continue
            eval_col = 'eval_' + col
            if eval_col not in df.columns:
                df[eval_col] = None
            print(f"\n{'=' * 50}")
            print(f"=== {model} | {task['prompt_version']} ===")
            print(f"{'=' * 50}")
            correct = 0
            total = 0
            for idx in df.index:
                raw = df.at[idx, col]
                if pd.isna(raw):
                    continue
                user_query = df.at[idx, 'user_query']
                source_info = df.at[idx, '用例来源'] if '用例来源' in df.columns else ''
                total += 1
                if task['eval_type'] == 'llm_judge':
                    existing_eval = df.at[idx, eval_col]
                    if SKIP_EXISTING and pd.notna(existing_eval):
                        try:
                            result = json.loads(existing_eval)
                            is_correct = result.get('正确', False)
                            reason = result.get('原因', '')
                            print(f'[{idx}] {source_info} (skip) {reason[:80]}')
                            if is_correct:
                                correct += 1
                            continue
                        except (json.JSONDecodeError, ValueError):
                            pass
                    eval_prompt = EVAL_PROMPTS[task['name']]
                    result = call_judge(eval_prompt, str(user_query), raw)
                    is_correct = result.get('正确', False)
                    reason = result.get('原因', '')
                    df.at[idx, eval_col] = json.dumps(result, ensure_ascii=False)
                elif task['eval_type'] == 'parse_based':
                    pred_ids, is_valid = parse_id_list(raw)
                    ref_raw = df.at[idx, '参考答案']
                    ref_ids, _ = parse_id_list(str(ref_raw)) if pd.notna(ref_raw) else ([], True)
                    if is_valid and pred_ids is not None:
                        if len(ref_ids) == 0:
                            is_correct = len(pred_ids) == 0
                            reason = '完全匹配(空)' if is_correct else f'不应过滤: pred={pred_ids}, ref={ref_ids}'
                        else:
                            is_correct = set(ref_ids).issubset(set(pred_ids))
                            if is_correct:
                                extra = sorted(set(pred_ids) - set(ref_ids))
                                reason = f'包含匹配(多{extra})' if extra else '完全匹配'
                            else:
                                missing = sorted(set(ref_ids) - set(pred_ids))
                                reason = f'遗漏: {missing}, pred={pred_ids}, ref={ref_ids}'
                    else:
                        is_correct = False
                        reason = '格式错误' if pd.notna(raw) else '未运行'
                    result = {'正确': is_correct, '原因': reason}
                    df.at[idx, eval_col] = json.dumps(result, ensure_ascii=False)
                if is_correct:
                    correct += 1
                status = '✓' if is_correct else '✗'
                print(f'[{idx}] {source_info} {status} {reason[:80]}')
            acc = correct / total if total > 0 else 0
            print(f"\n--- {model} | {task['prompt_version']} ---")
            print(f'准确率：{correct}/{total} = {acc:.1%}')
            task_results[model] = {'total': total, 'correct': correct, 'accuracy': acc}
            df.to_excel(xlsx_path, index=False, engine='openpyxl')
        all_results[task['name']] = task_results
    return all_results

def print_summary(all_results):
    """Phase 3: 打印汇总表 + 保存 模型选型结果.xlsx"""
    if not all_results:
        print('暂无结果，请先运行 run_all_tests() 和 run_all_evals()')
        return
    all_models = []
    for task in TASK_CONFIGS:
        for m in task['models']:
            if m not in all_models:
                all_models.append(m)
    print(f"\n{'=' * 90}")
    print('模型选型汇总表')
    print(f"{'=' * 90}")
    header = f"{'任务':<30}"
    for m in all_models:
        header += f' {m:<12}'
    header += f" {'用例数':<8}"
    print(header)
    print('-' * (30 + 14 * len(all_models) + 8))
    rows_for_excel = []
    for task in TASK_CONFIGS:
        task_name = task['name']
        label = f"{task_name}({task['prompt_version']})"
        task_results = all_results.get(task_name, {})
        row = f'{label:<30}'
        row_excel = {'任务': label}
        case_count = ''
        for m in task['models']:
            if m in task_results and task_results[m]['total'] > 0:
                case_count = str(task_results[m]['total'])
                break
        for m in all_models:
            if m in task['models'] and m in task_results:
                r = task_results[m]
                if r['total'] > 0:
                    cell = f"{r['accuracy']:.1%}"
                else:
                    cell = 'N/A'
            else:
                cell = '-'
            row += f' {cell:<12}'
            row_excel[m] = cell
        row += f' {case_count:<8}'
        row_excel['用例数'] = case_count
        print(row)
        rows_for_excel.append(row_excel)
    print(f"{'=' * 90}")
    output_path = os.path.join(BASE_DIR, '模型选型结果.xlsx')
    pd.DataFrame(rows_for_excel).to_excel(output_path, index=False, engine='openpyxl')
    print(f'\n汇总表已保存至: {output_path}')
    return rows_for_excel
