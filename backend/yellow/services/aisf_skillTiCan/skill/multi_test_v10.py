# Private iCAP Yellow business implementation. Do not publish.
"""
四场景 Skill 提参批量测试脚本

支持场景：
1. IoT控制：iot_control_skill
2. 医院挂号：health-register
3. 吃药提醒：health_take_medicine_skill
4. 健康档案生成：health_record_generate_skill

功能：
1. 读取 Excel 测试用例
2. 组装 messages
3. 自动给 tool_call.function.arguments 注入 tool_call_id
4. 自动修复 assistant.content=None 为 ""
5. 调用模型接口
6. 解析模型输出，支持 ```json ... ``` 代码块
7. 规则校验；IOT 仅在结构正确但 command 文本不一致时追加语义阅卷
8. 所有失败细节统一写入 error_reason，导出精简测试结果 Excel
"""
import ast
import copy
import json
import re
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
import prompt_v18 as sp
EXCEL_PATH = 'test_0611.xlsx'
SHEET_NAME = 'Sheet1'
OUTPUT_PATH = 'test_result_0626_prompt_v19_32B_0611test_medicine_v12_register_v5_IOT_v1_test.xlsx'
SKILL_MD_PATH_MAP = {'iot_control_skill': 'skill_IOT_v1.md', 'health-register': 'skill_health_registered_v5.md', 'health_take_medicine_skill': 'skill_take_medicine_v13.md'}
API_BASE_URL = 'http://127.0.0.1:1/unconfigured'
API_KEY = ''
MODEL_NAME = 'Qwen3-32B'
ENABLE_IOT_SEMANTIC_JUDGE = True
JUDGE_MODEL_NAME = MODEL_NAME
JUDGE_TEMPERATURE = 0
TEMPERATURE = 0
TIMEOUT = 120
MAX_WORKERS = 1
LIMIT = None
FLATTEN_TOOL_MESSAGES = False
MOCK_MODE = False
DEBUG_PRINT_MESSAGES = False
DEBUG_PRINT_RESPONSE = False
PRINT_EACH_RESULT = True
PRINT_FAILED_DETAIL = True
PRINT_MODEL_OUTPUT = True
SAVE_JSONL_EVERY_CASE = False
JSONL_LOG_PATH = '提参测试过程日志_四场景版.jsonl'

def read_text(path: str) -> str:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f'文件不存在: {path}')
    return path_obj.read_text(encoding='utf-8')

def safe_cell(value: Any) -> str:
    """把 Excel 单元格转成干净字符串。"""
    if pd.isna(value):
        return ''
    return str(value).strip()

def parse_json_like(text: Any) -> Any:
    """
    解析 JSON 字符串。
    兼容：
    1. 标准 JSON
    2. Python dict 字符串
    3. 被 ```json 包起来的内容
    """
    if isinstance(text, (dict, list)):
        return text
    s = safe_cell(text)
    if not s:
        raise ValueError('空字符串无法解析为 JSON')
    s = s.strip()
    code_block_pattern = '```(?:json)?\\s*(.*?)\\s*```'
    matches = re.findall(code_block_pattern, s, flags=re.DOTALL | re.IGNORECASE)
    if matches:
        for block in matches:
            candidate = block.strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass
    try:
        return json.loads(s)
    except Exception:
        pass
    try:
        return ast.literal_eval(s)
    except Exception as e:
        raise ValueError(f'JSON 解析失败: {s[:300]}') from e

