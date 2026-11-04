# Private iCAP Yellow business implementation. Do not publish.
"""
批量上下文改写测试 + 规则阅卷 + 按维度统计

输入 Excel 默认需要包含以下列：
- 上下文
- 当前语句
- 改写关键字
- 改写黑名单
- 维度

处理流程：
1. 从另一个 py 文件导入 system prompt；
2. 将“上下文”和“当前语句”组装成模型输入：
       <历史上下文>
       ==========
       # 当前用户输入
       xxxx
3. 调用 OpenAI-compatible Chat Completions 接口做改写；
4. 保存模型原始输出；
5. 规则阅卷：
   - 所有“改写关键字”都命中；
   - 且任何“改写黑名单”都未命中；
   - 才判定为正确；
6. 输出测试明细、总体统计、按“维度”统计准确率。

关键字 / 黑名单支持以下分隔符：
- 英文逗号 ,
- 中文逗号 ，
- 顿号 、
"""
from __future__ import annotations
import importlib
import json
import re
import time
from pathlib import Path
from typing import Any
import pandas as pd
import requests
import prompt_without_thought as sp
INPUT_FILE = '上下文数据标注09121440.xlsx'
OUTPUT_FILE = 'rewrite_test_result.xlsx'
INPUT_SHEET = 0
CONTEXT_COLUMN = '上下文'
CURRENT_QUERY_COLUMN = '当前语句'
KEYWORD_COLUMN = '改写关键字'
BLACKLIST_COLUMN = '改写黑名单'
DIMENSION_COLUMN = '维度'
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
MODEL_RESPONSE_COLUMN = 'model_response'
JUDGE_RESULT_COLUMN = '判定结果'
JUDGE_REASON_COLUMN = '判定原因'
REQUIRED_KEYWORDS_COLUMN = '要求关键字'
MATCHED_KEYWORDS_COLUMN = '命中关键字'
MISSING_KEYWORDS_COLUMN = '缺失关键字'
BLACKLIST_TERMS_COLUMN = '黑名单词'
HIT_BLACKLIST_COLUMN = '命中黑名单'
API_ERROR_COLUMN = '接口错误'
ASSEMBLED_INPUT_COLUMN = '组装后输入'

def normalize_cell(value: Any) -> str:
    """将 Excel 单元格安全转换为字符串。"""
    if value is None:
        return ''
    try:
        is_na = pd.isna(value)
        if isinstance(is_na, bool) and is_na:
            return ''
    except (TypeError, ValueError):
        pass
    return str(value).strip()

def remove_trailing_separator(context: str) -> str:
    """
    如果上下文最后已经带了一行 ========，
    先去掉，避免组装后出现两次分隔线。
    """
    text = context.rstrip()
    text = re.sub('(?:\\r?\\n)?\\s*=+\\s*$', '', text)
    return text.rstrip()

def build_model_input(context: str, current_query: str) -> str:
    """
    组装为：
    历史上下文
    ==========
    # 当前用户输入
    xxxx
    """
    context = remove_trailing_separator(normalize_cell(context))
    current_query = normalize_cell(current_query)
    current_block = f'# 当前用户输入\n{current_query}'
    if context:
        return f'{context}\n==========\n{current_block}'
    return current_block

def split_terms(value: Any) -> list[str]:
    """
    按英文逗号、中文逗号、顿号拆分关键字。
    去空、去重，同时保留原顺序。
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
    关键字匹配时：
    - 忽略大小写
    - 忽略各种空白

    不删除标点，避免过度宽松。
    """
    value = normalize_cell(text).lower()
    value = re.sub('\\s+', '', value)
    return value

def match_terms(model_response: str, keywords: list[str], blacklist: list[str]) -> dict[str, Any]:
    """
    阅卷规则：
    1. 所有关键字都必须命中；
    2. 任意黑名单词命中即失败。
    """
    normalized_response = normalize_for_match(model_response)
    matched_keywords: list[str] = []
    missing_keywords: list[str] = []
    for keyword in keywords:
        if normalize_for_match(keyword) in normalized_response:
            matched_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)
    hit_blacklist: list[str] = []
    for term in blacklist:
        if normalize_for_match(term) in normalized_response:
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

def call_llm(system_prompt: str, user_input: str) -> tuple[str, str]:
    """
    返回：
    - 模型 content
    - 错误信息；成功时为空字符串
    """
    headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
    payload = {'model': MODEL_NAME, 'messages': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_input}], 'temperature': TEMPERATURE, 'chat_template_kwargs': {'enable_thinking': False}}
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
                raise ValueError(f'接口 JSON 顶层不是对象；实际类型={type(data).__name__}')
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

def build_overall_stats(detail_df: pd.DataFrame) -> pd.DataFrame:
    total = len(detail_df)
    correct = int((detail_df[JUDGE_RESULT_COLUMN] == '正确').sum())
    failed = int((detail_df[JUDGE_RESULT_COLUMN] == '失败').sum())
    api_failed = int((detail_df[JUDGE_RESULT_COLUMN] == '调用失败').sum())
    accuracy = correct / total * 100 if total > 0 else 0
    return pd.DataFrame({'指标': ['总样本数', '正确数', '失败数', '调用失败数', '总体准确率'], '数值': [total, correct, failed, api_failed, f'{accuracy:.2f}%']})

