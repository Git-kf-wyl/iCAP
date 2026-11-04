# Private iCAP Yellow business implementation. Do not publish.
"""
改写结果对比 + GPT 复核模块

可作为模块调用：

    import compare

    result = compare.compare_intents(
        OUTPUT_XLSX,
        INPUT_FILE,
        col_name="model_response",
        output_file="对比结果.xlsx",
    )

处理逻辑：
1. 解析测试结果与标准答案中的 {"意图":"..."}；
2. 归一化后完全一致，直接判定正确；
3. 不一致时，调用 GPT 结合上下文进行复核；
4. GPT 输出“正确/错误 + 原因”；
5. 生成对比详情、总体准确率汇总和按标签准确率统计。
"""
from __future__ import annotations
import ast
import json
import re
import time
from pathlib import Path
from typing import Any
import pandas as pd
import requests
import urllib3
DEFAULT_GPT_API_URL = 'http://127.0.0.1:1/unconfigured'
DEFAULT_GPT_API_KEY = ''
DEFAULT_GPT_MODEL = 'gpt-5.6-sol'
PROXIES = {'http': '', 'https': ''}
DEFAULT_PROXIES = None
DEFAULT_VERIFY_SSL = False
DEFAULT_REQUEST_TIMEOUT_SECONDS = 180
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_SECONDS = 2
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
REWRITE_CORE_RULES = '上下文改写器的核心职责：\n\n1. 指代消解：\n   当前用户输入包含依赖上下文的“他、她、它、这个、那个、前者、后者、第几个”等指代时，\n   仅在上下文存在唯一明确对象的情况下，将其替换为明确对象。\n\n2. 主题补全：\n   当前用户输入缺少独立理解所必需的对象、主题或条件时，\n   根据上下文补充最少且必要的信息。\n\n3. 不改写：\n   当前用户输入本身完整清晰时，应保持原意，不得强行继承历史条件。\n\n4. 最小改写：\n   只补充理解所必需的信息，不回答用户问题，不总结、不润色、不纠错、不扩写，\n   不擅自添加历史中不相关、已失效或用户未明确保留的条件。\n\n5. 当前输入优先：\n   当前用户输入出现新的对象、地点、时间或条件时，优先采用当前输入，\n   不得把新旧同类条件同时保留。\n\n6. 结果应能脱离上下文独立理解，同时不得改变用户原始诉求。\n\n标准答案是重要参考，但不要求实际结果与标准答案逐字一致。\n如果实际结果与标准答案表达不同，但语义等价且符合上述规则，可以判定为正确。\n'
GPT_JUDGE_SYSTEM_PROMPT = '你是“上下文改写结果评审器”。\n\n你的任务是判断“实际改写结果”是否正确。\n请结合历史上下文、当前用户输入、标准答案以及改写器核心规则进行判断。\n\n## 改写器核心目标\n改写器的目标是：在不回答用户问题的前提下，将当前用户输入改写为能脱离上下文独立理解的表达。\n\n它主要完成以下三类任务：\n1. 指代消解：将“他、她、它、这个、那个、前者、后者、第几个”等依赖上下文的指代表达替换为明确对象。\n2. 主题补全：当当前用户输入缺少独立理解所必需的主题、对象、条件或锚点时，根据上下文补充必要信息。\n3. 不改写：当当前用户输入本身已经完整清晰时，可保持原意，不必强行补充或改写。\n\n## 判分原则\n你判断“实际改写结果”是否正确时，核心看以下几点：\n\n1. 是否符合用户原始意图\n- 改写后必须忠实表达用户原始诉求，不得改变意图。\n\n2. 是否保留了关键信息\n- 不得遗漏用户原输入中的关键信息。\n- 不得遗漏理解当前意图所必需的上下文信息。\n\n3. 是否完成了必要改写\n- 能做指代消解的，是否完成了指代消解；\n- 能做主题补全的，是否完成了主题补全；\n- 不需要改写的，是否保持了用户原意。\n\n4. 是否允许表达形式变化\n以下情况即使与标准答案不完全一致，也可以判定为“正确”：\n- 语序调整，但语义不变；\n- 句式压缩或改写为更适合检索的短语，只要核心意图完整保留；\n- 对明显口语病句、重复字词、轻微不通顺表达做了自然修正；\n- 增删了不影响意图的语气词、衔接词、赘余表达；\n- 与标准答案不完全同形，但语义等价、信息完整。\n\n5. 哪些情况应判为错误\n以下情况应判定为“错误”：\n- 改变了用户原意；\n- 丢失了用户输入中的关键信息；\n- 丢失了理解意图所必需的上下文信息；\n- 本应完成指代消解却没有完成；\n- 本应完成主题补全却没有完成；\n- 继承了不该继承的历史信息；\n- 擅自添加了用户未表达、上下文也无必要支持的新信息；\n- 过度扩写、错误纠错、错误概括，导致结果偏离用户意图。\n\n## 特别说明\n- 标准答案只是参考答案，不要求实际结果与标准答案逐字一致。\n- 只要实际结果语义等价、信息完整、符合用户意图，即可判定为“正确”。\n- 不要因为语序不同、表达更简洁、句式更自然、病句轻微修正，就判为错误。\n- “最小改写”不等于“逐字尽量不动”；只要不改变意图、不丢失信息、完成必要改写，即可视为合理。\n\n## 示例判断倾向\n1.\n当前用户输入：帮我生成一张图片，然后关于我们家过年吃饺子的。\n实际结果：帮我生成一张关于我们家过年吃饺子的图片。\n标准答案：帮我生成一张图片，然后关于我们家过年吃饺子的。\n应判定：正确\n原因：只是语序调整，语义未变，未丢失信息。\n\n2.\n当前用户输入：你再介绍一下他的演艺生涯。\n上下文可确定“他”是黄晓明。\n实际结果：黄晓明演艺生涯\n标准答案：你再介绍一下黄晓明的演艺生涯。\n应判定：正确\n原因：已完成指代消解，核心检索意图完整保留，表达压缩但语义等价。\n\n3.\n当前用户输入：我不要要烦恼\n实际结果：我不要烦恼\n应判定：正确\n原因：属于轻微病句/重复词修正，未改变原意。\n\n## 输出要求\n只能输出严格 JSON，禁止输出 Markdown 代码块或额外文字。\n\n输出格式：\n{"是否正确":"正确","原因":"一句话说明判断依据"}\n\n或：\n{"是否正确":"错误","原因":"一句话说明主要问题"}\n'

