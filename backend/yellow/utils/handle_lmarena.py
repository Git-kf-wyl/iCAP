# Private iCAP Yellow business implementation. Do not publish.
import csv
import json
import re
import time
from datetime import datetime
import httpx
import pandas as pd
import requests
from openai import OpenAI
prompt_fetch_arena_ai = '\n你是一个json内容提取工具，请查询最新的https://arena.ai/leaderboard/text的表格和查询最新消息，将表格排行榜的前50名，输出一个json。\n\n#查询时间\n2026/4/23\n\n#要求\nrank: 从表格的Rank获取\nmodel: 从表格的Model获取\nelo: 从表格的Score获取\nvotes: 从表格的Votes获取\norganization: 从表格的Model的公司名称获取\ndate: 需要另外查询Model的发布时间\n\n#输出格式：\n[\n  {\n    "rank": 1,\n    "model": "claude-opus-4-7-thinking",\n    "elo": 1503,\n    "votes": 4924,\n    "organization": "Anthropic",\n    "date": "2026/4/16"\n    }\n]\n'
prompt_fetch_model_date = '\n你是一个查询模型发布时间的专家，请快速查询{0}模型的官方发布时间\n\n#要求\n只返回时间，不需要返回其他额外信息\n\n#输出格式\n2026/4/23\n'
OPEN_SOURCE_ORG_LIST = ['alibaba', 'deepseek', 'moonshot', 'z.ai', 'xiaomi']
CLOSED_SOURCE_ORG_LIST = ['anthropic', 'openai', 'google', 'xai']
ALIBABA_MODEL_LIST = ['qwen4', 'qwen3.6-plus', 'qwen3.5-max', 'qwen3.5-397b-a17b', 'qwen3-max', 'qwen3-235b-a22b', 'qwen2.5-max', 'qwen2-72b', 'qwen1.5-110b']
DEEPSEEK_MODEL_LIST = ['deepseek-r2', 'deepseek-v4', 'deepseek-v3.2-exp', 'deepseek-r1', 'deepseek-v3.1', 'deepseek-v3', 'deepseek-v2.5', 'deepseek-coder-v2']
Moonshot_MODEL_LIST = ['kimi-k2.6', 'kimi-k2.5-think', 'kimi-k2-think']
Zai_MODEL_LIST = ['glm-5.1', 'glm-5', 'glm-4.5']
XIAOMI_MODEL_LIST = ['mimo-v2-pro']
ANTHROPIC_MODEL_LIST = ['claude-opus-4-7-think', 'claude-opus-4-6-think', 'claude-opus-4-5', 'claude-opus-4', 'claude-3-opus']
OpenAI_MODEL_LIST = ['gpt-6', 'gpt-5.4', 'gpt-5.1-high', 'gpt-5-high', 'o3', 'o1']
Google_MODEL_LIST = ['gemini-3.1-pro', 'gemini-2.5-pro', 'gemini-2.0', 'gemini-1.5-pro']
xAI_MODEL_LIST = ['grok-4.20', 'grok-4.1', 'grok-4', 'grok-3', 'grok-2']

def get_need_list(csv_file_path):
    data = pd.read_csv(csv_file_path)
    need_list = data['model'].tolist()
    return need_list

def json_to_excel(json_file_path, new_file_path, csv_file):
    try:
        data_origin = pd.read_csv(csv_file)
        data = pd.read_json(json_file_path)
        merged_data = pd.merge(data_origin, data, on='model', how='left', suffixes=('', '_json'))
        for col in ['elo', 'organization', 'rank', 'votes']:
            json_not_nan = merged_data[f'{col}_json'].notna()
            data_origin.loc[json_not_nan, col] = merged_data.loc[json_not_nan, f'{col}_json']
        data_origin.to_csv(new_file_path, index=False)
        print(f'JSON 文件已成功转换为 CSV 文件: {new_file_path}')
    except FileNotFoundError as e:
        print(f'文件未找到错误: {e}')
    except pd.errors.EmptyDataError as e:
        print(f'数据为空错误: {e}')
    except Exception as e:
        print(f'发生未知错误: {e}')

def _json_to_excel(json_file_path, new_file_path):
    try:
        with open(json_file_path, mode='r', encoding='utf-8') as json_file:
            data = json.load(json_file)
        fieldnames = data[0].keys()
        with open(new_file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        print(f'CSV 文件已保存为：{new_file_path}')
    except FileNotFoundError as e:
        print(f'文件未找到错误: {e}')
    except Exception as e:
        print(f'发生未知错误: {e}')

def gen_new_elo_csv():
    json_file_path = 'lmarena_leaderboard.json'
    new_file_path = 'lmarena_leaderboard_new.csv'
    csv_file_path = 'lmarena_leaderboard.csv'
    json_to_excel(json_file_path, new_file_path, csv_file_path)

def get_ranking_from_arena():
    HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    LATEST_POINTER_URL = 'https://raw.githubusercontent.com/oolong-tea-2026/arena-ai-leaderboards/main/data/latest.json'
    current_date = datetime.now().strftime('%Y-%m-%d')
    SPECIFY_DATE_RANK_URL = f'https://raw.githubusercontent.com/oolong-tea-2026/arena-ai-leaderboards/main/data/{current_date}/text.json'
    try:
        res = requests.get(LATEST_POINTER_URL, verify=True, headers=HEADERS, timeout=50)
        latest_date_code = res.status_code
        if latest_date_code != 200:
            print('latest_date arena-ai 查询失败稍后再试')
            return 'err'
        else:
            time.sleep(60)
            res = requests.get(SPECIFY_DATE_RANK_URL, verify=True, headers=HEADERS, timeout=50)
            text = res.json()
            for m in text['models'][:50]:
                print(f"#{m['rank']} {m['model']} ({m['vendor']}) — ELO {m['score']}±{m['ci']}")
            return text['models'][:50]
    except Exception as e:
        print(f'arena-ai 查询失败,e: {e}')
    return 'err'

def check_new_model(arena_list, csv_file):
    if arena_list == 'err' or not arena_list:
        print('arena-ai 查询失败稍后再试')
        return []
    data_origin = pd.read_csv(csv_file)
    new_model_list = []
    for model in arena_list:
        if model['model'] not in data_origin['model'].values and model['vendor'].lower() in OPEN_SOURCE_ORG_LIST + CLOSED_SOURCE_ORG_LIST:
            new_model_list.append({'model': model['model'], 'model_name': model['model'], 'organization': model['vendor'], 'rank': model['rank'], 'elo': model['score'], 'votes': model['votes'], 'closed/open': 'closed' if model['vendor'].lower() in CLOSED_SOURCE_ORG_LIST else 'open'})
    return new_model_list

def request_model_date(model_name_to_fetch_date):
    API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    API_KEY = ''
    client = OpenAI(base_url=API_URL.rstrip('/').rsplit('/chat/completions', 1)[0], api_key=API_KEY, http_client=httpx.Client(verify=True))
    response = client.chat.completions.create(model='qwen3.6-plus', messages=[{'role': 'user', 'content': prompt_fetch_model_date.replace('{0}', model_name_to_fetch_date)}], timeout=3600, temperature=0)
    return response.choices[0].message.content
