# Private iCAP Yellow business implementation. Do not publish.
"""
批量上下文改写测试脚本

功能：
1. 读取一个 Excel；
2. 将“上下文”解析成真正的多轮 messages；
3. 将“当前语句”作为最后一个 user message，并包装为：
       # 当前用户输入
       xxxx
4. system prompt 直接从 prompt_without_thought.py 导入；
5. 调用模型执行改写；
6. 保存：
   - 原始上下文
   - 当前语句
   - 实际发送给模型的完整 messages
   - 模型输出
   - 规则判定结果
7. 宽松规则：
   - 所有“改写关键字”都必须命中；
   - 任意“改写黑名单”都不能命中；
8. 严格规则：
   - 先满足宽松规则；
   - 若“审核结果=不改写”，再要求当前用户输入与模型改写文本
     去除标点和空白后完全一致；
   - 其他审核结果下，严格规则与宽松规则相同；
9. 输出总体和不同“维度”下的宽松 / 严格两套准确率。

输入 Excel 默认列：
- 上下文
- 当前语句
- 改写关键字
- 改写黑名单
- 维度

关键字和黑名单支持：
英文逗号 , / 中文逗号 ， / 顿号 、
"""
from __future__ import annotations
import json
import re
import time
from pathlib import Path
from typing import Any
import pandas as pd
import requests
import urllib3
import prompt_without_thought as sp
SYSTEM_PROMPT = sp.SYS_PROMPT
INPUT_FILE = '上下文改写评测集_v1.0.xlsx'
OUTPUT_FILE = 'rewrite_test_result_qwen3.8_27b.xlsx'
INPUT_SHEET = 0
CONTEXT_COLUMN = '上下文'
CURRENT_QUERY_COLUMN = '当前语句'
KEYWORD_COLUMN = '改写关键字'
BLACKLIST_COLUMN = '改写黑名单'
REVIEW_RESULT_COLUMN = '审核结果'
DIMENSION_COLUMN = '维度'
DIMENSION_COLUMN_ALIASES = ('改写类型',)
LLM_BASE_URL = 'http://127.0.0.1:1/unconfigured'
API_KEY = ''
MODEL_NAME = 'Qwen3.8-27B'
PROXIES = None
VERIFY_SSL = False
REQUEST_TIMEOUT_SECONDS = 180
MAX_RETRIES = 3
RETRY_BASE_SECONDS = 2
TEMPERATURE = 0
SAVE_INTERVAL = 20
RESUME_FROM_OUTPUT = True
EMPTY_KEYWORD_COUNTS_AS_PASS = False
MESSAGES_JSON_COLUMN = 'messages_json'
MODEL_RESPONSE_COLUMN = 'model_response'
LOOSE_JUDGE_RESULT_COLUMN = '宽松判定结果'
LOOSE_JUDGE_REASON_COLUMN = '宽松判定原因'
STRICT_JUDGE_RESULT_COLUMN = '严格判定结果'
STRICT_JUDGE_REASON_COLUMN = '严格判定原因'
REWRITE_TEXT_COLUMN = '模型改写文本'
STRICT_CURRENT_TEXT_COLUMN = '严格匹配_当前输入'
STRICT_MODEL_TEXT_COLUMN = '严格匹配_模型输出'
REQUIRED_KEYWORDS_COLUMN = '要求关键字'
MATCHED_KEYWORDS_COLUMN = '命中关键字'
MISSING_KEYWORDS_COLUMN = '缺失关键字'
BLACKLIST_TERMS_COLUMN = '黑名单词'
HIT_BLACKLIST_COLUMN = '命中黑名单'
API_ERROR_COLUMN = '接口错误'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def normalize_cell(value: Any) -> str:
    """安全读取 Excel 单元格。"""
    if value is None:
        return ''
    try:
        is_na = pd.isna(value)
        if isinstance(is_na, bool) and is_na:
            return ''
    except (TypeError, ValueError):
        pass
    return str(value).strip()

def split_terms(value: Any) -> list[str]:
    """
    按英文逗号、中文逗号、顿号拆分。
    去空、去重、保持原顺序。
    """
    text = normalize_cell(value)
    if not text:
        return []
    parts = re.split('[,，、]', text)
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        term = part.strip()
        if not term:
            continue
        if term not in seen:
            result.append(term)
            seen.add(term)
    return result

def normalize_for_match(text: str) -> str:
    """
    规则匹配时：
    - 忽略大小写
    - 忽略所有空白
    - 不主动删除标点
    """
    value = normalize_cell(text).lower()
    value = re.sub('\\s+', '', value)
    return value