def parse_model_json_output(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    尝试从模型输出里解析 JSON。
    支持：
    1. 纯 JSON
    2. ```json ... ``` 代码块
    3. 前后夹杂少量说明文本
    """
    if text is None:
        return (None, '模型输出为空')
    s = str(text).strip()
    code_block_pattern = '```(?:json)?\\s*(.*?)\\s*```'
    matches = re.findall(code_block_pattern, s, flags=re.DOTALL | re.IGNORECASE)
    if matches:
        for block in matches:
            candidate = block.strip()
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return (obj, '')
            except Exception:
                continue
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return (obj, '')
        return (None, '模型输出不是 JSON object')
    except Exception:
        pass
    start = s.find('{')
    end = s.rfind('}')
    if start >= 0 and end > start:
        candidate = s[start:end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return (obj, '')
            return (None, '截取后不是 JSON object')
        except Exception as e:
            return (None, f'截取 JSON 后仍解析失败: {e}')
    return (None, '未找到可解析 JSON')

def parse_medication_list_for_compare(value: Any) -> Any:
    """
    medicationList 可能是 JSON 字符串，也可能已经是数组。
    评测时把可解析的 JSON 字符串转成结构化对象再比较，避免因为空格、转义、字段顺序导致误判。
    """
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return s
        try:
            parsed = json.loads(s)
        except Exception:
            return s
        return parsed
    return value

def normalize_json(obj: Any) -> Any:
    """
    递归归一化，方便比较。
    dict 按 key 排序，list 保留顺序。

    特殊处理：
    - medicationList 如果是 JSON 字符串，先解析成数组/对象再比较。
      这样 `[{"a":1}]` 和带空格/字段顺序不同的 JSON 字符串可以语义等价。
    """
    if isinstance(obj, dict):
        normalized = {}
        for k, v in sorted(obj.items(), key=lambda x: x[0]):
            if k == 'medicationList':
                normalized[k] = normalize_json(parse_medication_list_for_compare(v))
            else:
                normalized[k] = normalize_json(v)
        return normalized
    if isinstance(obj, list):
        return [normalize_json(x) for x in obj]
    return obj

def exact_match(expected: Any, actual: Any) -> bool:
    return normalize_json(expected) == normalize_json(actual)

def get_tool_calls(skill_select_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    return skill_select_result.get('tool_calls', []) or []

def get_function_arguments(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    args = tool_call.get('function', {}).get('arguments', '{}')
    if isinstance(args, dict):
        return args
    return parse_json_like(args)

def inject_tool_call_id_into_arguments(skill_select_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    给每个 tool_call.function.arguments 注入 tool_call_id。
    同时把 assistant.content=None 修成 ""。

    例：
    {
      "id": "A_01",
      "function": {
        "arguments": "{"content":"xxx","depends_on":"False"}"
      }
    }

    变成：
    {
      "id": "A_01",
      "function": {
        "arguments": "{"tool_call_id":"A_01","content":"xxx","depends_on":"False"}"
      }
    }
    """
    if not isinstance(skill_select_result, dict):
        return skill_select_result
    fixed = copy.deepcopy(skill_select_result)
    if fixed.get('role') == 'assistant' and fixed.get('content') is None:
        fixed['content'] = ''
    tool_calls = fixed.get('tool_calls', []) or []
    for tc in tool_calls:
        tool_call_id = tc.get('id', '')
        function_obj = tc.get('function', {})
        args_raw = function_obj.get('arguments', '{}')
        if isinstance(args_raw, dict):
            args_obj = args_raw
        else:
            args_obj = parse_json_like(args_raw)
        if not isinstance(args_obj, dict):
            raise ValueError(f'function.arguments 解析后不是对象: {args_raw}')
        new_args_obj = {'tool_call_id': tool_call_id}
        new_args_obj.update(args_obj)
        new_args_obj['tool_call_id'] = tool_call_id
        function_obj['arguments'] = json.dumps(new_args_obj, ensure_ascii=False)
        tc['function'] = function_obj
    return fixed
USE_UPSTREAM_AS_EXECUTED_TOOL_CALLS = True
UPSTREAM_RESULT_COLUMN_CANDIDATES = ['上游查询结果', '上游tool结果', '上游工具结果', '上游Skill结果', '上游结果']

def get_upstream_result_raw(row: pd.Series) -> str:
    """
    从 Excel 行里读取上游查询结果。

    v97 新增 AB 列名是「上游查询结果」。这里保留几个候选列名，
    避免以后人类又心血来潮把列名改成另一个同义词，然后脚本当场装死。
    """
    for col in UPSTREAM_RESULT_COLUMN_CANDIDATES:
        if col in row.index:
            value = safe_cell(row.get(col, ''))
            if value:
                return value
    return ''

def normalize_upstream_results(raw: Any) -> List[Dict[str, Any]]:
    """
    解析并归一化上游查询结果。

    支持 Excel 单元格里填：
    1. JSON 数组：[{...}]
    2. JSON 对象：{...}
    3. ```json ...``` 包裹的 JSON

    返回值统一为 List[Dict]，空值返回空数组。
    """
    if isinstance(raw, list):
        obj = raw
    elif isinstance(raw, dict):
        obj = [raw]
    else:
        text = safe_cell(raw)
        if not text:
            return []
        obj = parse_json_like(text)
    if isinstance(obj, dict):
        obj = [obj]
    if not isinstance(obj, list):
        raise ValueError('上游查询结果解析后必须是数组或对象')
    normalized: List[Dict[str, Any]] = []
    for i, item in enumerate(obj, start=1):
        if not isinstance(item, dict):
            raise ValueError(f'上游查询结果第{i}项不是对象: {item}')
        normalized.append(item)
    return normalized

def build_upstream_result_context(row: pd.Series) -> str:
    """
    把 Excel 的「上游查询结果」列转成一段可塞进 messages 的上下文。

    仅在 USE_UPSTREAM_AS_EXECUTED_TOOL_CALLS=False 时使用。
    方案二默认不会走这里，而是把上游结果拼成 assistant.tool_calls 里的 executed tool_call。
    """
    raw = get_upstream_result_raw(row)
    upstream_results = normalize_upstream_results(raw)
    if not upstream_results:
        return ''
    return '以下是当前用户输入相关的上游 Skill/tool 查询结果，已经执行完成。\n这些结果用于补全本轮参数提取，尤其是已选 tool_call 的 arguments.depends_on=True 时。\n请把每项 result 当作真实上游返回结果使用。\n注意：这里的 tool_call_id 只标识上游查询结果，不参与本轮 param_results 的 tool_call_id 对齐；本轮输出仍必须使用 Skill 选择结果中的 tool_call.id。\n\n' + json.dumps(upstream_results, ensure_ascii=False, indent=2)

def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {'true', '1', 'yes', 'y'}

def get_tool_call_arguments_obj(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """安全读取 tool_call.function.arguments 为 dict。"""
    args_raw = tool_call.get('function', {}).get('arguments', '{}')
    if isinstance(args_raw, dict):
        return args_raw
    return parse_json_like(args_raw)

def set_tool_call_arguments_obj(tool_call: Dict[str, Any], args_obj: Dict[str, Any]) -> Dict[str, Any]:
    """把 arguments dict 回写为 JSON 字符串。"""
    fixed = copy.deepcopy(tool_call)
    function_obj = fixed.get('function', {})
    function_obj['arguments'] = json.dumps(args_obj, ensure_ascii=False)
    fixed['function'] = function_obj
    return fixed

def get_original_tool_calls(skill_select_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """原始 skill选择结果中的 tool_call 均视为本轮待提参对象。"""
    return get_tool_calls(skill_select_result)

def build_executed_tool_calls_from_upstream(row: pd.Series) -> List[Dict[str, Any]]:
    """
    把 Excel「上游查询结果」转为 assistant.tool_calls 中的上游事实来源。

    这些 tool_call 只提供已执行结果，不会有对应 Skill.md tool 消息，
    因此不参与本轮 param_results 输出。
    """
    upstream_results = normalize_upstream_results(get_upstream_result_raw(row))
    upstream_tool_calls: List[Dict[str, Any]] = []
    for idx, item in enumerate(upstream_results, start=1):
        tool_call_id = safe_cell(item.get('tool_call_id', '')) or f'UP_{idx:02d}'
        skill_name = safe_cell(item.get('skill_name', '')) or safe_cell(item.get('name', '')) or 'general-query'
        result = item.get('result', item)
        args_obj = {'tool_call_id': tool_call_id, 'content': json.dumps(result, ensure_ascii=False), 'depends_on': 'False'}
        if 'source_content' in item:
            args_obj['source_content'] = item.get('source_content')
        upstream_tool_calls.append({'id': tool_call_id, 'type': 'function', 'function': {'name': skill_name, 'arguments': json.dumps(args_obj, ensure_ascii=False)}})
    return upstream_tool_calls

def attach_upstream_dependency_ids(skill_select_result: Dict[str, Any], upstream_tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    原始待提参 tool_call 不注入 status。
    仅当 depends_on=True 且未提供 depends_on_tool_call_ids 时，
    默认关联本行全部上游事实来源。
    """
    fixed = copy.deepcopy(skill_select_result)
    upstream_ids = [tc.get('id', '') for tc in upstream_tool_calls if tc.get('id', '')]
    new_tool_calls = []
    for tc in get_tool_calls(fixed):
        args_obj = get_tool_call_arguments_obj(tc)
        if _truthy(args_obj.get('depends_on', '')) and upstream_ids:
            args_obj.setdefault('depends_on_tool_call_ids', upstream_ids)
        new_tool_calls.append(set_tool_call_arguments_obj(tc, args_obj))
    fixed['tool_calls'] = new_tool_calls
    return fixed

def merge_upstream_executed_tool_calls(row: pd.Series, skill_select_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成 message 用的 assistant.tool_calls：
    先放上游事实来源，再放原始待提参 tool_call。
    """
    upstream_tool_calls = build_executed_tool_calls_from_upstream(row)
    fixed = attach_upstream_dependency_ids(skill_select_result, upstream_tool_calls)
    if not upstream_tool_calls:
        return fixed
    original_tool_calls = get_tool_calls(fixed)
    fixed['tool_calls'] = upstream_tool_calls + original_tool_calls
    if fixed.get('role') == 'assistant' and fixed.get('content') is None:
        fixed['content'] = ''
    return fixed

def build_flatten_tool_messages_context(original_skill_select_result: Dict[str, Any], skill_md_map: Dict[str, str]) -> str:
    """
    FLATTEN_TOOL_MESSAGES=True 时使用。
    只为原始 skill选择结果中的待提参 tool_call 提供 Skill.md。
    """
    tool_messages = []
    for tc in get_original_tool_calls(original_skill_select_result):
        tool_call_id = tc.get('id', '')
        skill_name = tc.get('function', {}).get('name', '')
        skill_md = skill_md_map.get(skill_name, '')
        tool_messages.append({'role': 'tool', 'tool_call_id': tool_call_id, 'content': skill_md})
    return '以下是本轮待提参 Skill 对应的 tool 消息，content 为对应 Skill.md 正文。\n这些内容原本是 role=tool 的消息，现在为了兼容普通聊天接口，被压缩为 JSON 文本提供。\n只有这里提供了 Skill.md 正文的 tool_call 才需要输出 param_results；其他 assistant.tool_calls 只作为上游事实来源。\n如果同一个 skill 出现多个待提参 tool_call，也会有多条 tool 消息，正文可以相同，但 tool_call_id 不同。\n\n' + json.dumps(tool_messages, ensure_ascii=False, indent=2)

def build_messages(row: pd.Series, system_prompt: str, skill_md_map: Dict[str, str]) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    memory_info = safe_cell(row.get('记忆信息', ''))
    location = safe_cell(row.get('当前位置', ''))
    current_date = safe_cell(row.get('当前日期', ''))
    system_context = f'## 记忆信息：{memory_info}\n## 当前位置：{location}\n## 当前日期：{current_date}'
    messages.append({'role': 'system', 'content': f'{system_prompt}\n{system_context}'})
    for i in range(1, 6):
        q = safe_cell(row.get(f'query{i}', ''))
        a = safe_cell(row.get(f'assistant{i}', ''))
        if q:
            messages.append({'role': 'user', 'content': q})
        if a:
            messages.append({'role': 'assistant', 'content': a})
    current_user_input = safe_cell(row.get('当前用户输入', ''))
    messages.append({'role': 'user', 'content': f'## 当前用户输入\n{current_user_input}'})
    original_skill_select_result = parse_json_like(row.get('skill选择结果', ''))
    original_skill_select_result = inject_tool_call_id_into_arguments(original_skill_select_result)
    if USE_UPSTREAM_AS_EXECUTED_TOOL_CALLS:
        skill_select_result_for_message = merge_upstream_executed_tool_calls(row, original_skill_select_result)
    else:
        upstream_result_context = build_upstream_result_context(row)
        if upstream_result_context:
            messages.append({'role': 'user', 'content': upstream_result_context})
        skill_select_result_for_message = original_skill_select_result
    if FLATTEN_TOOL_MESSAGES:
        messages.append({'role': 'user', 'content': '以下是已经完成的 Skill 选择结果，包含一个或多个 tool_calls。\n这些内容原本是 assistant.tool_calls 消息，现在为了兼容普通聊天接口，被压缩为 JSON 文本提供。\n只有后续提供对应 Skill.md 正文的 tool_call 才是本轮待提参对象；没有 Skill.md 的 tool_call 只作为上游事实来源。\n不要重新选择 Skill，不要修改 tool_call_id、skill_name，不要改变待提参 tool_call 的输出顺序。\n\n' + json.dumps(skill_select_result_for_message, ensure_ascii=False, indent=2)})
    else:
        messages.append(skill_select_result_for_message)
    if FLATTEN_TOOL_MESSAGES:
        messages.append({'role': 'user', 'content': build_flatten_tool_messages_context(original_skill_select_result, skill_md_map)})
    else:
        for tc in get_original_tool_calls(original_skill_select_result):
            tool_call_id = tc.get('id', '')
            skill_name = tc.get('function', {}).get('name', '')
            skill_md = skill_md_map.get(skill_name, '')
            messages.append({'role': 'tool', 'tool_call_id': tool_call_id, 'content': skill_md})
    return messages

def call_llm(messages: List[Dict[str, Any]], model_name: Optional[str]=None, temperature: Optional[float]=None) -> Dict[str, Any]:
    """调用模型，返回 {content, input_tokens, output_tokens, elapsed_time}。

    保留对 MOCK_MODE 的兼容：mock 不返回 usage，按 0 处理。
    """
    start_time = time.time()
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}
    payload = {'model': model_name or MODEL_NAME, 'messages': messages, 'temperature': TEMPERATURE if temperature is None else temperature, 'chat_template_kwargs': {'enable_thinking': False}}
    resp = requests.post(API_BASE_URL, headers=headers, json=payload, timeout=TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f'HTTP {resp.status_code}: {resp.text[:1000]}')
    data = resp.json()
    elapsed_time = time.time() - start_time
    if DEBUG_PRINT_RESPONSE:
        print('========== RAW RESPONSE ==========')
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print('==================================')
    try:
        content = data['choices'][0]['message']['content']
    except Exception as e:
        raise RuntimeError(f'模型返回格式异常: {json.dumps(data, ensure_ascii=False)[:1000]}') from e
    usage = data.get('usage') or {}
    return {'content': content, 'input_tokens': usage.get('prompt_tokens', 0) or 0, 'output_tokens': usage.get('completion_tokens', 0) or 0, 'elapsed_time': round(elapsed_time, 4)}
IOT_JUDGE_SYSTEM_PROMPT = '你是 IOT Control 结果语义评测器。\n你的任务是判断模型提取出的 IOT command 与标准 command 是否表达相同的设备控制意图。\n\n判定原则：\n1. 不要求措辞、语序、标点或句式完全一致，只判断控制语义是否等价。\n2. 必须完整比较每个控制操作的目标设备/对象、动作或状态、模式/参数/数值，以及能改变控制含义的空间或对象限定信息。\n3. 多个控制操作允许合并、拆分或调整表达顺序，只要控制操作集合完全等价。\n4. 同义表达、自然语言改写、简称与完整说法，只要不会改变实际控制结果，可以判为正确。\n5. 如果存在设备或对象错误、动作错误、参数/模式/数值错误、关键限定错误、遗漏控制、额外新增控制，判为错误。\n6. 不因为表达更自然、更简洁或更详细就判错；但新增的细节如果会改变实际执行结果，则判错。\n7. 这里只判断 command 的控制语义，不判断 JSON 格式、tool_call_id、skill_name 等结构问题，这些已由外层规则校验。\n\n最终只能输出严格 JSON：\n正确：{"result":"1","reason":""}\n错误：{"result":"0","reason":"简洁说明不等价之处"}\n禁止输出 Markdown、代码块、解释或其他字段。'

def _extract_iot_command_pairs(expected: Dict[str, Any], actual: Dict[str, Any], skill_select_result: Dict[str, Any]) -> Tuple[bool, List[Dict[str, str]], str]:
    """
    判断当前失败 case 是否适合交给 IOT 语义阅卷。

    只允许“结构完全正确，差异仅可能来自 IOT command 文本”的 case 进入阅卷。
    非 IOT 参数差异、JSON/数量/id/skill_name/字段结构错误都直接保留规则判错。
    """
    if not isinstance(actual, dict):
        return (False, [], 'actual 不是 JSON object')
    expected_results = expected.get('param_results', [])
    actual_results = actual.get('param_results', [])
    tool_calls = get_original_tool_calls(skill_select_result)
    if not isinstance(expected_results, list) or not isinstance(actual_results, list):
        return (False, [], 'param_results 不是数组')
    if not len(expected_results) == len(actual_results) == len(tool_calls):
        return (False, [], '结果数量不一致')
    extra_field_ok, _ = validate_extra_fields(actual_results)
    if not extra_field_ok:
        return (False, [], '字段结构不合法')
    pairs: List[Dict[str, str]] = []
    has_iot_diff = False
    for i, (exp_item, act_item, tc) in enumerate(zip(expected_results, actual_results, tool_calls), start=1):
        expected_id = exp_item.get('tool_call_id')
        actual_id = act_item.get('tool_call_id')
        selected_id = tc.get('id')
        if expected_id != actual_id or expected_id != selected_id:
            return (False, [], f'第{i}项 tool_call_id 不一致')
        expected_skill = exp_item.get('skill_name')
        actual_skill = act_item.get('skill_name')
        selected_skill = tc.get('function', {}).get('name')
        if expected_skill != actual_skill or expected_skill != selected_skill:
            return (False, [], f'第{i}项 skill_name 不一致')
        expected_args = exp_item.get('arguments', {})
        actual_args = act_item.get('arguments', {})
        if not isinstance(expected_args, dict) or not isinstance(actual_args, dict):
            return (False, [], f'第{i}项 arguments 不是对象')
        if expected_skill != 'iot_control_skill':
            if not exact_match(expected_args, actual_args):
                return (False, [], f'第{i}项非 IOT arguments 不一致')
            continue
        expected_command = expected_args.get('command')
        actual_command = actual_args.get('command')
        if not isinstance(expected_command, str) or not isinstance(actual_command, str):
            return (False, [], f'第{i}项 IOT command 缺失或类型错误')
        if expected_command != actual_command:
            has_iot_diff = True
        pairs.append({'tool_call_id': str(expected_id), 'expected_command': expected_command, 'actual_command': actual_command})
    if not pairs:
        return (False, [], '当前 case 没有 IOT 结果')
    if not has_iot_diff:
        return (False, [], 'IOT command 没有文本差异')
    return (True, pairs, '')

def build_iot_judge_messages(row: pd.Series, command_pairs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    current_user_input = safe_cell(row.get('当前用户输入', ''))
    user_payload = {'当前用户输入': current_user_input, '待判定IOT结果': command_pairs}
    return [{'role': 'system', 'content': IOT_JUDGE_SYSTEM_PROMPT}, {'role': 'user', 'content': '请判断以下每组 expected_command 与 actual_command 是否表达完全等价的 IOT 控制意图。只有所有组都语义等价时，整体 result 才能为 1。\n' + json.dumps(user_payload, ensure_ascii=False, indent=2)}]

def parse_iot_judge_output(text: str) -> Tuple[bool, str]:
    obj, error = parse_model_json_output(text)
    if obj is None:
        return (False, f'阅卷输出解析失败: {error}')
    result_value = str(obj.get('result', '')).strip()
    reason = safe_cell(obj.get('reason', ''))
    if result_value == '1':
        return (True, reason)
    if result_value == '0':
        return (False, reason or 'IOT command 语义不等价')
    return (False, f'阅卷 result 非法: {json.dumps(obj, ensure_ascii=False)}')

def run_iot_semantic_judge(row: pd.Series, expected: Dict[str, Any], actual: Dict[str, Any], skill_select_result: Dict[str, Any]) -> Tuple[bool, bool, str]:
    """
    返回：(是否触发阅卷, 阅卷是否通过, 原因)
    """
    candidate, pairs, candidate_reason = _extract_iot_command_pairs(expected=expected, actual=actual, skill_select_result=skill_select_result)
    if not candidate:
        return (False, False, candidate_reason)
    judge_messages = build_iot_judge_messages(row, pairs)
    judge_output = call_llm(judge_messages, model_name=JUDGE_MODEL_NAME, temperature=JUDGE_TEMPERATURE)['content']
    passed, reason = parse_iot_judge_output(judge_output)
    return (True, passed, reason)
ALLOWED_FIELDS = {'iot_control_skill': {'command'}, 'health-register': {'hospital', 'department', 'doctor', 'type', 'startTime', 'endTime'}, 'health_take_medicine_skill': {'medicationList', 'medicationName', 'quantity', 'cron'}, 'remind-create': {'medicationList', 'medicationName', 'quantity', 'cron'}, 'remind_create': {'medicationList', 'medicationName', 'quantity', 'cron'}, 'health_record_generate_skill': {'outpatientRecords', 'outpatientDetails'}}
MEDICINE_SKILLS = {'health_take_medicine_skill', 'remind-create', 'remind_create'}
MEDICATION_LIST_ITEM_FIELDS = {'medicationName', 'quantity', 'cron'}
RECORD_FIELDS = {'hospitalName', 'visitDate', 'doctor', 'department', 'diagnosis'}
DETAIL_FIELDS = {'visitDate', 'doctor', 'department', 'diagnosis', 'medicationName', 'quantity', 'usageDosage', 'labTestReport', 'examinationReport'}

def parse_medication_list_for_validation(value: Any) -> Tuple[Optional[List[Any]], str]:
    """
    校验 medicationList。

    兼容两种形态：
    1. string：JSON.stringify 后的紧凑 JSON 字符串，解析后必须是数组
    2. list：如果后续把 Skill.md 改成 array，这里也能兼容，省得脚本又返工。
    """
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return (None, 'medicationList 是空字符串')
        try:
            parsed = json.loads(s)
        except Exception as e:
            return (None, f'medicationList 不是合法 JSON 字符串: {e}')
        if not isinstance(parsed, list):
            return (None, 'medicationList JSON 解析后不是数组')
        return (parsed, '')
    if isinstance(value, list):
        return (value, '')
    return (None, f'medicationList 类型非法，应为 JSON 字符串或数组，实际为 {type(value).__name__}')

def validate_medication_list_items(medication_list: List[Any], result_index: int, skill_name: str) -> List[str]:
    """检查 medicationList 内部字段。"""
    errors: List[str] = []
    for item_index, med in enumerate(medication_list, start=1):
        if not isinstance(med, dict):
            errors.append(f'第{result_index}个结果 {skill_name}: medicationList 第{item_index}项不是对象')
            continue
        extra = set(med.keys()) - MEDICATION_LIST_ITEM_FIELDS
        if extra:
            errors.append(f'第{result_index}个结果 {skill_name}: medicationList 第{item_index}项多余字段 {sorted(extra)}')
        if 'usageDosage' in med:
            errors.append(f'第{result_index}个结果 {skill_name}: medicationList 第{item_index}项不应输出 usageDosage')
        for field in ['medicationName', 'quantity', 'cron']:
            if field in med and (not isinstance(med[field], str)):
                errors.append(f'第{result_index}个结果 {skill_name}: medicationList 第{item_index}项 {field} 不是字符串')
    return errors

def _normalize_medication_item_for_compare(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    归一化单个药品项，比较时只保留可输出字段，并删除空值。
    字段顺序由 normalize_json 兜底处理。
    """
    normalized: Dict[str, Any] = {}
    for field in ['medicationName', 'quantity', 'cron']:
        if field in item and (not is_empty_value(item.get(field))):
            normalized[field] = item.get(field)
    return normalized

def normalize_medicine_arguments_for_compare(args: Any) -> Any:
    """
    吃药提醒新旧结构兼容比较。

    旧结构：{"medicationName":"A","quantity":"1粒","cron":"0 21 * * *"}
    新结构：{"medicationList":[{"medicationName":"A","quantity":"1粒","cron":"0 21 * * *"}]}
    或：   {"medicationList":"[{"medicationName":"A",...}]"}

    比较时统一转成：{"medicationList":[...]}。
    这样旧用例期望和新版模型输出不会因为字段形态不同而假失败。
    真是谢天谢地，字段迁移终于不用靠空格审判了。
    """
    if not isinstance(args, dict):
        return args
    if 'medicationList' in args:
        med_list = parse_medication_list_for_compare(args.get('medicationList'))
        if isinstance(med_list, list):
            normalized_list = []
            for item in med_list:
                if isinstance(item, dict):
                    normalized_list.append(_normalize_medication_item_for_compare(item))
                else:
                    normalized_list.append(item)
            return {'medicationList': normalized_list}
        return {'medicationList': med_list}
    old_item = {}
    for field in ['medicationName', 'quantity', 'cron']:
        if field in args and (not is_empty_value(args.get(field))):
            old_item[field] = args.get(field)
    if old_item:
        return {'medicationList': [_normalize_medication_item_for_compare(old_item)]}
    return args

def normalize_arguments_for_compare_by_skill(skill_name: str, args: Any) -> Any:
    """按 skill 类型归一化 arguments，用于评测比较，不改变原始模型输出。"""
    if skill_name in MEDICINE_SKILLS:
        return normalize_medicine_arguments_for_compare(args)
    return args

def validate_extra_fields(actual_results: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    检查是否输出了 Skill.md 未定义字段。
    包括健康档案的嵌套字段。
    """
    errors = []
    for idx, item in enumerate(actual_results):
        skill_name = item.get('skill_name', '')
        args = item.get('arguments', {})
        if not isinstance(args, dict):
            errors.append(f'第{idx + 1}个结果 {skill_name}: arguments 不是对象')
            continue
        allowed = ALLOWED_FIELDS.get(skill_name)
        if allowed is None:
            errors.append(f'第{idx + 1}个结果: 未知 skill_name {skill_name}')
            continue
        extra = set(args.keys()) - allowed
        if extra:
            errors.append(f'第{idx + 1}个结果 {skill_name}: 多余字段 {sorted(extra)}')
        if skill_name == 'iot_control_skill':
            if 'command' in args and (not isinstance(args['command'], str)):
                errors.append(f'第{idx + 1}个结果 iot_control_skill: command 不是字符串')
        if skill_name == 'health-register':
            if 'type' in args and args['type'] not in {'1', '2'}:
                errors.append(f"第{idx + 1}个结果 health-register: type 非法 {args['type']}")
            has_start = 'startTime' in args
            has_end = 'endTime' in args
            if has_start != has_end:
                errors.append(f'第{idx + 1}个结果 health-register: startTime/endTime 未成对')
        if skill_name in MEDICINE_SKILLS:
            if 'usageDosage' in args:
                errors.append(f'第{idx + 1}个结果 {skill_name}: 不应输出 usageDosage')
            if 'cron' in args and (not isinstance(args['cron'], str)):
                errors.append(f'第{idx + 1}个结果 {skill_name}: cron 不是字符串')
            if 'medicationList' in args:
                medication_list, medication_list_error = parse_medication_list_for_validation(args['medicationList'])
                if medication_list_error:
                    errors.append(f'第{idx + 1}个结果 {skill_name}: {medication_list_error}')
                else:
                    errors.extend(validate_medication_list_items(medication_list=medication_list or [], result_index=idx + 1, skill_name=skill_name))
                mixed_old_fields = {'medicationName', 'quantity', 'cron'} & set(args.keys())
                if mixed_old_fields:
                    errors.append(f'第{idx + 1}个结果 {skill_name}: 已输出 medicationList，不应同时输出顶层旧字段 {sorted(mixed_old_fields)}')
        if skill_name == 'health_record_generate_skill':
            records = args.get('outpatientRecords', [])
            details = args.get('outpatientDetails', [])
            if 'outpatientRecords' in args and (not isinstance(records, list)):
                errors.append(f'第{idx + 1}个结果 health_record_generate_skill: outpatientRecords 不是数组')
            if 'outpatientDetails' in args and (not isinstance(details, list)):
                errors.append(f'第{idx + 1}个结果 health_record_generate_skill: outpatientDetails 不是数组')
            if isinstance(records, list):
                for r_i, record in enumerate(records, start=1):
                    if not isinstance(record, dict):
                        errors.append(f'第{idx + 1}个结果 outpatientRecords 第{r_i}项不是对象')
                        continue
                    record_extra = set(record.keys()) - RECORD_FIELDS
                    if record_extra:
                        errors.append(f'第{idx + 1}个结果 outpatientRecords 第{r_i}项多余字段 {sorted(record_extra)}')
            if isinstance(details, list):
                for d_i, detail in enumerate(details, start=1):
                    if not isinstance(detail, dict):
                        errors.append(f'第{idx + 1}个结果 outpatientDetails 第{d_i}项不是对象')
                        continue
                    detail_extra = set(detail.keys()) - DETAIL_FIELDS
                    if detail_extra:
                        errors.append(f'第{idx + 1}个结果 outpatientDetails 第{d_i}项多余字段 {sorted(detail_extra)}')
    return (len(errors) == 0, errors)
_MISSING = object()

def is_empty_value(value: Any) -> bool:
    """
    判断一个值在业务语义上是否等价于“空”。

    这里故意把以下情况都视为空：
    1. None
    2. 空字符串 / 纯空白字符串
    3. 空数组 / 数组内元素全为空
    4. 空对象 / 对象内所有字段值全为空

    这样可以支持：
    expected arguments = {}
    actual arguments = {"outpatientRecords": [], "outpatientDetails": []}
    在宽松判定下认为一致。
    """
    if value is _MISSING:
        return True
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    if isinstance(value, (list, tuple, set)):
        return all((is_empty_value(item) for item in value))
    if isinstance(value, dict):
        return all((is_empty_value(v) for v in value.values()))
    return False

def json_value(value: Any) -> str:
    """把差异值转成稳定可读的字符串，方便写 error_reason。"""
    if value is _MISSING:
        return '<缺失>'
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return repr(value)

def build_json_diff(expected_value: Any, actual_value: Any, path: str, loose: bool=False) -> List[str]:
    """
    递归生成 JSON 差异说明。

    loose=False：严格比较，缺字段、空数组、空对象都会如实报差异。
    loose=True：缺失字段 和 空值字段 视为等价，不再报错。
    """
    if path.endswith('.medicationList'):
        expected_value = normalize_json(parse_medication_list_for_compare(expected_value))
        actual_value = normalize_json(parse_medication_list_for_compare(actual_value))
    if exact_match(expected_value, actual_value):
        return []
    if loose and is_empty_value(expected_value) and is_empty_value(actual_value):
        return []
    diffs: List[str] = []
    if expected_value is _MISSING:
        if loose and is_empty_value(actual_value):
            return []
        empty_tip = '（实际值为空，宽松判定可接受）' if is_empty_value(actual_value) else ''
        return [f'{path}：实际多输出字段，actual={json_value(actual_value)}{empty_tip}']
    if actual_value is _MISSING:
        if loose and is_empty_value(expected_value):
            return []
        empty_tip = '（期望值为空，宽松判定可接受）' if is_empty_value(expected_value) else ''
        return [f'{path}：缺失参数，expected={json_value(expected_value)}{empty_tip}']
    if isinstance(expected_value, dict) and isinstance(actual_value, dict):
        keys = sorted(set(expected_value.keys()) | set(actual_value.keys()))
        for key in keys:
            next_expected = expected_value.get(key, _MISSING)
            next_actual = actual_value.get(key, _MISSING)
            diffs.extend(build_json_diff(next_expected, next_actual, f'{path}.{key}', loose=loose))
        return diffs
    if isinstance(expected_value, list) and isinstance(actual_value, list):
        common_len = min(len(expected_value), len(actual_value))
        for i in range(common_len):
            diffs.extend(build_json_diff(expected_value[i], actual_value[i], f'{path}[{i}]', loose=loose))
        if len(expected_value) > len(actual_value):
            for i in range(common_len, len(expected_value)):
                missing_expected_item = expected_value[i]
                if loose and is_empty_value(missing_expected_item):
                    continue
                diffs.append(f'{path}[{i}]：缺失数组项，expected={json_value(missing_expected_item)}')
        if len(actual_value) > len(expected_value):
            for i in range(common_len, len(actual_value)):
                extra_actual_item = actual_value[i]
                if loose and is_empty_value(extra_actual_item):
                    continue
                diffs.append(f'{path}[{i}]：实际多输出数组项，actual={json_value(extra_actual_item)}')
        return diffs
    if type(expected_value) is not type(actual_value):
        if loose and is_empty_value(expected_value) and is_empty_value(actual_value):
            return []
        return [f'{path}：类型不一致，expected_type={type(expected_value).__name__}，actual_type={type(actual_value).__name__}，expected={json_value(expected_value)}，actual={json_value(actual_value)}']
    return [f'{path}：值不一致，expected={json_value(expected_value)}，actual={json_value(actual_value)}']

def validate_output_structure(expected: Dict[str, Any], actual: Optional[Dict[str, Any]], skill_select_result: Dict[str, Any], parse_error: str='') -> Dict[str, Any]:
    """
    校验 JSON 结构、tool_call_id、skill_name、arguments 和字段合法性。
    中间判断只在函数内部使用，不再展开成 Excel 列；所有失败原因统一写入 error_reason。
    """
    result = {'是否通过': False, '判定结果': '不通过', '是否宽松通过': False, '宽松判定结果': '不通过', 'error_reason': '', 'loose_error_reason': ''}
    if actual is None:
        reason = parse_error or '模型输出为空或 JSON 解析失败'
        result['error_reason'] = reason
        result['loose_error_reason'] = reason
        return result
    if 'param_results' not in actual or not isinstance(actual['param_results'], list):
        reason = 'actual 缺少 param_results 数组'
        result['error_reason'] = reason
        result['loose_error_reason'] = reason
        return result
    expected_results = expected.get('param_results', [])
    actual_results = actual.get('param_results', [])
    tool_calls = get_original_tool_calls(skill_select_result)
    expected_count = len(expected_results)
    actual_count = len(actual_results)
    selected_count = len(tool_calls)
    result_count_match = expected_count == actual_count == selected_count
    compare_len = min(expected_count, actual_count, selected_count)
    expected_results_part = expected_results[:compare_len]
    actual_results_part = actual_results[:compare_len]
    tool_calls_part = tool_calls[:compare_len]
    expected_ids = [x.get('tool_call_id') for x in expected_results_part]
    actual_ids = [x.get('tool_call_id') for x in actual_results_part]
    selected_ids = [x.get('id') for x in tool_calls_part]
    tool_call_id_match = expected_ids == actual_ids == selected_ids
    expected_skill_names = [x.get('skill_name') for x in expected_results_part]
    actual_skill_names = [x.get('skill_name') for x in actual_results_part]
    selected_skill_names = [x.get('function', {}).get('name') for x in tool_calls_part]
    skill_name_match = expected_skill_names == actual_skill_names == selected_skill_names
    argument_errors: List[str] = []
    loose_argument_errors: List[str] = []
    for i in range(compare_len):
        expected_args_raw = expected_results_part[i].get('arguments', {})
        actual_args_raw = actual_results_part[i].get('arguments', {})
        skill_name_for_compare = expected_results_part[i].get('skill_name') or actual_results_part[i].get('skill_name', '')
        expected_args = normalize_arguments_for_compare_by_skill(skill_name_for_compare, expected_args_raw)
        actual_args = normalize_arguments_for_compare_by_skill(skill_name_for_compare, actual_args_raw)
        path = f'第{i + 1}个结果.arguments'
        argument_errors.extend(build_json_diff(expected_args, actual_args, path=path, loose=False))
        loose_argument_errors.extend(build_json_diff(expected_args, actual_args, path=path, loose=True))
    arguments_match = len(argument_errors) == 0
    arguments_loose_match = len(loose_argument_errors) == 0
    extra_field_ok, extra_errors = validate_extra_fields(actual_results)
    errors: List[str] = []
    loose_errors: List[str] = []
    if not result_count_match:
        msg = f'param_results 数量不匹配；expected={expected_count}；actual={actual_count}；selected_tool_calls={selected_count}'
        errors.append(msg)
        loose_errors.append(msg)
    if not tool_call_id_match:
        msg = f'tool_call_id 不匹配；expected={expected_ids}；actual={actual_ids}；selected={selected_ids}'
        errors.append(msg)
        loose_errors.append(msg)
    if not skill_name_match:
        msg = f'skill_name 不匹配；expected={expected_skill_names}；actual={actual_skill_names}；selected={selected_skill_names}'
        errors.append(msg)
        loose_errors.append(msg)
    if not arguments_match:
        errors.extend(argument_errors)
    if not arguments_loose_match:
        loose_errors.extend(loose_argument_errors)
    if not extra_field_ok:
        errors.extend(extra_errors)
        loose_errors.extend(extra_errors)
    result['error_reason'] = '；'.join(errors)
    result['loose_error_reason'] = '；'.join(loose_errors)
    result['是否通过'] = bool(result_count_match and tool_call_id_match and skill_name_match and arguments_match and extra_field_ok)
    result['是否宽松通过'] = bool(result_count_match and tool_call_id_match and skill_name_match and arguments_loose_match and extra_field_ok)
    result['判定结果'] = '通过' if result['是否通过'] else '不通过'
    result['宽松判定结果'] = '通过' if result['是否宽松通过'] else '不通过'
    return result

def process_one_case(index: int, row: pd.Series, system_prompt: str, skill_md_map: Dict[str, str]) -> Dict[str, Any]:
    case_id = safe_cell(row.get('case_id', f'row_{index}'))
    output_record = row.to_dict()
    output_record['row_index'] = index
    output_record['case_id'] = case_id
    try:
        messages = build_messages(row, system_prompt, skill_md_map)
        expected = parse_json_like(row.get('期望输出', ''))
        skill_select_result = parse_json_like(row.get('skill选择结果', ''))
        skill_select_result = inject_tool_call_id_into_arguments(skill_select_result)
        input_tokens = 0
        output_tokens = 0
        model_elapsed_time = 0.0
        if MOCK_MODE:
            model_output = json.dumps(expected, ensure_ascii=False)
        else:
            if DEBUG_PRINT_MESSAGES:
                print('\n========== DEBUG MESSAGES ==========')
                print(json.dumps(messages, ensure_ascii=False, indent=2))
                print('message 数量:', len(messages))
                print('总字符数:', sum((len(str(m.get('content', ''))) for m in messages if isinstance(m, dict))))
                print('====================================\n')
            llm_result = call_llm(messages)
            model_output = llm_result['content']
            input_tokens = llm_result.get('input_tokens', 0)
            output_tokens = llm_result.get('output_tokens', 0)
            model_elapsed_time = llm_result.get('elapsed_time', 0.0)
        if PRINT_MODEL_OUTPUT:
            print(f'\n[{case_id}] 模型输出：')
            print(model_output)
        actual, parse_error = parse_model_json_output(model_output)
        eval_result = validate_output_structure(expected=expected, actual=actual, skill_select_result=skill_select_result, parse_error=parse_error)
        if ENABLE_IOT_SEMANTIC_JUDGE and (not eval_result.get('是否通过', False)) and (actual is not None):
            judge_triggered, judge_passed, judge_reason = run_iot_semantic_judge(row=row, expected=expected, actual=actual, skill_select_result=skill_select_result)
            if judge_triggered and judge_passed:
                eval_result['是否通过'] = True
                eval_result['判定结果'] = '通过（IOT语义阅卷）'
                eval_result['是否宽松通过'] = True
                eval_result['宽松判定结果'] = '通过（IOT语义阅卷）'
                eval_result['error_reason'] = ''
                eval_result['loose_error_reason'] = ''
            elif judge_triggered and (not judge_passed):
                judge_msg = f'IOT语义阅卷不通过: {judge_reason}'
                old_error = eval_result.get('error_reason', '')
                old_loose_error = eval_result.get('loose_error_reason', '')
                eval_result['error_reason'] = (old_error + '；' + judge_msg).strip('；')
                eval_result['loose_error_reason'] = (old_loose_error + '；' + judge_msg).strip('；')
        output_record['messages'] = json.dumps(messages, ensure_ascii=False)
        output_record['model_output'] = model_output
        output_record['model_json'] = json.dumps(actual, ensure_ascii=False) if actual is not None else ''
        output_record['input_tokens'] = input_tokens
        output_record['output_tokens'] = output_tokens
        output_record['total_tokens'] = input_tokens + output_tokens
        output_record['model_elapsed_time'] = model_elapsed_time
        output_record.update(eval_result)
    except Exception as e:
        output_record['messages'] = output_record.get('messages', '')
        output_record['model_output'] = output_record.get('model_output', '')
        output_record['model_json'] = ''
        output_record['input_tokens'] = 0
        output_record['output_tokens'] = 0
        output_record['total_tokens'] = 0
        output_record['model_elapsed_time'] = 0.0
        output_record['是否通过'] = False
        output_record['判定结果'] = '不通过'
        output_record['是否宽松通过'] = False
        output_record['宽松判定结果'] = '不通过'
        output_record['error_reason'] = f'脚本异常: {e}'
        output_record['loose_error_reason'] = f'脚本异常: {e}'
        output_record['traceback'] = traceback.format_exc()
    return output_record

def main():
    start_time = time.time()
    print('读取 system prompt...')
    system_prompt = sp.SYS_PROMPT
    print(f'system prompt读取成功:{system_prompt}')
    print('读取 Skill.md...')
    skill_md_map = {skill_name: read_text(path) for skill_name, path in SKILL_MD_PATH_MAP.items()}
    print('读取 Excel...')
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, dtype=str)
    if LIMIT is not None:
        df = df.head(LIMIT).copy()
    print(f'准备测试用例数: {len(df)}')
    print(f'MOCK_MODE: {MOCK_MODE}')
    print(f'FLATTEN_TOOL_MESSAGES: {FLATTEN_TOOL_MESSAGES}')
    print(f'MAX_WORKERS: {MAX_WORKERS}')
    if SAVE_JSONL_EVERY_CASE:
        jsonl_path = Path(JSONL_LOG_PATH)
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        if jsonl_path.exists():
            jsonl_path.unlink()
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for index, row in df.iterrows():
            futures.append(executor.submit(process_one_case, index, row, system_prompt, skill_md_map))
        for i, future in enumerate(as_completed(futures), start=1):
            record = future.result()
            results.append(record)
            if SAVE_JSONL_EVERY_CASE:
                jsonl_path = Path(JSONL_LOG_PATH)
                with jsonl_path.open('a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            case_id = record.get('case_id', '')
            passed = record.get('是否通过', False)
            result_text = record.get('判定结果', '未知')
            error_reason = record.get('error_reason', '')
            if PRINT_EACH_RESULT:
                print(f'[{i}/{len(futures)}] {case_id} - {result_text}')
            if PRINT_FAILED_DETAIL and (not passed):
                print(f'  失败原因: {error_reason}')
                parse_error = record.get('parse_error', '')
                if parse_error:
                    print(f'  解析错误: {parse_error}')
                model_output = record.get('model_output', '')
                if model_output:
                    print(f'  模型输出: {str(model_output)[:500]}')
                traceback_text = record.get('traceback', '')
                if traceback_text:
                    print(f'  traceback: {traceback_text[:1000]}')
            if not PRINT_EACH_RESULT and (i % 10 == 0 or i == len(futures)):
                print(f'已完成 {i}/{len(futures)}')
    result_df = pd.DataFrame(results)
    if 'row_index' in result_df.columns:
        result_df = result_df.sort_values(by='row_index').reset_index(drop=True)
    total = len(result_df)
    pass_ok = int(result_df['是否通过'].fillna(False).sum()) if total else 0
    loose_pass_ok = int(result_df['是否宽松通过'].fillna(False).sum()) if total else 0
    summary = pd.DataFrame([{'指标': '总用例数', '值': total}, {'指标': '严格通过数', '值': pass_ok}, {'指标': '严格通过率', '值': pass_ok / total if total else 0}, {'指标': '宽松通过数', '值': loose_pass_ok}, {'指标': '宽松通过率', '值': loose_pass_ok / total if total else 0}])
    group_sheets = {}
    for col in ['意图数量', 'tool_call结构', '信息来源', '参数完整度', '场景覆盖', '叶子维度ID']:
        if col in result_df.columns:
            gdf = result_df.groupby(col, dropna=False).agg(总数=('case_id', 'count'), 严格通过数=('是否通过', 'sum'), 宽松通过数=('是否宽松通过', 'sum')).reset_index()
            gdf['严格通过率'] = gdf['严格通过数'] / gdf['总数']
            gdf['宽松通过率'] = gdf['宽松通过数'] / gdf['总数']
            group_sheets[col] = gdf
    print('写出结果 Excel...')
    output_path = Path(OUTPUT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        result_df.to_excel(writer, sheet_name='明细结果', index=False)
        summary.to_excel(writer, sheet_name='总体统计', index=False)
        for col, gdf in group_sheets.items():
            sheet_name = f'按{col}统计'
            sheet_name = sheet_name[:31]
            gdf.to_excel(writer, sheet_name=sheet_name, index=False)
    cost = time.time() - start_time
    print('完成。')
    print(f'输出文件: {output_path}')
    print(f'总用例数: {total}')
    print(f'严格通过率: {(pass_ok / total if total else 0):.2%}')
    print(f'宽松通过率: {(loose_pass_ok / total if total else 0):.2%}')
    print(f'耗时: {cost:.2f}s')
