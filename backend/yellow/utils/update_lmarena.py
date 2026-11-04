# Private iCAP Yellow business implementation. Do not publish.
import os
import re
import json
import math
import requests
import pandas as pd
from datetime import datetime, timedelta
current_dir = os.path.dirname(os.path.abspath(__file__))
LM_ARENA_CSV_PATH = os.path.join(current_dir, '../config', 'lmarena_leaderboard.csv')
LM_ARENA_LATEST_URL = 'https://raw.githubusercontent.com/oolong-tea-2026/arena-ai-leaderboards/main/data/latest.json'
LM_ARENA_API_BASE = 'https://raw.githubusercontent.com/oolong-tea-2026/arena-ai-leaderboards/main/data'

def get_ai_model_pubdate_and_model_name(input_name):
    """
    获取AI模型的发布日期和官方名称
    """
    url = 'https://qianfan.baidubce.com/v2/ai_search/web_summary'
    payload = json.dumps({'messages': [{'content': f'{input_name}是什么时候发布的？以及这个模型的官方名称叫什么？\n请严格按照以下格式进行输出：date: xxxx/xx/xx\n，例如：date: 2024/8/9\nmodel_name: DeepSeek-R1-0528', 'role': 'user'}], 'stream': False, 'resource_type_filter': [{'type': 'web', 'top_k': 10}]})
    headers = {'Content-Type': 'application/json', 'Authorization': ''}
    try:
        response = requests.request('POST', url, headers=headers, data=payload.encode('utf-8'), timeout=30)
        response.encoding = 'utf-8'
        result = response.json()['choices'][0]['message']['content']
        return result
    except Exception as e:
        print(f'get_ai_model_pubdate_and_model_name 请求失败: {e}')
        return None

def parse_model_pubdate_response(response_text):
    """
    解析AI模型信息响应，提取date和model_name
    返回 (date, model_name) 元组，解析失败返回 (None, None)
    """
    if not response_text:
        return (None, None)
    date = None
    model_name = None
    for line in response_text.strip().split('\n'):
        line = line.strip()
        if line.startswith('date:'):
            date = line[len('date:'):].strip()
        elif line.startswith('model_name:'):
            model_name = line[len('model_name:'):].strip()
    return (date, model_name)

def normalize_date(date_str):
    """
    规则1: 校验日期格式，必须符合 xxxx/xx/xx（年月日数字），
    返回规范格式 xxxx/x/x（去掉前导零），
    日期不合法则返回 None
    """
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    m = re.match('^(\\d{4})[/\\-](\\d{1,2})[/\\-](\\d{1,2})$', date_str)
    if not m:
        return None
    year, month, day = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    try:
        dt = datetime(year, month, day)
    except ValueError:
        return None
    return f'{dt.year}/{dt.month}/{dt.day}'

def clean_model_name(model_name):
    """
    规则2: 去除首尾空格，去除 ** 等特殊字符，
    只允许包含字母、数字、-、.、空格、中文
    """
    if not model_name or not isinstance(model_name, str):
        return None
    name = model_name.strip()
    name = re.sub('[\\*\\#\\_]+', '', name)
    name = name.strip()
    if not name:
        return None
    cleaned = re.sub('[^a-zA-Z0-9\\-\\.\\s]', '', name)
    cleaned = cleaned.strip()
    return cleaned if cleaned else None

def extract_best_model_name(model_name, original_model):
    """
    规则3: 如果 model_name 包含括号 () 或 （），
    提取括号内外内容，模糊匹配（小写化），保留与原始 model 更匹配的那一个
    """
    if not model_name or not original_model:
        return model_name
    m = re.search('[（(](.+?)[)）]', model_name)
    if not m:
        return model_name
    inside = m.group(1).strip()
    outside = (model_name[:m.start()] + model_name[m.end():]).strip()
    orig_lower = set(original_model.lower())
    inside_lower = inside.lower()
    outside_lower = outside.lower()

    def jaccard_similarity(candidate):
        if not candidate:
            return 0
        cand_set = set(candidate)
        intersection = len(orig_lower & cand_set)
        union = len(orig_lower | cand_set)
        return intersection / union if union else 0
    score_inside = jaccard_similarity(inside_lower)
    score_outside = jaccard_similarity(outside_lower)
    if score_inside >= score_outside:
        return inside
    else:
        return outside

def model_key(name):
    """
    规则4 查重key: 全部小写，去掉 . _ 和空格
    """
    if not name:
        return ''
    return re.sub('[\\._\\s]', '', name.lower())

def is_within_last_two_years(date_str):
    """
    规则5: 校验日期是否在近2年内
    """
    if not date_str:
        return False
    m = re.match('^(\\d{4})/(\\d{1,2})/(\\d{1,2})$', date_str)
    if not m:
        return False
    try:
        dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return False
    two_years_ago = datetime.now() - timedelta(days=730)
    return dt >= two_years_ago