def normalize_for_strict_match(text: str) -> str:
    """
    严格“不改写”匹配：
    - 去除中英文标点
    - 去除空白
    - 其余字符保持不变
    """
    value = normalize_cell(text)
    value = re.sub('[^\\w\\s]', '', value, flags=re.UNICODE)
    value = re.sub('\\s+', '', value)
    return value

def extract_rewrite_text(model_response: str) -> str:
    """
    优先从 {"意图":"xxx"} 中提取真正的改写文本。
    若无法解析，则退化为原始输出。
    """
    raw = normalize_cell(model_response)
    if not raw:
        return ''
    cleaned = re.sub('^```(?:json)?\\s*', '', raw, flags=re.IGNORECASE)
    cleaned = re.sub('\\s*```$', '', cleaned).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, str):
            try:
                nested = json.loads(data)
                if isinstance(nested, dict):
                    data = nested
            except Exception:
                pass
        if isinstance(data, dict):
            intent = data.get('意图')
            if isinstance(intent, str):
                return intent.strip()
    except Exception:
        pass
    return raw

def remove_trailing_separator(context: str) -> str:
    """
    删除上下文末尾的 ======= / ======== / 任意数量等号。

    例如：
        user: xxx
        assistant: xxx
        =======

    变成：
        user: xxx
        assistant: xxx

    注意：
    分隔线不会传给模型。
    """
    text = normalize_cell(context).rstrip()
    text = re.sub('(?:\\r?\\n)?\\s*=+\\s*$', '', text)
    return text.rstrip()

def parse_context_messages(context: str) -> list[dict[str, str]]:
    """
    把 Excel 中这种文本：

        user: 我想看熊
        assistant: 无可用助手回复
        user: 小女孩的
        assistant: 无可用助手回复
        =======

    解析为：

        [
            {"role": "user", "content": "我想看熊"},
            {"role": "assistant", "content": "无可用助手回复"},
            {"role": "user", "content": "小女孩的"},
            {"role": "assistant", "content": "无可用助手回复"}
        ]

    支持 content 跨多行。
    """
    text = remove_trailing_separator(context)
    if not text:
        return []
    pattern = re.compile('(?ms)^(user|assistant)\\s*:\\s*(.*?)(?=^(?:user|assistant)\\s*:|\\Z)')
    messages: list[dict[str, str]] = []
    for role, content in pattern.findall(text):
        content = content.strip()
        if not content:
            continue
        messages.append({'role': role, 'content': content})
    if text and (not messages):
        raise ValueError(f'上下文无法解析出 user:/assistant: 消息，请检查格式。上下文前300字：{text[:300]!r}')
    return messages

def build_messages(context: str, current_query: str) -> list[dict[str, str]]:
    """
    最终真正送给模型的 messages：

    [
        {"role": "system", "content": SYSTEM_PROMPT},
        ...历史 user / assistant messages...,
        {
            "role": "user",
            "content": "# 当前用户输入\\n新的当前输入"
        }
    ]
    """
    history_messages = parse_context_messages(context)
    current_query = normalize_cell(current_query)
    current_message = {'role': 'user', 'content': f'# 当前用户输入\n{current_query}'}
    return [{'role': 'system', 'content': SYSTEM_PROMPT}, *history_messages, current_message]

def messages_to_json(messages: list[dict[str, str]]) -> str:
    """
    将实际发送给模型的完整 messages 保存成可读 JSON。
    """
    return json.dumps(messages, ensure_ascii=False, indent=2)

