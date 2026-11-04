# Private iCAP Yellow business implementation. Do not publish.
"""
用户操作统计 - 后端接口服务

数据源：日志目录下的 *.txt 文件，每行一个 JSON record。
支持两种日志格式：
  1. Chat 日志：含 user_id, type, timestamp, model_id, query, response, config
  2. AISchool 日志：含 user_id, type, timestamp, content

部门信息：通过 LDAP 查询缓存到本地 JSON 文件，避免重复查询。
"""
from state_storage import open_state, state_exists, state_isfile
import json
import os
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Optional
import threading
from utils.consts import USER_LOG_DIR
CHINA_TZ = timezone(timedelta(hours=8))
LDAP_SERVER = 'http://127.0.0.1:1/unconfigured'
LDAP_USER = ''
LDAP_PASSWORD = ''
LDAP_BASE = 'dc=china,dc=huawei,dc=com'
CACHE_DIR = os.path.dirname(USER_LOG_DIR) if os.path.dirname(USER_LOG_DIR) else '.'
DEPT_CACHE_PATH = os.path.join(CACHE_DIR, 'user_dept_cache.json')
_cache_lock = threading.Lock()

def parse_timestamp(ts):
    """自动识别时间戳是秒级还是毫秒级，返回北京时间 datetime 对象。"""
    try:
        ts = float(ts)
    except (TypeError, ValueError):
        return None
    if ts > 10000000000.0:
        dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
    else:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.astimezone(CHINA_TZ)