def normalize_cell(value: Any) -> str:
    if value is None:
        return ''
    try:
        is_na = pd.isna(value)
        if isinstance(is_na, bool) and is_na:
            return ''
    except (TypeError, ValueError):
        pass
    return str(value).strip()

def remove_punctuation(text: str) -> str:
    """去除中英文标点和空白，并统一为小写。"""
    text = re.sub('[^\\w\\s]', '', text)
    text = re.sub('\\s+', '', text)
    return text.lower()

def parse_json_like(value: Any) -> Any:
    """兼容标准 JSON、二次编码 JSON 和 Python 字面量。"""
    if isinstance(value, (list, dict)):
        return value
    text = normalize_cell(value)
    if not text:
        return None
    current: Any = text
    for _ in range(3):
        if not isinstance(current, str):
            break
        candidate = current.strip()
        candidate = re.sub('^```(?:json|text)?\\s*', '', candidate, flags=re.IGNORECASE)
        candidate = re.sub('\\s*```$', '', candidate).strip()
        try:
            current = json.loads(candidate)
            continue
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            current = ast.literal_eval(candidate)
            continue
        except (ValueError, SyntaxError):
            break
    return current

def extract_intent(cell_value: Any) -> tuple[bool, str | None]:
    """
    从单元格提取 {"意图":"..."} 中的意图。
    返回：(是否成功, 意图值)
    """
    parsed = parse_json_like(cell_value)
    if not isinstance(parsed, dict) or '意图' not in parsed:
        return (False, None)
    intent = parsed.get('意图')
    if not isinstance(intent, str):
        return (False, None)
    intent = intent.strip()
    if not intent:
        return (False, None)
    return (True, intent)

def strip_current_query_wrapper(text: str) -> str:
    value = normalize_cell(text)
    patterns = ['^\\s*#+\\s*当前用户输入\\s*[:：]?\\s*', '^\\s*当前用户输入\\s*[:：]\\s*']
    for pattern in patterns:
        value = re.sub(pattern, '', value, flags=re.IGNORECASE)
    return value.strip()

def normalize_for_query_match(text: str) -> str:
    value = strip_current_query_wrapper(text)
    value = re.sub('\\s+', '', value)
    value = value.strip('。！？!?，,；;：:')
    return value