def call_llm(messages: list[dict[str, str]]) -> tuple[str, str]:
    """
    返回：
    - model_response
    - api_error
    """
    headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
    payload = {'model': MODEL_NAME, 'messages': messages, 'temperature': TEMPERATURE, 'chat_template_kwargs': {'enable_thinking': False}}
    last_error = ''
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request('POST', LLM_BASE_URL, json=payload, headers=headers, verify=VERIFY_SSL, timeout=REQUEST_TIMEOUT_SECONDS)
            response_text = response.text or ''
            content_type = response.headers.get('Content-Type', '')
            request_id = response.headers.get('x-request-id') or response.headers.get('request-id') or response.headers.get('x-trace-id') or ''
            if not response.ok:
                error_message = f'HTTP {response.status_code}；Content-Type={content_type!r}；request-id={request_id!r}；响应前500字={response_text[:500]!r}'
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    return ('', error_message)
                raise RuntimeError(error_message)
            if not response_text.strip():
                raise ValueError(f'接口返回空响应体；HTTP {response.status_code}；Content-Type={content_type!r}；request-id={request_id!r}')
            try:
                data = response.json()
            except Exception as exc:
                raise ValueError(f'接口响应不是合法 JSON；HTTP {response.status_code}；Content-Type={content_type!r}；request-id={request_id!r}；响应前500字={response_text[:500]!r}') from exc
            if not isinstance(data, dict):
                raise ValueError(f'接口 JSON 顶层不是对象；实际类型={type(data).__name__}；响应前500字={response_text[:500]!r}')
            choices = data.get('choices') or []
            if not choices:
                raise ValueError(f'响应中没有 choices；request-id={request_id!r}；响应前500字={response_text[:500]!r}')
            choice = choices[0]
            message = choice.get('message') or {}
            content = normalize_cell(message.get('content'))
            if not content:
                finish_reason = choice.get('finish_reason')
                reasoning_content = normalize_cell(message.get('reasoning_content'))
                raise ValueError(f'模型返回空 content；finish_reason={finish_reason!r}；reasoning_content前200字={reasoning_content[:200]!r}')
            return (content, '')
        except Exception as exc:
            last_error = str(exc)
            if attempt < MAX_RETRIES:
                wait_seconds = RETRY_BASE_SECONDS * attempt
                print(f'    第 {attempt}/{MAX_RETRIES} 次调用失败，{wait_seconds} 秒后重试：{last_error}')
                time.sleep(wait_seconds)
    return ('', last_error)

def judge_response(model_response: str, keywords: list[str], blacklist: list[str]) -> dict[str, Any]:
    """
    正确条件：
    1. 所有改写关键字都命中；
    2. 所有黑名单词都未命中。

    例如：
      改写关键字 = "熊，小女孩"
      黑名单 = "电影、动画"

    model_response 必须同时包含：
      熊
      小女孩

    且不能包含：
      电影
      动画
    """
    normalized_response = normalize_for_match(model_response)
    matched_keywords: list[str] = []
    missing_keywords: list[str] = []
    for keyword in keywords:
        normalized_keyword = normalize_for_match(keyword)
        if normalized_keyword in normalized_response:
            matched_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)
    hit_blacklist: list[str] = []
    for term in blacklist:
        normalized_term = normalize_for_match(term)
        if normalized_term in normalized_response:
            hit_blacklist.append(term)
    if not keywords and (not EMPTY_KEYWORD_COUNTS_AS_PASS):
        is_correct = False
        reason = '未配置改写关键字'
    elif missing_keywords:
        is_correct = False
        reason = '缺失关键字：' + '、'.join(missing_keywords)
        if hit_blacklist:
            reason += '；同时命中黑名单：' + '、'.join(hit_blacklist)
    elif hit_blacklist:
        is_correct = False
        reason = '命中黑名单：' + '、'.join(hit_blacklist)
    else:
        is_correct = True
        if keywords:
            reason = '所有关键字均命中，且未命中黑名单'
        else:
            reason = '未设置关键字，且未命中黑名单'
    return {'is_correct': is_correct, 'reason': reason, 'matched_keywords': matched_keywords, 'missing_keywords': missing_keywords, 'hit_blacklist': hit_blacklist}

def judge_strict_rule(loose_is_correct: bool, loose_reason: str, review_result: str, current_query: str, model_response: str) -> dict[str, Any]:
    """
    严格规则：
    - 先满足宽松规则；
    - 仅当“审核结果 == 不改写”时，再要求：
      当前用户输入 == 模型改写文本（忽略标点和空白）；
    - 其他审核结果下，严格规则直接沿用宽松规则。
    """
    rewrite_text = extract_rewrite_text(model_response)
    current_norm = normalize_for_strict_match(current_query)
    model_norm = normalize_for_strict_match(rewrite_text)
    review_result = normalize_cell(review_result)
    if not loose_is_correct:
        return {'is_correct': False, 'reason': f'宽松规则失败：{loose_reason}', 'rewrite_text': rewrite_text, 'current_norm': current_norm, 'model_norm': model_norm}
    if review_result != '不改写':
        return {'is_correct': True, 'reason': '非“不改写”用例，严格规则沿用宽松结果', 'rewrite_text': rewrite_text, 'current_norm': current_norm, 'model_norm': model_norm}
    if current_norm == model_norm:
        return {'is_correct': True, 'reason': '宽松规则通过，且“不改写”用例去除标点后与当前输入完全一致', 'rewrite_text': rewrite_text, 'current_norm': current_norm, 'model_norm': model_norm}
    return {'is_correct': False, 'reason': '宽松规则通过，但“不改写”用例硬匹配失败：当前输入与模型改写文本去除标点后不一致', 'rewrite_text': rewrite_text, 'current_norm': current_norm, 'model_norm': model_norm}