def parse_date_ymd(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d')

def _load_dept_cache():
    """从本地缓存文件加载部门映射"""
    if not state_isfile(DEPT_CACHE_PATH):
        return {}
    try:
        with open_state(DEPT_CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_dept_cache(cache):
    """保存部门映射到本地缓存文件"""
    with _cache_lock:
        try:
            os.makedirs(os.path.dirname(DEPT_CACHE_PATH) or '.', exist_ok=True)
            with open_state(DEPT_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'保存部门缓存失败: {e}')

def _query_ldap_dept(*args, **kwargs):
    return ''

def _build_dept_str(dept_info):
    """将部门信息拼接为 '四级部门-五级部门-六级部门' 字符串"""
    if not dept_info:
        return ''
    parts = [dept_info.get('dept4', ''), dept_info.get('dept5', ''), dept_info.get('dept6', '')]
    parts = [p for p in parts if p]
    unique = []
    for p in parts:
        if not unique or p != unique[-1]:
            unique.append(p)
    return '-'.join(unique)

def refresh_dept_cache():
    """
    全量刷新部门缓存：扫描日志目录收集所有出现的 user_id，批量查询 LDAP。
    由定时任务调用，不在业务接口中触发。
    """
    print('开始全量刷新部门缓存...')
    all_user_ids = set()
    if os.path.isdir(USER_LOG_DIR):
        for filename in os.listdir(USER_LOG_DIR):
            if not filename.endswith('.txt'):
                continue
            uid = filename[:-4]
            if uid:
                all_user_ids.add(uid)
    print(f'共发现 {len(all_user_ids)} 个用户，开始 LDAP 查询...')
    cache = {}
    for i, uid in enumerate(all_user_ids):
        info = _query_ldap_dept(uid)
        if info:
            cache[uid] = info
        else:
            cache[uid] = {'dept4': '', 'dept5': '', 'dept6': '', 'name': ''}
        if (i + 1) % 50 == 0:
            print(f'已查询 {i + 1}/{len(all_user_ids)} 个用户')
    _save_dept_cache(cache)
    print(f'部门缓存刷新完成，共缓存 {len(cache)} 个用户')
    return cache

def _get_dept_cache():
    """仅读取缓存文件，不触发 LDAP 查询"""
    return _load_dept_cache()

def get_user_dept(user_id: str, cache: dict=None):
    """获取单个用户的部门拼接字符串（仅读缓存，不触发 LDAP）"""
    if cache is None:
        cache = _load_dept_cache()
    info = cache.get(user_id)
    return _build_dept_str(info)

def load_all_records(start_date: Optional[str]=None, end_date: Optional[str]=None):
    """从日志目录加载所有记录，按日期过滤。"""
    records = []
    if not os.path.isdir(USER_LOG_DIR):
        return records
    for filename in os.listdir(USER_LOG_DIR):
        if not filename.endswith('.txt'):
            continue
        filepath = os.path.join(USER_LOG_DIR, filename)
        if not state_isfile(filepath):
            continue
        try:
            with open_state(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    user_id = raw.get('user_id', '')
                    if not user_id:
                        continue
                    ts = parse_timestamp(raw.get('timestamp'))
                    if ts is None:
                        continue
                    date_str = parse_date_ymd(ts)
                    if start_date and date_str < start_date:
                        continue
                    if end_date and date_str > end_date:
                        continue
                    records.append({'user_id': user_id, 'timestamp': ts, 'date_str': date_str, 'type': str(raw.get('type', '')), 'model_id': str(raw.get('model_id', '')), 'query': raw.get('query', ''), 'response': raw.get('response', ''), 'content': raw.get('content', ''), 'config': raw.get('config', '')})
        except Exception as e:
            print(f'读取日志文件失败 {filepath}: {e}')
            continue
    return records

def get_overview(start_date: Optional[str]=None, end_date: Optional[str]=None):
    """概览统计"""
    records = load_all_records(start_date, end_date)
    total_operations = len(records)
    user_set = set((r['user_id'] for r in records))
    daily_count = defaultdict(int)
    for r in records:
        daily_count[r['date_str']] += 1
    days = len(daily_count)
    daily_avg = round(total_operations / days, 1) if days > 0 else 0
    peak_day = None
    if daily_count:
        peak_date = max(daily_count, key=daily_count.get)
        peak_day = {'date': peak_date, 'count': daily_count[peak_date]}
    return {'total_operations': total_operations, 'active_users': len(user_set), 'daily_avg': daily_avg, 'peak_day': peak_day}

def get_trend(start_date: Optional[str]=None, end_date: Optional[str]=None, type_filter: Optional[str]=None):
    """用户操作趋势折线图"""
    records = load_all_records(start_date, end_date)
    daily_type_count = defaultdict(lambda: defaultdict(int))
    for r in records:
        t = r['type']
        if type_filter and t != type_filter:
            continue
        daily_type_count[r['date_str']][t] += 1
    all_dates = sorted(daily_type_count.keys())
    all_types = set()
    for dc in daily_type_count.values():
        all_types.update(dc.keys())
    series = []
    for t in sorted(all_types):
        data = [daily_type_count[d].get(t, 0) for d in all_dates]
        series.append({'name': t, 'data': data})
    return {'xAxis': all_dates, 'series': series}

def get_type_distribution(start_date: Optional[str]=None, end_date: Optional[str]=None):
    """操作类型分布饼图"""
    records = load_all_records(start_date, end_date)
    type_count = defaultdict(int)
    for r in records:
        t = r['type'] if r['type'] else 'unknown'
        type_count[t] += 1
    items = [{'name': k, 'value': v} for k, v in sorted(type_count.items(), key=lambda x: -x[1])]
    return {'items': items}

def get_top_users(start_date: Optional[str]=None, end_date: Optional[str]=None, top_n: int=10):
    """活跃用户排行柱状图"""
    records = load_all_records(start_date, end_date)
    user_count = defaultdict(int)
    for r in records:
        user_count[r['user_id']] += 1
    sorted_users = sorted(user_count.items(), key=lambda x: -x[1])[:top_n]
    return {'users': [u[0] for u in sorted_users], 'counts': [u[1] for u in sorted_users]}

def get_department_stats(start_date: Optional[str]=None, end_date: Optional[str]=None, top_n: int=15):
    """
    部门使用统计（柱状图）：
      统计各四级/五级/六级部门的操作次数，按次数降序取 top_n。
      返回三组数据分别对应 dept4/dept5/dept6，前端用 Tab 切换展示。
    """
    records = load_all_records(start_date, end_date)
    all_user_ids = set((r['user_id'] for r in records))
    cache = _get_dept_cache()
    user_count = defaultdict(int)
    for r in records:
        user_count[r['user_id']] += 1
    dept_counters = {'dept4': defaultdict(int), 'dept5': defaultdict(int), 'dept6': defaultdict(int)}
    for uid, cnt in user_count.items():
        info = cache.get(uid, {})
        for level in ['dept4', 'dept5', 'dept6']:
            dept_name = info.get(level, '').strip()
            if dept_name:
                dept_counters[level][dept_name] += cnt
    result = {}
    for level in ['dept4', 'dept5', 'dept6']:
        sorted_items = sorted(dept_counters[level].items(), key=lambda x: -x[1])[:top_n]
        result[level] = {'names': [item[0] for item in sorted_items], 'counts': [item[1] for item in sorted_items]}
    return result

def get_details(start_date: Optional[str]=None, end_date: Optional[str]=None, user_id: Optional[str]=None, type_filter: Optional[str]=None, model_id: Optional[str]=None, keyword: Optional[str]=None, types: Optional[str]=None, page: int=1, page_size: int=20):
    """
    操作明细（分页）：
      支持 keyword（用户名模糊搜索）、types（逗号分隔的多类型筛选，仅作用于明细）。
      返回记录含 dept 字段。
    """
    records = load_all_records(start_date, end_date)
    if user_id:
        records = [r for r in records if user_id.lower() in r['user_id'].lower()]
    if model_id:
        records = [r for r in records if model_id.lower() in r['model_id'].lower()]
    records.sort(key=lambda r: r['timestamp'], reverse=True)
    if types:
        type_list = [t.strip() for t in types.split(',') if t.strip()]
        records = [r for r in records if r['type'] in type_list]
    if keyword:
        records = [r for r in records if keyword.lower() in r['user_id'].lower()]
    total = len(records)
    start = (page - 1) * page_size
    end = start + page_size
    page_records = records[start:end]
    dept_cache = _get_dept_cache()
    filtered = []
    for r in page_records:
        content = r.get('content', '')
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False)
        content = str(content)
        dept_str = get_user_dept(r['user_id'], dept_cache)
        filtered.append({'user_id': r['user_id'], 'timestamp': r['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if r.get('timestamp') else '', 'type': r['type'], 'model_id': r['model_id'], 'dept': dept_str, 'content': content[:200] if content else '', 'query': str(r.get('query', ''))[:1000], 'response': str(r.get('response', ''))[:1000]})
    return {'total': total, 'page': page, 'page_size': page_size, 'records': filtered}

def get_user_candidates(keyword: str='', limit: int=20):
    """用户搜索建议"""
    records = load_all_records()
    users = {}
    if keyword:
        users = {}
    else:
        users = {}
    return sorted(users)[:limit]

def get_model_candidates():
    """模型列表"""
    records = load_all_records()
    models = set((r['model_id'] for r in records if r['model_id']))
    return sorted(models)

def get_type_candidates():
    """操作类型列表（明细表格筛选器用）"""
    records = load_all_records()
    types = set((r['type'] for r in records if r['type']))
    return sorted(types)