def build_history_context(full_context_value: Any, original_query: str) -> str:
    """
    从 full_context_json 中：
    - 删除 role=system；
    - 删除与 original_query 重复的最后一条当前用户输入；
    - 其余消息按原顺序保留。
    """
    parsed = parse_json_like(full_context_value)
    if isinstance(parsed, dict):
        for key in ('messages', 'context', 'conversation', 'full_context_json'):
            if isinstance(parsed.get(key), list):
                parsed = parsed[key]
                break
    if not isinstance(parsed, list):
        raw = normalize_cell(full_context_value)
        return raw if raw else '（无历史上下文）'
    messages = [item for item in parsed if isinstance(item, dict)]
    original_normalized = normalize_for_query_match(original_query)
    remove_index: int | None = None
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if normalize_cell(message.get('role')).lower() != 'user':
            continue
        content = normalize_cell(message.get('content'))
        content_normalized = normalize_for_query_match(content)
        has_marker = bool(re.search('#+\\s*当前用户输入|当前用户输入\\s*[:：]', content))
        same_as_original = bool(original_normalized and content_normalized == original_normalized)
        if has_marker or same_as_original:
            remove_index = index
            break
    lines: list[str] = []
    for index, message in enumerate(messages):
        role = normalize_cell(message.get('role')).lower()
        if role == 'system':
            continue
        if remove_index is not None and index == remove_index:
            continue
        content = normalize_cell(message.get('content'))
        if not content:
            content = '（空内容）'
        lines.append(f"[{role or 'unknown'}]\n{content}")
    return '\n\n'.join(lines) if lines else '（无历史上下文）'

def resolve_query_placeholder(intent: str, original_query: str, enabled: bool) -> str:
    if enabled and intent.strip() in {'Query', '【Query】', '__QUERY__'}:
        return original_query.strip()
    return intent.strip()

def build_gpt_user_prompt(history_context: str, original_query: str, actual_response: str, expected_answer: str, actual_intent: str, expected_intent: str) -> str:
    return f'## 历史上下文\n{history_context}\n\n## 当前用户输入\n{original_query}\n\n## 实际模型输出原文\n{actual_response}\n\n## 实际改写意图\n{actual_intent}\n\n## 标准答案原文\n{expected_answer}\n\n## 标准答案意图\n{expected_intent}\n\n## 任务\n判断实际改写结果是否正确。\n请严格按照指定 JSON 格式输出“是否正确”和“原因”。\n'

def parse_gpt_judgement(raw_text: str) -> tuple[bool, str, str]:
    """
    返回：
    - 是否解析成功
    - 是否正确：正确 / 错误
    - 原因
    """
    parsed = parse_json_like(raw_text)
    if not isinstance(parsed, dict):
        return (False, '', '')
    verdict = normalize_cell(parsed.get('是否正确') or parsed.get('正确与否') or parsed.get('result'))
    reason = normalize_cell(parsed.get('原因') or parsed.get('reason'))
    verdict_mapping = {'正确': '正确', '是': '正确', 'true': '正确', 'True': '正确', '错误': '错误', '不正确': '错误', '否': '错误', 'false': '错误', 'False': '错误'}
    normalized_verdict = verdict_mapping.get(verdict)
    if normalized_verdict and reason:
        return (True, normalized_verdict, reason)
    return (False, '', '')