def build_overall_stats(detail_df: pd.DataFrame) -> pd.DataFrame:
    """总体宽松 / 严格两套准确率。"""
    total = len(detail_df)
    loose_correct = int((detail_df[LOOSE_JUDGE_RESULT_COLUMN] == '正确').sum())
    loose_failed = int((detail_df[LOOSE_JUDGE_RESULT_COLUMN] == '失败').sum())
    strict_correct = int((detail_df[STRICT_JUDGE_RESULT_COLUMN] == '正确').sum())
    strict_failed = int((detail_df[STRICT_JUDGE_RESULT_COLUMN] == '失败').sum())
    api_failed = int((detail_df[LOOSE_JUDGE_RESULT_COLUMN] == '调用失败').sum())
    loose_accuracy = loose_correct / total * 100 if total else 0
    strict_accuracy = strict_correct / total * 100 if total else 0
    return pd.DataFrame({'指标': ['总样本数', '宽松规则正确数', '宽松规则失败数', '宽松规则准确率', '严格规则正确数', '严格规则失败数', '严格规则准确率', '调用失败数'], '数值': [total, loose_correct, loose_failed, f'{loose_accuracy:.2f}%', strict_correct, strict_failed, f'{strict_accuracy:.2f}%', api_failed]})

def build_dimension_stats(detail_df: pd.DataFrame) -> pd.DataFrame:
    """按照“维度”分别统计宽松 / 严格准确率。"""
    temp = detail_df.copy()
    dimension_column = DIMENSION_COLUMN
    if dimension_column not in temp.columns:
        for alias in DIMENSION_COLUMN_ALIASES:
            if alias in temp.columns:
                temp = temp.rename(columns={alias: dimension_column})
                break
    temp[dimension_column] = temp[dimension_column].fillna('').astype(str).str.strip().replace('', '（空标签）')
    rows: list[dict[str, Any]] = []
    for dimension, group in temp.groupby(dimension_column, sort=False):
        total = len(group)
        loose_correct = int((group[LOOSE_JUDGE_RESULT_COLUMN] == '正确').sum())
        loose_failed = int((group[LOOSE_JUDGE_RESULT_COLUMN] == '失败').sum())
        strict_correct = int((group[STRICT_JUDGE_RESULT_COLUMN] == '正确').sum())
        strict_failed = int((group[STRICT_JUDGE_RESULT_COLUMN] == '失败').sum())
        api_failed = int((group[LOOSE_JUDGE_RESULT_COLUMN] == '调用失败').sum())
        loose_accuracy = loose_correct / total * 100 if total else 0
        strict_accuracy = strict_correct / total * 100 if total else 0
        rows.append({'维度': dimension, '样本数': total, '宽松正确数': loose_correct, '宽松失败数': loose_failed, '宽松准确率': f'{loose_accuracy:.2f}%', '严格正确数': strict_correct, '严格失败数': strict_failed, '严格准确率': f'{strict_accuracy:.2f}%', '调用失败数': api_failed})
    return pd.DataFrame(rows)
_ILLEGAL_EXCEL_CHAR_RE = re.compile('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]')

def _sanitize_excel_text(value):
    """剔除字符串中 openpyxl 无法写入 Excel 的非法字符；非字符串原样返回。"""
    if isinstance(value, str):
        return _ILLEGAL_EXCEL_CHAR_RE.sub('', value)
    return value

def _sanitize_df(df):
    """按单元格清理 DataFrame，防止写 Excel 时抛 IllegalCharacterError。"""
    for col in df.columns:
        df[col] = df[col].map(_sanitize_excel_text)
    return df

def save_result(detail_df: pd.DataFrame, output_file: str | Path) -> None:
    """
    输出 3 个 Sheet：
    - 测试明细
    - 总体统计
    - 维度统计
    """
    detail_df = _sanitize_df(detail_df)
    overall_df = _sanitize_df(build_overall_stats(detail_df))
    dimension_df = _sanitize_df(build_dimension_stats(detail_df))
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        detail_df.to_excel(writer, sheet_name='测试明细', index=False)
        overall_df.to_excel(writer, sheet_name='总体统计', index=False)
        dimension_df.to_excel(writer, sheet_name='维度统计', index=False)