def build_dimension_stats(detail_df: pd.DataFrame) -> pd.DataFrame:
    """
    按“维度”统计准确率。
    空标签统一显示为“（空标签）”。
    """
    temp = detail_df.copy()
    temp[DIMENSION_COLUMN] = temp[DIMENSION_COLUMN].fillna('').astype(str).str.strip().replace('', '（空标签）')
    rows: list[dict[str, Any]] = []
    for dimension, group in temp.groupby(DIMENSION_COLUMN, sort=False):
        total = len(group)
        correct = int((group[JUDGE_RESULT_COLUMN] == '正确').sum())
        failed = int((group[JUDGE_RESULT_COLUMN] == '失败').sum())
        api_failed = int((group[JUDGE_RESULT_COLUMN] == '调用失败').sum())
        accuracy = correct / total * 100 if total > 0 else 0
        rows.append({'维度': dimension, '样本数': total, '正确数': correct, '失败数': failed, '调用失败数': api_failed, '准确率': f'{accuracy:.2f}%'})
    return pd.DataFrame(rows)

def save_result(detail_df: pd.DataFrame, output_file: str | Path) -> None:
    overall_df = build_overall_stats(detail_df)
    dimension_df = build_dimension_stats(detail_df)
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

def validate_input_columns(df: pd.DataFrame) -> None:
    required_columns = [CONTEXT_COLUMN, CURRENT_QUERY_COLUMN, KEYWORD_COLUMN, BLACKLIST_COLUMN, DIMENSION_COLUMN]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError('输入 Excel 缺少必要列：' + '、'.join(missing) + '；当前列：' + '、'.join(map(str, df.columns)))

def run_batch_test() -> pd.DataFrame:
    validate_config()
    system_prompt = sp.SYS_PROMPT_NO_FEWSHOT
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
                print(f'检测到已有输出，将尝试断点续跑：{OUTPUT_FILE}')
        except Exception as exc:
            print(f'已有输出读取失败，本次从头执行：{exc}')
            detail_df = input_df.copy()
    else:
        detail_df = input_df.copy()
    output_columns = [ASSEMBLED_INPUT_COLUMN, MODEL_RESPONSE_COLUMN, JUDGE_RESULT_COLUMN, JUDGE_REASON_COLUMN, REQUIRED_KEYWORDS_COLUMN, MATCHED_KEYWORDS_COLUMN, MISSING_KEYWORDS_COLUMN, BLACKLIST_TERMS_COLUMN, HIT_BLACKLIST_COLUMN, API_ERROR_COLUMN]
    for column in output_columns:
        if column not in detail_df.columns:
            detail_df[column] = ''
    total_rows = len(detail_df)
    processed_since_save = 0
    for i in range(total_rows):
        excel_row = i + 2
        existing_response = normalize_cell(detail_df.at[i, MODEL_RESPONSE_COLUMN])
        existing_result = normalize_cell(detail_df.at[i, JUDGE_RESULT_COLUMN])
        if RESUME_FROM_OUTPUT and existing_response and existing_result:
            print(f'[{i + 1}/{total_rows}] Excel 第 {excel_row} 行已完成，跳过')
            continue
        context = normalize_cell(detail_df.at[i, CONTEXT_COLUMN])
        current_query = normalize_cell(detail_df.at[i, CURRENT_QUERY_COLUMN])
        keywords = split_terms(detail_df.at[i, KEYWORD_COLUMN])
        blacklist = split_terms(detail_df.at[i, BLACKLIST_COLUMN])
        assembled_input = build_model_input(context, current_query)
        detail_df.at[i, ASSEMBLED_INPUT_COLUMN] = assembled_input
        detail_df.at[i, REQUIRED_KEYWORDS_COLUMN] = '、'.join(keywords)
        detail_df.at[i, BLACKLIST_TERMS_COLUMN] = '、'.join(blacklist)
        print(f'[{i + 1}/{total_rows}] 正在处理 Excel 第 {excel_row} 行...')
        if not current_query:
            detail_df.at[i, JUDGE_RESULT_COLUMN] = '失败'
            detail_df.at[i, JUDGE_REASON_COLUMN] = '当前语句为空'
            processed_since_save += 1
            continue
        model_response, api_error = call_llm(system_prompt, assembled_input)
        detail_df.at[i, MODEL_RESPONSE_COLUMN] = model_response
        detail_df.at[i, API_ERROR_COLUMN] = api_error
        if api_error:
            detail_df.at[i, JUDGE_RESULT_COLUMN] = '调用失败'
            detail_df.at[i, JUDGE_REASON_COLUMN] = api_error
            print(f'  -> 调用失败：{api_error}')
        else:
            judge = match_terms(model_response, keywords, blacklist)
            detail_df.at[i, MATCHED_KEYWORDS_COLUMN] = '、'.join(judge['matched_keywords'])
            detail_df.at[i, MISSING_KEYWORDS_COLUMN] = '、'.join(judge['missing_keywords'])
            detail_df.at[i, HIT_BLACKLIST_COLUMN] = '、'.join(judge['hit_blacklist'])
            detail_df.at[i, JUDGE_RESULT_COLUMN] = '正确' if judge['is_correct'] else '失败'
            detail_df.at[i, JUDGE_REASON_COLUMN] = judge['reason']
            print(f"  -> {detail_df.at[i, JUDGE_RESULT_COLUMN]}；{judge['reason']}")
        processed_since_save += 1
        if SAVE_INTERVAL > 0 and processed_since_save >= SAVE_INTERVAL:
            save_result(detail_df, OUTPUT_FILE)
            processed_since_save = 0
            print(f'  已阶段保存：{OUTPUT_FILE}')
    save_result(detail_df, OUTPUT_FILE)
    overall = build_overall_stats(detail_df)
    print('\n' + '=' * 60)
    print('批量测试完成')
    print('=' * 60)
    for _, row in overall.iterrows():
        print(f"{row['指标']}: {row['数值']}")
    print(f'结果文件：{OUTPUT_FILE}')
    return detail_df