def request_gpt_judgement(user_prompt: str, *, gpt_api_url: str, gpt_api_key: str, gpt_model: str, proxies: dict[str, str] | None, verify_ssl: bool, request_timeout_seconds: int, max_retries: int, retry_base_seconds: int, log_fn=print) -> tuple[str, str, str]:
    """
    返回：
    - GPT 复核结果：正确 / 错误 / 调用失败
    - 原因
    - 原始输出
    """
    headers = {'Authorization': f'Bearer {gpt_api_key}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
    payload = {'model': gpt_model, 'messages': [{'role': 'system', 'content': GPT_JUDGE_SYSTEM_PROMPT}, {'role': 'user', 'content': user_prompt}]}
    last_error = ''
    last_raw = ''
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request('POST', gpt_api_url, json=payload, headers=headers, verify=verify_ssl, proxies=PROXIES, timeout=request_timeout_seconds)
            response_text = response.text or ''
            log_fn(response_text)
            content_type = response.headers.get('Content-Type', '')
            request_id = response.headers.get('x-request-id') or response.headers.get('request-id') or response.headers.get('x-trace-id') or ''
            if not response.ok:
                error_message = f'HTTP {response.status_code}；Content-Type={content_type!r}；request-id={request_id!r}；响应前500字={response_text[:500]!r}'
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    return ('调用失败', error_message, response_text)
                raise RuntimeError(error_message)
            if not response_text.strip():
                raise ValueError(f'接口返回空响应体；HTTP {response.status_code}；Content-Type={content_type!r}；request-id={request_id!r}')
            try:
                data = response.json()
            except (requests.exceptions.JSONDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f'接口响应不是合法 JSON；HTTP {response.status_code}；Content-Type={content_type!r}；request-id={request_id!r}；响应前500字={response_text[:500]!r}') from exc
            if not isinstance(data, dict):
                raise ValueError(f'接口 JSON 顶层不是对象；实际类型={type(data).__name__}；响应前500字={response_text[:500]!r}')
            choices = data.get('choices') or []
            if not choices:
                raise ValueError(f'响应中没有 choices；HTTP {response.status_code}；request-id={request_id!r}；响应前500字={response_text[:500]!r}')
            message = choices[0].get('message') or {}
            raw_output = normalize_cell(message.get('content'))
            last_raw = raw_output
            if not raw_output:
                finish_reason = choices[0].get('finish_reason')
                reasoning_content = normalize_cell(message.get('reasoning_content'))
                raise ValueError(f'GPT 返回空 content；finish_reason={finish_reason!r}；reasoning_content前200字={reasoning_content[:200]!r}；request-id={request_id!r}')
            success, verdict, reason = parse_gpt_judgement(raw_output)
            if success:
                return (verdict, reason, raw_output)
            raise ValueError(f'GPT 返回格式无法解析：{raw_output!r}')
        except Exception as exc:
            last_error = str(exc)
            if attempt < max_retries:
                wait_seconds = retry_base_seconds * attempt
                log_fn(f'    GPT 第 {attempt}/{max_retries} 次调用失败，{wait_seconds} 秒后重试：{exc}')
                time.sleep(wait_seconds)
    return ('调用失败', last_error, last_raw)

def compare_intents(test_file: str | Path, answer_file: str | Path, col_name: str='model_response', output_file: str | Path | None=None, *, answer_col: str | None='model_response', answer_sheet: str | int='Sheet2', label_col: str='final_dimension', full_context_col: str='full_context_json', original_query_col: str='original_query', context_source: str='test', gpt_api_url: str=DEFAULT_GPT_API_URL, gpt_api_key: str=DEFAULT_GPT_API_KEY, gpt_model: str=DEFAULT_GPT_MODEL, proxies: dict[str, str] | None=DEFAULT_PROXIES, verify_ssl: bool=DEFAULT_VERIFY_SSL, request_timeout_seconds: int=DEFAULT_REQUEST_TIMEOUT_SECONDS, max_retries: int=DEFAULT_MAX_RETRIES, retry_base_seconds: int=DEFAULT_RETRY_BASE_SECONDS, resolve_query_placeholder: bool=True, strict_row_count: bool=True, log_fn=print) -> pd.DataFrame:
    """
    对比测试结果与标准答案；字符串不一致时，调用 GPT 复核。

    最简调用：
        compare_intents(
            OUTPUT_XLSX,
            INPUT_FILE,
            col_name="model_response",
            output_file="对比结果.xlsx",
        )

    参数：
        test_file:
            测试结果 Excel。
        answer_file:
            标准答案 Excel。
        col_name:
            测试结果列名；默认 model_response。
        output_file:
            输出结果路径；为 None 时不导出 Excel。
        answer_col:
            标准答案列名；不传时与 col_name 相同。
        answer_sheet:
            标准答案所在 Sheet；默认 Sheet2，也可传 0。
        label_col:
            标准答案 Sheet 中的标签列名；默认“标签”。
            输出会按该列分组统计准确率。
        full_context_col:
            上下文列名。
        original_query_col:
            当前用户输入列名。
        context_source:
            上下文列所在文件，test 或 answer。
        gpt_*:
            GPT 接口配置。
        resolve_query_placeholder:
            是否将 Query 占位符替换为 original_query 后比较。
        strict_row_count:
            两个文件行数不一致时是否直接报错。
        log_fn:
            日志输出函数，默认 print。用于把本函数的 print 输出
            同时写入调用方（multi_test.py）打开的任务日志文件。

    返回：
        包含逐行判断结果的 DataFrame。
    """
    answer_col = answer_col or col_name
    context_source = context_source.strip().lower()
    if context_source not in {'test', 'answer'}:
        raise ValueError("context_source 只能是 'test' 或 'answer'")
    if not gpt_api_key or gpt_api_key.startswith('YOUR_'):
        raise ValueError('请填写 gpt_api_key，或修改脚本顶部 DEFAULT_GPT_API_KEY')
    if not gpt_model or gpt_model.startswith('YOUR_'):
        raise ValueError('请填写 gpt_model，或修改脚本顶部 DEFAULT_GPT_MODEL')
    df_test = pd.read_excel(test_file)
    df_answer = pd.read_excel(answer_file, sheet_name=answer_sheet)

    def validate_columns(df: pd.DataFrame, required_columns: list[str], file_label: str) -> None:
        missing = [column for column in required_columns if column not in df.columns]
        if missing:
            raise ValueError(f'{file_label}缺少必要列：{missing}；当前列：{list(df.columns)}')
    validate_columns(df_test, [col_name], '测试结果文件')
    validate_columns(df_answer, [answer_col, label_col], '标准答案文件')
    context_df = df_test if context_source == 'test' else df_answer
    context_file_label = '测试结果文件' if context_source == 'test' else '标准答案文件'
    validate_columns(context_df, [full_context_col, original_query_col], context_file_label)
    if len(df_test) != len(df_answer):
        message = f'两个文件行数不一致：测试结果 {len(df_test)} 行，标准答案 {len(df_answer)} 行'
        log_fn(f'⚠️ {message}，本次只比较共有行。')
    total_rows = min(len(df_test), len(df_answer))
    results: list[dict[str, Any]] = []
    direct_correct_count = 0
    gpt_correct_count = 0
    mismatch_error_count = 0
    model_format_error_count = 0
    answer_format_error_count = 0
    manual_review_count = 0
    for i in range(total_rows):
        excel_row = i + 2
        test_cell = df_test[col_name].iloc[i]
        answer_cell = df_answer[answer_col].iloc[i]
        case_label = normalize_cell(df_answer[label_col].iloc[i]) or '未标注'
        context_row = context_df.iloc[i]
        full_context_value = context_row[full_context_col]
        original_query = normalize_cell(context_row[original_query_col])
        success_test, intent_test = extract_intent(test_cell)
        success_answer, intent_answer = extract_intent(answer_cell)
        rule_result = ''
        gpt_result = ''
        gpt_reason = ''
        gpt_raw_output = ''
        final_result = ''
        if not success_test:
            rule_result = '测试结果格式错误'
            final_result = '格式错误'
            model_format_error_count += 1
        elif not success_answer:
            rule_result = '标准答案格式错误'
            final_result = '待人工判断'
            answer_format_error_count += 1
            manual_review_count += 1
        else:
            resolved_test_intent = resolve_query_placeholder_fn(intent_test or '', original_query, resolve_query_placeholder)
            resolved_answer_intent = resolve_query_placeholder_fn(intent_answer or '', original_query, resolve_query_placeholder)
            cleaned_test = remove_punctuation(resolved_test_intent)
            cleaned_answer = remove_punctuation(resolved_answer_intent)
            if cleaned_test == cleaned_answer:
                rule_result = '一致'
                final_result = '正确'
                direct_correct_count += 1
            else:
                rule_result = '不一致，进入GPT复核'
                history_context = build_history_context(full_context_value, original_query)
                gpt_prompt = build_gpt_user_prompt(history_context=history_context, original_query=original_query, actual_response=normalize_cell(test_cell), expected_answer=normalize_cell(answer_cell), actual_intent=resolved_test_intent, expected_intent=resolved_answer_intent)
                log_fn(f'[{i + 1}/{total_rows}] Excel 第 {excel_row} 行不一致，正在 GPT 复核...')
                gpt_result, gpt_reason, gpt_raw_output = request_gpt_judgement(gpt_prompt, gpt_api_url=gpt_api_url, gpt_api_key=gpt_api_key, gpt_model=gpt_model, proxies=proxies, verify_ssl=verify_ssl, request_timeout_seconds=request_timeout_seconds, max_retries=max_retries, retry_base_seconds=retry_base_seconds, log_fn=log_fn)
                if gpt_result == '正确':
                    final_result = '正确'
                    gpt_correct_count += 1
                elif gpt_result == '错误':
                    final_result = '错误'
                    mismatch_error_count += 1
                else:
                    final_result = '待人工判断'
                    manual_review_count += 1
        results.append({'Excel行号': excel_row, '标签': case_label, '当前用户输入': original_query, '测试结果(原始)': normalize_cell(test_cell), '标准答案(原始)': normalize_cell(answer_cell), '测试意图': intent_test if success_test else '格式错误', '答案意图': intent_answer if success_answer else '格式错误', '规则对比结果': rule_result, 'GPT复核结果': gpt_result, 'GPT复核原因': gpt_reason, 'GPT原始输出': gpt_raw_output, '最终结果': final_result})
    result_df = pd.DataFrame(results)
    correct_count = direct_correct_count + gpt_correct_count
    total_valid_for_accuracy = total_rows - answer_format_error_count
    accuracy = correct_count / total_valid_for_accuracy * 100 if total_valid_for_accuracy > 0 else 0
    label_summary_rows: list[dict[str, Any]] = []
    for label_value, group in result_df.groupby('标签', dropna=False, sort=False):
        label_total = len(group)
        label_direct_correct = int((group['规则对比结果'] == '一致').sum())
        label_gpt_correct = int((group['GPT复核结果'] == '正确').sum())
        label_gpt_error = int((group['GPT复核结果'] == '错误').sum())
        label_test_format_error = int((group['规则对比结果'] == '测试结果格式错误').sum())
        label_answer_format_error = int((group['规则对比结果'] == '标准答案格式错误').sum())
        label_manual_review = int((group['最终结果'] == '待人工判断').sum())
        label_correct = int((group['最终结果'] == '正确').sum())
        label_error = int(group['最终结果'].isin(['错误', '格式错误']).sum())
        label_valid_total = label_total - label_answer_format_error
        label_accuracy = label_correct / label_valid_total * 100 if label_valid_total > 0 else 0
        label_summary_rows.append({'标签': normalize_cell(label_value) or '未标注', '总样本数': label_total, '统计样本数': label_valid_total, '规则直接正确': label_direct_correct, 'GPT复核正确': label_gpt_correct, 'GPT复核错误': label_gpt_error, '测试结果格式错误': label_test_format_error, '标准答案格式错误': label_answer_format_error, '待人工判断': label_manual_review, '最终正确数': label_correct, '最终错误数': label_error, '准确率': f'{label_accuracy:.2f}%'})
    label_summary_df = pd.DataFrame(label_summary_rows)
    log_fn('=' * 65)
    log_fn('📊 改写结果准确率报告（含 GPT 复核）')
    log_fn('=' * 65)
    log_fn(f'总样本数:                  {total_rows}')
    log_fn(f'规则直接判定正确:          {direct_correct_count}')
    log_fn(f'GPT 复核后判定正确:        {gpt_correct_count}')
    log_fn(f'GPT 复核后判定错误:        {mismatch_error_count}')
    log_fn(f'测试结果格式错误:          {model_format_error_count}')
    log_fn(f'标准答案格式错误:          {answer_format_error_count}')
    log_fn(f'待人工判断:                {manual_review_count}')
    log_fn(f'最终正确数:                {correct_count}')
    log_fn(f'最终准确率:                {accuracy:.2f}%')
    log_fn('=' * 65)
    if not label_summary_df.empty:
        log_fn('\n📌 按标签准确率')
        log_fn('-' * 65)
        for _, row in label_summary_df.iterrows():
            log_fn(f"{row['标签']}: {row['最终正确数']}/{row['统计样本数']}，准确率 {row['准确率']}，待人工 {row['待人工判断']}")
        log_fn('-' * 65)
    if output_file:
        summary_df = pd.DataFrame({'指标': ['总样本数', '标签数', '规则直接判定正确', 'GPT复核后判定正确', 'GPT复核后判定错误', '测试结果格式错误', '标准答案格式错误', '待人工判断', '最终正确数', '最终准确率'], '数值': [total_rows, len(label_summary_df), direct_correct_count, gpt_correct_count, mismatch_error_count, model_format_error_count, answer_format_error_count, manual_review_count, correct_count, f'{accuracy:.2f}%']})
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            result_df.to_excel(writer, sheet_name='对比详情', index=False)
            summary_df.to_excel(writer, sheet_name='准确率汇总', index=False)
            label_summary_df.to_excel(writer, sheet_name='标签准确率', index=False)
        log_fn(f'\n结果已导出到：{output_path}')
    return result_df

def resolve_query_placeholder_fn(intent: str, original_query: str, enabled: bool) -> str:
    return resolve_query_placeholder(intent, original_query, enabled)