def validate_config() -> None:
    if not Path(INPUT_FILE).exists():
        raise FileNotFoundError(f'输入文件不存在：{INPUT_FILE}')
    if not API_KEY or API_KEY.startswith('YOUR_'):
        raise ValueError('请先在脚本顶部填写 API_KEY')
    if not MODEL_NAME or MODEL_NAME.startswith('YOUR_'):
        raise ValueError('请先在脚本顶部填写 MODEL_NAME')
    if not isinstance(SYSTEM_PROMPT, str):
        raise TypeError('prompt_without_thought.SYS_PROMPT 必须是字符串')
    if not SYSTEM_PROMPT.strip():
        raise ValueError('prompt_without_thought.SYS_PROMPT 为空')

def validate_input_columns(df: pd.DataFrame) -> None:
    required_columns = [CONTEXT_COLUMN, CURRENT_QUERY_COLUMN, KEYWORD_COLUMN, BLACKLIST_COLUMN, REVIEW_RESULT_COLUMN]
    if DIMENSION_COLUMN not in df.columns:
        for alias in DIMENSION_COLUMN_ALIASES:
            if alias in df.columns:
                break
        else:
            required_columns.append(DIMENSION_COLUMN)
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError('输入 Excel 缺少必要列：' + '、'.join(missing) + '；当前列：' + '、'.join(map(str, df.columns)))