def fetch_lmarena_latest_data():
    """
    从外部接口获取最新排名数据，返回models列表
    """
    try:
        resp = requests.get(LM_ARENA_LATEST_URL, timeout=30)
        resp.raise_for_status()
        latest = resp.json()
        date_str = latest.get('date')
        if not date_str:
            print('latest.json 中未找到 date 字段')
            return (None, None)
        text_url = f'{LM_ARENA_API_BASE}/{date_str}/text.json'
        resp2 = requests.get(text_url, timeout=30)
        resp2.raise_for_status()
        text_data = resp2.json()
        models = text_data.get('models', [])
        filtered = []
        for m in models:
            model_name = m.get('model', '')
            if 'beta' in model_name.lower():
                continue
            ai_resp = get_ai_model_pubdate_and_model_name(model_name)
            pub_date, refreshed_name = parse_model_pubdate_response(ai_resp)
            time_val = normalize_date(pub_date) if pub_date else normalize_date(date_str)
            if time_val is None:
                time_val = normalize_date(date_str)
            if time_val is None:
                print(f'跳过 {model_name}: 日期格式不合法 ({pub_date})')
                continue
            raw_name = refreshed_name if refreshed_name else model_name
            bracketed_name = extract_best_model_name(raw_name, model_name)
            final_name = clean_model_name(bracketed_name)
            if final_name is None:
                final_name = clean_model_name(model_name)
            if final_name is None:
                print(f'跳过 {model_name}: model_name清洗后为空')
                continue
            if not is_within_last_two_years(time_val):
                print(f'跳过 {model_name}: 日期 {time_val} 超过2年')
                continue
            filtered.append({'original_model': model_name, 'model': model_name, 'model_name': final_name, 'elo': m.get('score', 0), 'time': time_val, 'organization': m.get('vendor', ''), 'closed/open': 'closed' if m.get('license', '').lower() == 'proprietary' else 'open', 'rank': m.get('rank', 0), 'votes': m.get('votes', 0)})
        return (date_str, filtered)
    except Exception as e:
        print(f'fetch_lmarena_latest_data 失败: {e}')
        return (None, None)

def update_lmarena_csv():
    """
    每天23:00自动更新csv数据，包含完整的数据校验与去重
    """
    print(f'[{datetime.now()}] 开始更新LM Arena CSV数据...')
    date_str, models = fetch_lmarena_latest_data()
    if models is None:
        print('获取LM Arena数据失败，跳过更新')
        return
    try:
        df_existing = pd.read_csv(LM_ARENA_CSV_PATH)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_existing = pd.DataFrame(columns=['time', 'model', 'model_name', 'elo', 'organization', 'closed/open', 'rank', 'votes'])
    existing_rows = df_existing.to_dict(orient='records')
    cleaned_existing = []
    for row in existing_rows:
        time_val = normalize_date(str(row.get('time', '')))
        if time_val is None:
            print(f"删除已有行: 日期格式不合法 ({row.get('time')})")
            continue
        if not is_within_last_two_years(time_val):
            print(f'删除已有行: 日期 {time_val} 超过2年')
            continue
        name = clean_model_name(str(row.get('model_name', '')))
        if name is None:
            print(f'删除已有行: model_name清洗后为空')
            continue
        row['time'] = time_val
        row['model_name'] = name
        for col in ['elo', 'rank', 'votes']:
            if isinstance(row.get(col), float) and math.isnan(row[col]):
                row[col] = 0
        cleaned_existing.append(row)
    all_rows = cleaned_existing + models
    dedup = {}
    for row in all_rows:
        key = model_key(row.get('model_name', ''))
        if not key:
            continue
        elo = row.get('elo', 0)
        if isinstance(elo, float) and math.isnan(elo):
            elo = 0
        elo = float(elo) if not isinstance(elo, (int, float)) else float(elo)
        if key in dedup:
            existing_elo = dedup[key].get('elo', 0)
            if isinstance(existing_elo, float) and math.isnan(existing_elo):
                existing_elo = 0
            if elo > float(existing_elo):
                dedup[key] = row
        else:
            dedup[key] = row
    final_rows = list(dedup.values())
    final_rows.sort(key=lambda r: float(r.get('rank', 0)) if not (isinstance(r.get('rank'), float) and math.isnan(r.get('rank'))) else 9999)
    df_final = pd.DataFrame(final_rows)
    df_final.to_csv(LM_ARENA_CSV_PATH, index=False)
    print(f'[{datetime.now()}] LM Arena CSV更新完成，共{len(df_final)}条记录（去重后）')