def run_batch_test() -> pd.DataFrame:
    validate_config()
    input_df = pd.read_excel(INPUT_FILE, sheet_name=INPUT_SHEET)
    validate_input_columns(input_df)
    if RESUME_FROM_OUTPUT and Path(OUTPUT_FILE).exists():
        try:
            detail_df = pd.read_excel(OUTPUT_FILE, sheet_name='测试明细')
            if len(detail_df) != len(input_df):
                print('检测到已有输出，但行数与当前输入不一致，本次从头执行。')
                detail_df = input_df.copy()
            else:
                for column in input_df.columns:
                    detail_df[column] = input_df[column]
                print('检测到已有输出，将尝试从已有结果断点续跑。')
        except Exception as exc:
            print(f'已有输出读取失败，本次从头执行：{exc}')
            detail_df = input_df.copy()
    else:
        detail_df = input_df.copy()
    output_columns = [MESSAGES_JSON_COLUMN, MODEL_RESPONSE_COLUMN, LOOSE_JUDGE_RESULT_COLUMN, LOOSE_JUDGE_REASON_COLUMN, STRICT_JUDGE_RESULT_COLUMN, STRICT_JUDGE_REASON_COLUMN, REWRITE_TEXT_COLUMN, STRICT_CURRENT_TEXT_COLUMN, STRICT_MODEL_TEXT_COLUMN, REQUIRED_KEYWORDS_COLUMN, MATCHED_KEYWORDS_COLUMN, MISSING_KEYWORDS_COLUMN, BLACKLIST_TERMS_COLUMN, HIT_BLACKLIST_COLUMN, API_ERROR_COLUMN]
    for column in output_columns:
        if column not in detail_df.columns:
            detail_df[column] = ''
    total_rows = len(detail_df)
    processed_since_save = 0
    for i in range(total_rows):
        excel_row = i + 2
        existing_response = normalize_cell(detail_df.at[i, MODEL_RESPONSE_COLUMN])
        existing_loose_result = normalize_cell(detail_df.at[i, LOOSE_JUDGE_RESULT_COLUMN])
        existing_strict_result = normalize_cell(detail_df.at[i, STRICT_JUDGE_RESULT_COLUMN])
        if RESUME_FROM_OUTPUT and existing_response and existing_loose_result and existing_strict_result:
            print(f'[{i + 1}/{total_rows}] Excel 第 {excel_row} 行已完成，跳过')
            continue
        context = normalize_cell(detail_df.at[i, CONTEXT_COLUMN])
        current_query = normalize_cell(detail_df.at[i, CURRENT_QUERY_COLUMN])
        keywords = split_terms(detail_df.at[i, KEYWORD_COLUMN])
        blacklist = split_terms(detail_df.at[i, BLACKLIST_COLUMN])
        review_result = normalize_cell(detail_df.at[i, REVIEW_RESULT_COLUMN])
        detail_df.at[i, REQUIRED_KEYWORDS_COLUMN] = '、'.join(keywords)
        detail_df.at[i, BLACKLIST_TERMS_COLUMN] = '、'.join(blacklist)
        print(f'[{i + 1}/{total_rows}] 正在处理 Excel 第 {excel_row} 行...')
        if not current_query:
            detail_df.at[i, LOOSE_JUDGE_RESULT_COLUMN] = '失败'
            detail_df.at[i, LOOSE_JUDGE_REASON_COLUMN] = '当前语句为空'
            detail_df.at[i, STRICT_JUDGE_RESULT_COLUMN] = '失败'
            detail_df.at[i, STRICT_JUDGE_REASON_COLUMN] = '当前语句为空'
            processed_since_save += 1
            continue
        try:
            messages = build_messages(context, current_query)
        except Exception as exc:
            error_message = f'上下文解析失败：{exc}'
            detail_df.at[i, LOOSE_JUDGE_RESULT_COLUMN] = '失败'
            detail_df.at[i, LOOSE_JUDGE_REASON_COLUMN] = error_message
            detail_df.at[i, STRICT_JUDGE_RESULT_COLUMN] = '失败'
            detail_df.at[i, STRICT_JUDGE_REASON_COLUMN] = error_message
            detail_df.at[i, API_ERROR_COLUMN] = error_message
            print(f'  -> {error_message}')
            processed_since_save += 1
            continue
        detail_df.at[i, MESSAGES_JSON_COLUMN] = messages_to_json(messages)
        model_response, api_error = call_llm(messages)
        detail_df.at[i, MODEL_RESPONSE_COLUMN] = model_response
        detail_df.at[i, API_ERROR_COLUMN] = api_error
        if api_error:
            detail_df.at[i, LOOSE_JUDGE_RESULT_COLUMN] = '调用失败'
            detail_df.at[i, LOOSE_JUDGE_REASON_COLUMN] = api_error
            detail_df.at[i, STRICT_JUDGE_RESULT_COLUMN] = '调用失败'
            detail_df.at[i, STRICT_JUDGE_REASON_COLUMN] = api_error
            print(f'  -> 调用失败：{api_error}')
        else:
            judge = judge_response(model_response, keywords, blacklist)
            detail_df.at[i, MATCHED_KEYWORDS_COLUMN] = '、'.join(judge['matched_keywords'])
            detail_df.at[i, MISSING_KEYWORDS_COLUMN] = '、'.join(judge['missing_keywords'])
            detail_df.at[i, HIT_BLACKLIST_COLUMN] = '、'.join(judge['hit_blacklist'])
            detail_df.at[i, LOOSE_JUDGE_RESULT_COLUMN] = '正确' if judge['is_correct'] else '失败'
            detail_df.at[i, LOOSE_JUDGE_REASON_COLUMN] = judge['reason']
            strict_judge = judge_strict_rule(loose_is_correct=judge['is_correct'], loose_reason=judge['reason'], review_result=review_result, current_query=current_query, model_response=model_response)
            detail_df.at[i, STRICT_JUDGE_RESULT_COLUMN] = '正确' if strict_judge['is_correct'] else '失败'
            detail_df.at[i, STRICT_JUDGE_REASON_COLUMN] = strict_judge['reason']
            detail_df.at[i, REWRITE_TEXT_COLUMN] = strict_judge['rewrite_text']
            detail_df.at[i, STRICT_CURRENT_TEXT_COLUMN] = strict_judge['current_norm']
            detail_df.at[i, STRICT_MODEL_TEXT_COLUMN] = strict_judge['model_norm']
            print(f"  -> 宽松={detail_df.at[i, LOOSE_JUDGE_RESULT_COLUMN]}；严格={detail_df.at[i, STRICT_JUDGE_RESULT_COLUMN]}；{strict_judge['reason']}")
        processed_since_save += 1
        if SAVE_INTERVAL > 0 and processed_since_save >= SAVE_INTERVAL:
            save_result(detail_df, OUTPUT_FILE)
            processed_since_save = 0
            print(f'  已阶段保存：{OUTPUT_FILE}')
    save_result(detail_df, OUTPUT_FILE)
    overall_df = build_overall_stats(detail_df)
    dimension_df = build_dimension_stats(detail_df)
    print('\n' + '=' * 60)
    print('批量测试完成')
    print('=' * 60)
    for _, row in overall_df.iterrows():
        print(f"{row['指标']}: {row['数值']}")
    print('\n按维度统计：')
    if dimension_df.empty:
        print('无维度数据')
    else:
        print(dimension_df.to_string(index=False))
    print(f'\n结果文件：{OUTPUT_FILE}')
    return detail_df
