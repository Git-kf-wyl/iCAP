# Private iCAP Yellow business implementation. Do not publish.
"""
paperAgent - arXiv 每日论文自动化处理服务
运行在独立端口 7303，通过 adapter.py (:8081) 统一暴露给前端

本服务封装了 paperAgent 的核心功能（arXiv论文获取、LLM分析、Excel报告生成），
以 REST API 形式对外提供，支持异步任务执行和结果查询。

"""
from state_storage import open_state, state_exists, state_isfile
import json
import ast
import os
import re
import time
import datetime
import threading
import random
import urllib3
import logging
import sys
from io import BytesIO
from urllib.parse import urlencode
import requests
import httpx
import feedparser
import pandas as pd
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from utils.consts import PROXY_URL
proxies = {}
transport = httpx.HTTPTransport(retries=3, verify=True)
http_client = httpx.Client(transport=transport, timeout=180)
API_ENDPOINT = 'http://127.0.0.1:1/unconfigured'
MAX_PAPERS_DEMO = 10
MAX_PAPERS_FULL = 200
WORK_DIR = os.getcwd()
PAPER_RESULT_DIR = os.path.join(WORK_DIR, 'paper_agent_results')
PAPER_LOG_DIR = os.path.join(WORK_DIR, 'paper_agent_logs')
PAPER_PNG_DIR = os.path.join(WORK_DIR, 'paper_agent_png')
PAPER_ORIGINAL_DIR = os.path.join(WORK_DIR, 'paper_agent_original')
PAPER_PDF_DIR = os.path.join(WORK_DIR, 'paper_agent_pdf')
for d in [PAPER_RESULT_DIR, PAPER_LOG_DIR, PAPER_PNG_DIR, PAPER_ORIGINAL_DIR, PAPER_PDF_DIR]:
    os.makedirs(d, exist_ok=True)
ALLOWED_CATEGORIES = [('语言模型/推理模型', 'LLM/LRM'), ('视觉模型/多模态', 'VLM/VLA'), ('AI Agent/智能体', 'AGENT'), ('传统机器学习', 'ML'), ('决策推理', 'Deci/Reason'), ('仿真', 'Simu'), ('推荐搜索', 'Reco/Search'), ('其他', 'Other')]
CATEGORY_NAMES = [c[0] for c in ALLOWED_CATEGORIES]
PAPER_SEARCH_DIR = os.path.join(WORK_DIR, 'paper_agent_search')
os.makedirs(PAPER_SEARCH_DIR, exist_ok=True)
app = Flask(__name__)
CORS(app)
task_status = {'running': False, 'last_run_time': None, 'last_run_duration': None, 'last_run_status': None, 'last_run_paper_count': 0, 'last_run_error': None, 'current_progress': '', 'current_stage': ''}
logger = logging.getLogger('paper_agent_server')
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    fh = logging.FileHandler(os.path.join(PAPER_LOG_DIR, f'server_{datetime.date.today()}.log'), mode='a', encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

def update_status(**kwargs):
    """线程安全地更新任务状态"""
    for k, v in kwargs.items():
        task_status[k] = v
    logger.info(f'[STATUS] {json.dumps({k: kwargs[k] for k in kwargs}, ensure_ascii=False)}')

def chat(prompt):
    from call_api import get_response_chat
    return get_response_chat(query=prompt)

def get_daily_ai_papers(max_results=50, query_date=None):
    """从arXiv API获取cs.AI领域的最新论文"""
    if query_date is None:
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        query_date = utc_now.date() - datetime.timedelta(days=1)
    start_index = 0
    batch_size = 100
    total_results = 0
    daily_papers = []
    base_params = {'search_query': 'cat:cs.AI', 'sortBy': 'submittedDate', 'sortOrder': 'descending'}
    logger.info(f'正在获取cs.AI领域的最新论文（最多 {max_results} 篇）...')
    try:
        while total_results < max_results:
            batch_size = random.randint(90, 100)
            params = base_params.copy()
            params.update({'start': start_index, 'max_results': min(batch_size, max_results - total_results)})
            url = f'https://export.arxiv.org/api/query?{urlencode(params)}'
            logger.info(f'请求: {url}')
            success = False
            for attempt in range(3):
                try:
                    response = requests.get(url, timeout=15, proxies=proxies, verify=True)
                    response.raise_for_status()
                    success = True
                    break
                except Exception as e:
                    logger.warning(f'第{attempt + 1}次尝试失败：{e}，3秒后重试...')
                    time.sleep(3)
            if not success:
                logger.error('连续3次请求失败，无法连接arXiv。')
                break
            feed = feedparser.parse(response.content)
            if not feed.entries:
                logger.info('没有可以获取的论文了。')
                break
            page_count = 0
            for entry in feed.entries:
                try:
                    published = datetime.datetime.strptime(entry.published, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
                    if published.date() >= query_date or (published.date() == query_date - datetime.timedelta(days=1) and published.hour >= 18):
                        authors = [a.name for a in entry.authors]
                        pdf_url = None
                        for link in entry.links:
                            if link.get('title') == 'pdf' or link.get('type') == 'application/pdf':
                                pdf_url = link.href
                                break
                        if not pdf_url:
                            pdf_url = entry.id.replace('abs', 'pdf') + '.pdf'
                        arxiv_comment = getattr(entry, 'arxiv_comment', None)
                        daily_papers.append({'title': entry.title.replace('\n', ' ').strip(), 'authors': authors, 'abstract': entry.summary.replace('\n', ' ').strip(), 'published': published.isoformat(), 'pdf_url': pdf_url, 'entry_id': entry.id, 'primary_category': entry.tags[0]['term'] if entry.tags else 'cs.AI', 'arxiv_comment': arxiv_comment})
                        page_count += 1
                        total_results += 1
                        if total_results >= max_results:
                            break
                    elif published.date() > query_date:
                        continue
                    else:
                        logger.info(f'在位置 {start_index + page_count} 遇到非当天论文 ({published.date()})')
                        return daily_papers
                except Exception as e:
                    logger.warning(f'处理条目时出错: {e}')
            logger.info(f'获取了 {page_count} 篇论文')
            start_index += len(feed.entries)
            if len(feed.entries) < batch_size:
                break
            logger.info('sleep 60s, 避免请求过快')
            time.sleep(3)
    except requests.exceptions.RequestException as e:
        logger.error(f'API请求错误: {e}')
    except Exception as e:
        logger.error(f'意外错误: {e}')
    return daily_papers

def translate_abstract(abstract_en):
    """调用LLM翻译英文摘要为中文"""
    prompt = f'你是一个人工智能领域专家，你的任务是将下面的论文摘要翻译为中文。\n    要求清晰、准确、专业，不能与原英文摘要内容不符。请直接输出中文摘要。\n    【英文摘要】：{abstract_en}'
    try:
        logger.info('调用大模型API翻译摘要...')
        llm_response = chat(prompt)
        if ' response' in llm_response:
            answer_part = llm_response.split(' response', 1)[1].strip()
        else:
            answer_part = llm_response.strip()
        return answer_part
    except Exception as e:
        logger.error(f'摘要翻译失败: {e}')
        return ''

def call_llm_api(text):
    """调用大模型API进行论文内容分析（创新点、关键词、分类等）"""
    json_format = '{"创新点总结":"...", "关键词":"...", "机构":"...", "归类":"...", "核心技术":"...", "应用方向":"..."}'
    prompt = f"现在有论文内容如下：\n    {text}\n\n    请严格按以下要求处理学术论文内容：\n    1. 创新点总结：总结概括论文的核心创新点和贡献（200字以内）\n    2. 关键词：提取原文的关键词，翻译成中文的关键词\n    3. 机构：使用提供的机构信息，尽量使用中文名称\n    4. 归类：在以下类别中选择['语言模型/推理模型','推荐搜索','决策推理','视觉模型/多模态','AI Agent/智能体','仿真','传统机器学习','其他']\n    5. 核心技术：在以下类别中选择['强化学习','性能优化','训练方法','评测集','时序技术','图学习','数据技术','特征学习','AI Agent/智能体','其他']\n    6. 应用方向：在以下类别中选择['基础研究','运维','机器人/具身','3D建模','医学医药','通信','金融','AI for 科学','时空数据','图Graph','其他']\n\n    使用json格式输出，仅输出json，不用输出其他额外的分析内容，格式参考{json_format}\n    "
    return chat(prompt)

def extract_json_from_response(model_response):
    """从模型响应中提取JSON格式的答案内容"""
    if ' response' in model_response:
        answer_part = model_response.split(' response', 1)[1].strip()
    else:
        answer_part = model_response.strip()
    json_pattern = '\\{[\\s\\S]*\\}'
    json_match = re.search(json_pattern, answer_part)
    if json_match:
        json_str = json_match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                fixed_json = re.sub('([{,]\\s*)(\\w+)(\\s*:)', '\\1"\\2"\\3', json_str)
                fixed_json = fixed_json.replace("'", '"')
                fixed_json = re.sub(',\\s*([}\\]])', '\\1', fixed_json)
                return json.loads(fixed_json)
            except:
                pass
    code_block_match = re.search('```(?:json)?\\s*([\\s\\S]+?)\\s*```', answer_part)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except:
            json_match = re.search('\\{[\\s\\S]*\\}', code_block_match.group(1))
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except:
                    pass
    try:
        return json.loads(answer_part)
    except:
        return None

def download_pdf(url, save_path):
    """下载PDF文件"""
    if state_exists(save_path):
        logger.info(f'{save_path} 已存在，跳过下载')
        return save_path
    response = requests.get(url, verify=True, proxies=proxies)
    with open_state(save_path, 'wb') as f:
        f.write(response.content)
    logger.info(f'{save_path} 已下载')
    return save_path

def extract_text_from_pdf(pdf_path):
    """从PDF提取文本（使用pdfplumber）"""
    try:
        import pdfplumber
        full_text = ''
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ''
                full_text += page_text + '\n\n'
        logger.info(f'已解析文本字符{len(full_text)}')
        return full_text[:15000]
    except ImportError:
        logger.warning('pdfplumber未安装，跳过PDF文本提取')
        return ''
    except Exception as e:
        logger.warning(f'PDF解析失败: {e}')
        return ''

def parse_one(pdf_url, pdf_save_path):
    """解析单篇论文：下载PDF -> 提取文本 -> LLM分析 -> JSON解析"""
    try:
        logger.info('下载PDF文件中...')
        pdf_path = download_pdf(pdf_url, pdf_save_path)
        logger.info('解析PDF内容...')
        pdf_text = extract_text_from_pdf(pdf_path)
        if not pdf_text:
            return {}
        logger.info('调用大模型API进行总结...')
        llm_response = call_llm_api(pdf_text)
        logger.info('解析API响应...')
        result = extract_json_from_response(llm_response)
        return result or {}
    except Exception as e:
        logger.error(f'处理过程中出错: {str(e)}')
        return {}

def save_to_excel(df, excel_path):
    """将DataFrame写入格式化的Excel文件"""
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        pdf_col_idx = df.columns.get_loc('pdf_url') + 1
        name_url_col_idx = df.columns.get_loc('entry_id') + 1
        for row_idx, (pdf_url, name_url) in enumerate(zip(df['pdf_url'], df['entry_id']), start=2):
            cell_pdf = worksheet.cell(row=row_idx, column=pdf_col_idx)
            cell_pdf.value = pdf_url
            cell_pdf.hyperlink = pdf_url
            cell_pdf.style = 'Hyperlink'
            cell_name_url = worksheet.cell(row=row_idx, column=name_url_col_idx)
            cell_name_url.value = name_url
            cell_name_url.hyperlink = name_url
            cell_name_url.style = 'Hyperlink'

def recommend_papers_llm(papers):
    """让LLM从论文列表中推荐并给出理由"""
    paper_list_text = ''
    for i, p in enumerate(papers, 1):
        paper_list_text += f"\n【论文{i}】\n标题: {p['title']}\n摘要: {p['abstract'][:300]}\n链接: {p['entry_id']}\n"
    prompt = f'你是一个AI研究专家。以下是今天arXiv cs.AI领域的最新论文列表：\n\n{paper_list_text}\n\n请完成以下任务：\n1. 对每篇论文用一句话总结其核心贡献\n2. 从研究价值和创新性角度，推荐你认为最值得阅读的Top 3论文\n3. 对每篇推荐论文说明推荐理由（适合什么研究方向的人阅读）\n\n请用中文回答，格式清晰。'
    return chat(prompt)

def run_pipeline(max_papers, mode='full'):
    """运行论文管线（异步执行）"""
    try:
        update_status(running=True, current_stage='fetching', current_progress='正在从arXiv获取论文...', last_run_error=None)
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        query_date = utc_now.date() - datetime.timedelta(days=1)
        if utc_now.date().weekday() == 0:
            query_date = utc_now.date() - datetime.timedelta(days=3)
        csv_name = f'papers_{query_date}'
        update_status(current_progress='正在从arXiv API获取论文...')
        papers = get_daily_ai_papers(max_results=max_papers, query_date=query_date)
        if not papers:
            update_status(running=False, current_stage='done', current_progress='没有获取到论文', last_run_status='success', last_run_paper_count=0)
            return
        update_status(current_progress=f'已获取 {len(papers)} 篇论文，开始LLM分析...', current_stage='analyzing')
        df = pd.DataFrame(papers)
        original_csv = os.path.join(PAPER_ORIGINAL_DIR, f'{csv_name}.csv')
        df.to_csv(original_csv, index=False, encoding='utf_8_sig')
        pdf_dir = os.path.join(PAPER_PDF_DIR, csv_name)
        os.makedirs(pdf_dir, exist_ok=True)
        df = pd.read_csv(original_csv)
        for i in df.index:
            if 'processed' in df.loc[i] and df.loc[i]['processed'] == 'True':
                continue
            update_status(current_progress=f'正在分析第 {i + 1}/{len(df.index)} 篇论文...')
            abstract_chn = translate_abstract(df.loc[i]['abstract'])
            df.at[i, '摘要'] = abstract_chn
            pdf_url = df.loc[i]['pdf_url']
            pdf_name = pdf_url.split('/')[-1]
            pdf_save_path = os.path.join(pdf_dir, f'{pdf_name}.pdf')
            try:
                result_one = parse_one(pdf_url=pdf_url, pdf_save_path=pdf_save_path)
                if result_one:
                    for k, v in result_one.items():
                        try:
                            df.at[i, k] = v
                        except Exception:
                            pass
                    df.at[i, 'processed'] = True
                df.to_csv(os.path.join(PAPER_RESULT_DIR, f'{csv_name}_parsed.csv'), index=False, encoding='utf_8_sig')
            except Exception as e:
                logger.error(f'论文{i}分析失败: {e}')
        update_status(current_progress='正在生成Excel报告...', current_stage='generating')
        excel_path = os.path.join(PAPER_RESULT_DIR, f'{csv_name}_parsed.xlsx')
        save_to_excel(df, excel_path)
        csv_path = os.path.join(PAPER_RESULT_DIR, f'{csv_name}_parsed.csv')
        df.to_csv(csv_path, index=False, encoding='utf_8_sig')
        update_status(running=False, current_stage='done', current_progress='管线运行完成' + f'成功处理 {len(papers)} 篇论文', last_run_status='success', last_run_time=datetime.datetime.now().isoformat(), last_run_paper_count=len(papers))
    except Exception as e:
        logger.error(f'管线运行失败: {e}')
        update_status(running=False, current_stage='done', current_progress=f'运行失败: {str(e)}', last_run_status='failed', last_run_error=str(e))

def run_demo_pipeline():
    """运行快速演示（异步）"""
    try:
        update_status(running=True, current_stage='fetching', current_progress='正在从arXiv获取论文（快速模式）...', last_run_error=None)
        papers = get_daily_ai_papers(max_results=MAX_PAPERS_DEMO)
        if not papers:
            update_status(running=False, current_stage='done', current_progress='没有获取到论文', last_run_status='success', last_run_paper_count=0)
            return
        update_status(current_progress=f'已获取 {len(papers)} 篇论文，正在调用LLM分析推荐...', current_stage='analyzing')
        recommendation = recommend_papers_llm(papers)
        update_status(running=False, current_stage='done', current_progress='快速演示完成', last_run_status='success', last_run_time=datetime.datetime.now().isoformat(), last_run_paper_count=len(papers))
        result = {'papers': papers, 'recommendation': recommendation, 'timestamp': datetime.datetime.now().isoformat()}
        result_path = os.path.join(PAPER_RESULT_DIR, f'demo_{datetime.date.today().isoformat()}.json')
        with open_state(result_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f'快速演示失败: {e}')
        update_status(running=False, current_stage='done', current_progress=f'演示失败: {str(e)}', last_run_status='failed', last_run_error=str(e))

@app.route('/v1/paper_agent/status', methods=['GET'])
def get_status():
    """获取当前任务状态"""
    return (jsonify(task_status), 200)

@app.route('/v1/paper_agent/fetch_and_analyze', methods=['POST'])
def fetch_and_analyze():
    """触发完整论文管线（异步执行）"""
    if task_status['running']:
        return (jsonify({'error': '任务正在运行中，请等待完成'}), 409)
    data = request.get_json() or {}
    max_papers = data.get('max_papers', MAX_PAPERS_FULL)
    thread = threading.Thread(target=run_pipeline, args=(max_papers, 'full'))
    thread.daemon = True
    thread.start()
    return (jsonify({'message': '任务已启动', 'status': 'running'}), 202)

@app.route('/v1/paper_agent/quick_demo', methods=['POST'])
def quick_demo():
    """触发快速演示（异步执行）"""
    if task_status['running']:
        return (jsonify({'error': '任务正在运行中，请等待完成'}), 409)
    thread = threading.Thread(target=run_demo_pipeline)
    thread.daemon = True
    thread.start()
    return (jsonify({'message': '快速演示已启动', 'status': 'running'}), 202)

@app.route('/v1/paper_agent/results', methods=['GET'])
def list_results():
    """列出所有生成的结果文件"""
    files = []
    try:
        for f in os.listdir(PAPER_RESULT_DIR):
            file_path = os.path.join(PAPER_RESULT_DIR, f)
            if state_isfile(file_path):
                ext = os.path.splitext(f)[1].lower()
                if ext in ('.xlsx', '.csv', '.json'):
                    stat = os.stat(file_path)
                    files.append({'filename': f, 'size': stat.st_size, 'modified': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(), 'type': ext})
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)
    files.sort(key=lambda x: x['modified'], reverse=True)
    return (jsonify(files), 200)

@app.route('/v1/paper_agent/results/<filename>', methods=['GET'])
def download_result(filename):
    """下载指定的结果文件"""
    if '..' in filename or '/' in filename or '\\' in filename:
        return (jsonify({'error': '非法的文件名'}), 400)
    file_path = os.path.join(PAPER_RESULT_DIR, filename)
    if not state_exists(file_path):
        return (jsonify({'error': f'文件 {filename} 不存在'}), 404)
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {'.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.csv': 'text/csv; charset=utf-8', '.json': 'application/json; charset=utf-8'}
    return send_file(file_path, mimetype=mime_map.get(ext, 'application/octet-stream'), as_attachment=True, download_name=filename)

@app.route('/v1/paper_agent/latest_excel', methods=['GET'])
def get_latest_excel():
    """获取最新生成的Excel报告文件"""
    try:
        xlsx_files = [f for f in os.listdir(PAPER_RESULT_DIR) if f.lower().endswith('.xlsx')]
        if not xlsx_files:
            return (jsonify({'error': '暂无Excel报告'}), 404)
        latest = max(xlsx_files, key=lambda f: os.path.getmtime(os.path.join(PAPER_RESULT_DIR, f)))
        file_path = os.path.join(PAPER_RESULT_DIR, latest)
        return send_file(file_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=latest)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/paper_agent/latest_demo', methods=['GET'])
def get_latest_demo():
    """获取最新的快速演示结果"""
    try:
        json_files = [f for f in os.listdir(PAPER_RESULT_DIR) if f.startswith('demo_') and f.endswith('.json')]
        if not json_files:
            return (jsonify({'error': '暂无演示结果'}), 404)
        latest = max(json_files, key=lambda f: os.path.getmtime(os.path.join(PAPER_RESULT_DIR, f)))
        file_path = os.path.join(PAPER_RESULT_DIR, latest)
        with open_state(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return (jsonify(data), 200)
    except Exception as e:
        return (jsonify({'error': str(e)}), 500)

@app.route('/v1/paper_agent/health', methods=['GET'])
def health():
    """健康检查"""
    return (jsonify({'status': 'ok', 'running': task_status['running']}), 200)
_SEARCHED_ENTRY_IDS = set()

def load_all_local_papers():
    """加载所有本地的已分析论文数据（含归类字段），返回列表"""
    all_papers = []
    seen_ids = set()
    for fname in os.listdir(PAPER_RESULT_DIR):
        if not (fname.endswith('_parsed.csv') or fname.startswith('search_pool_')):
            continue
        fpath = os.path.join(PAPER_RESULT_DIR, fname)
        try:
            df = pd.read_csv(fpath, encoding='utf_8_sig')
            for _, row in df.iterrows():
                entry_id = str(row.get('entry_id', '')).strip()
                title = str(row.get('title', '')).strip()
                dedup_key = entry_id or title
                if not dedup_key or dedup_key in seen_ids:
                    continue
                seen_ids.add(dedup_key)
                paper = {'title': title, 'authors': str(row.get('authors', '')), 'abstract': str(row.get('abstract', '')), 'published': str(row.get('published', '')), 'pdf_url': str(row.get('pdf_url', '')), 'entry_id': entry_id, 'primary_category': str(row.get('primary_category', '')), 'arxiv_comment': str(row.get('arxiv_comment', '')), '归类': str(row.get('归类', '')), '核心技术': str(row.get('核心技术', '')), '应用方向': str(row.get('应用方向', '')), '摘要': str(row.get('摘要', '')), '创新点总结': str(row.get('创新点总结', '')), '关键词': str(row.get('关键词', '')), '机构': str(row.get('机构', '')), '_source': 'local_parsed'}
                all_papers.append(paper)
        except Exception as e:
            logger.warning(f'读取本地分析文件失败 {fname}: {e}')
    search_dir = PAPER_SEARCH_DIR
    if state_exists(search_dir):
        for fname in os.listdir(search_dir):
            if not fname.endswith('.csv'):
                continue
            fpath = os.path.join(search_dir, fname)
            try:
                df = pd.read_csv(fpath, encoding='utf_8_sig')
                for _, row in df.iterrows():
                    title = str(row.get('title', '')).strip()
                    entry_id = str(row.get('entry_id', '') or row.get('链接', '')).strip()
                    dedup_key = entry_id or title
                    if not dedup_key or dedup_key in seen_ids:
                        continue
                    seen_ids.add(dedup_key)
                    published = str(row.get('发布日期', row.get('published', '')))
                    link = str(row.get('链接', row.get('entry_id', '')))
                    paper = {'title': title, 'authors': str(row.get('authors', '')), 'abstract': str(row.get('abstract', '')), 'published': published, 'pdf_url': str(row.get('pdf_url', '')), 'entry_id': link, 'primary_category': str(row.get('primary_category', '')), 'arxiv_comment': str(row.get('arxiv_comment', '')), '归类': str(row.get('归类', '')), '核心技术': str(row.get('核心技术', '')), '应用方向': str(row.get('应用方向', '')), '摘要': str(row.get('摘要', '')), '创新点总结': str(row.get('创新点总结', '')), '关键词': str(row.get('关键词', '')), '机构': str(row.get('机构', '')), '_source': 'local_search'}
                    all_papers.append(paper)
            except Exception as e:
                logger.warning(f'读取历史搜索文件失败 {fname}: {e}')
    logger.info(f'本地共加载 {len(all_papers)} 篇论文（含归类数据）')
    return all_papers

def match_local_papers(local_papers, keywords, date_from, date_to, category, max_results):
    """从本地论文中按条件筛选匹配"""
    keyword_terms = [k.strip().lower() for k in keywords.replace('，', ',').split(',') if k.strip()]
    matched = []
    for paper in local_papers:
        title = paper.get('title', '').lower()
        abstract = paper.get('abstract', '').lower()
        if keyword_terms:
            keyword_match = any((term in title or term in abstract for term in keyword_terms))
            if not keyword_match:
                continue
        pub_str = paper.get('published', '')
        if pub_str and (date_from or date_to):
            try:
                pub_dt = datetime.datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                pub_date = pub_dt.date()
                if date_from:
                    from_dt = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
                    if pub_date < from_dt:
                        continue
                if date_to:
                    to_dt = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
                    if pub_date > to_dt:
                        continue
            except (ValueError, TypeError):
                pass
        if category:
            paper_cat = paper.get('归类', '').strip()
            if paper_cat != category:
                continue
        matched.append(paper)
        if len(matched) >= max_results:
            break
    return matched

def fetch_from_arxiv(keywords, date_from, date_to, category, max_needed, seen_entry_ids):
    """从arXiv API补充搜索（返回尚未在seen_entry_ids中的论文）"""
    keyword_terms = [k.strip() for k in keywords.replace('，', ',').split(',') if k.strip()]
    if not keyword_terms or max_needed <= 0:
        return []
    search_query_parts = []
    for term in keyword_terms:
        search_query_parts.append(f'(ti:"{term}" OR abs:"{term}")')
    search_query = 'AND'.join(search_query_parts)
    base_params = {'search_query': search_query, 'sortBy': 'submittedDate', 'sortOrder': 'descending', 'start': 0, 'max_results': min(max_needed * 2, 50)}
    url = f'https://export.arxiv.org/api/query?{urlencode(base_params)}'
    logger.info(f'arXiv补充搜索: {url}')
    try:
        response = requests.get(url, timeout=30, proxies=proxies, verify=True)
        response.raise_for_status()
    except Exception as e:
        logger.error(f'arXiv API请求失败: {e}')
        return []
    feed = feedparser.parse(response.content)
    new_papers = []
    for entry in feed.entries:
        if len(new_papers) >= max_needed:
            break
        published = None
        try:
            published = datetime.datetime.strptime(entry.published, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
        except (ValueError, AttributeError):
            continue
        if date_from:
            from_dt = datetime.datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
            if published.date() < from_dt.date():
                continue
        if date_to:
            to_dt = datetime.datetime.strptime(date_to, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
            if published.date() > to_dt.date():
                continue
        pdf_url = None
        for link in entry.links:
            if link.get('title') == 'pdf' or link.get('type') == 'application/pdf':
                pdf_url = link.href
                break
        if not pdf_url:
            pdf_url = entry.id.replace('abs', 'pdf') + '.pdf'
        entry_id = entry.id
        if entry_id in seen_entry_ids:
            continue
        seen_entry_ids.add(entry_id)
        authors_str = str([a.name for a in entry.authors])
        new_papers.append({'title': entry.title.replace('\n', ' ').strip(), 'authors': authors_str, 'abstract': entry.summary.replace('\n', ' ').strip(), 'published': published.isoformat() if published else '', 'pdf_url': pdf_url, 'entry_id': entry_id, 'primary_category': entry.tags[0]['term'] if entry.tags else 'cs.AI', 'arxiv_comment': getattr(entry, 'arxiv_comment', None) or '', '归类': '', '核心技术': '', '应用方向': '', '摘要': '', '创新点总结': '', '关键词': '', '机构': '', '_source': 'arxiv'})
    logger.info(f'arXiv补充搜索到 {len(new_papers)} 篇新论文')
    return new_papers

def normalize_paper_for_output(paper):
    """统一论文输出格式"""
    authors_raw = paper.get('authors', '')
    if isinstance(authors_raw, str) and authors_raw.startswith('[') and authors_raw.endswith(']'):
        try:
            parsed = ast.literal_eval(authors_raw)
            if isinstance(parsed, list):
                authors_raw = '; '.join(parsed)
        except:
            pass
    return {'title': paper.get('title', ''), 'authors': authors_raw, 'abstract': paper.get('abstract', ''), '发布日期': paper.get('published', ''), 'pdf_url': paper.get('pdf_url', ''), '链接': paper.get('entry_id', ''), 'primary_category': paper.get('primary_category', ''), 'arxiv_comment': paper.get('arxiv_comment', ''), '归类': paper.get('归类', ''), '核心技术': paper.get('核心技术', ''), '应用方向': paper.get('应用方向', ''), '摘要': paper.get('摘要', ''), '创新点总结': paper.get('创新点总结', ''), '关键词': paper.get('关键词', ''), '机构': paper.get('机构', '')}

@app.route('/v1/paper_agent/search', methods=['POST'])
def search_papers():
    """定制化论文搜索（混合检索策略）：
    1. 优先从本地存量数据匹配（每日管线结果 + 历史搜索结果）
    2. 不足时从arXiv API补充搜索
    3. 去重合并后按用户隔离存储

    Request body (JSON):
    {
        "keywords": "LLM, agent",
        "date_from": "2026-07-01",   // 可选，起始日期
        "date_to": "2026-07-21",     // 可选，截止日期
        "category": "语言模型/推理模型", // 可选，归类筛选
        "max_results": 20,           // 最大篇数，默认20
        "username": "xxx"            // 用户名，用于结果隔离
    }
    """
    if task_status['running']:
        return (jsonify({'error': '完整管线正在运行中，请等待完成后再搜索'}), 409)
    data = request.get_json() or {}
    keywords = data.get('keywords', '').strip()
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    category = data.get('category', '').strip()
    max_results = min(int(data.get('max_results', 20)), 20)
    username = data.get('username', 'anonymous').strip()
    if not keywords:
        return (jsonify({'error': '请输入搜索关键词'}), 400)
    try:
        logger.info(f'===== 混合搜索开始: keywords={keywords}, date_from={date_from}, date_to={date_to}, category={category}, max_results={max_results} =====')
        local_papers = load_all_local_papers()
        local_matched = match_local_papers(local_papers, keywords, date_from, date_to, category, max_results)
        logger.info(f'本地匹配到 {len(local_matched)} 篇论文')
        matched_ids = set()
        for p in local_matched:
            eid = p.get('entry_id', '').strip()
            if eid:
                matched_ids.add(eid)
        need = max_results - len(local_matched)
        arxiv_papers = []
        if need > 0:
            logger.info(f'本地不足，需要从arXiv补充 {need} 篇')
            arxiv_papers = fetch_from_arxiv(keywords, date_from, date_to, category, need, matched_ids)
        all_results = []
        seen_in_result = set()
        for p in local_matched:
            normalized = normalize_paper_for_output(p)
            dedup_key = normalized['链接'] or normalized['title']
            if dedup_key and dedup_key not in seen_in_result:
                seen_in_result.add(dedup_key)
                all_results.append(normalized)
        for p in arxiv_papers:
            normalized = normalize_paper_for_output(p)
            dedup_key = normalized['链接'] or normalized['title']
            if dedup_key and dedup_key not in seen_in_result:
                seen_in_result.add(dedup_key)
                all_results.append(normalized)
        final_count = len(all_results)
        local_count = len(local_matched)
        arxiv_count = len(arxiv_papers)
        logger.info(f'最终结果: 本地贡献 {local_count} 篇, arXiv补充 {arxiv_count} 篇, 总计 {final_count} 篇')
        if final_count == 0:
            return (jsonify({'error': '未搜索到相关论文'}), 404)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_username = re.sub('[^\\w\\-_]', '_', username)
        result_filename = f'search_{safe_username}_{timestamp}.csv'
        result_path = os.path.join(PAPER_SEARCH_DIR, result_filename)
        df = pd.DataFrame(all_results)
        df.to_csv(result_path, index=False, encoding='utf_8_sig')
        user_latest = os.path.join(PAPER_SEARCH_DIR, f'latest_{safe_username}.csv')
        df.to_csv(user_latest, index=False, encoding='utf_8_sig')
        pool_path = os.path.join(PAPER_RESULT_DIR, f'search_pool_{safe_username}_{timestamp}.csv')
        df.to_csv(pool_path, index=False, encoding='utf_8_sig')
        return (jsonify({'message': '搜索成功', 'filename': result_filename, 'count': final_count, 'local_count': local_count, 'arxiv_count': arxiv_count}), 200)
    except Exception as e:
        logger.error(f'搜索失败: {e}')
        return (jsonify({'error': f'搜索失败: {str(e)}'}), 500)

@app.route('/v1/paper_agent/search_csv', methods=['GET'])
def get_search_csv():
    """获取当前用户的最新搜索CSV结果"""
    username = request.args.get('username', 'anonymous').strip()
    safe_username = re.sub('[^\\w\\-_]', '_', username)
    latest_path = os.path.join(PAPER_SEARCH_DIR, f'latest_{safe_username}.csv')
    if not state_exists(latest_path):
        return (jsonify({'error': '暂无搜索结果'}), 404)
    with open_state(latest_path, 'r', encoding='utf_8_sig') as f:
        csv_content = f.read()
    return Response(csv_content, mimetype='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename=search_{safe_username}_latest.csv'})

@app.route('/v1/paper_agent/search_results/<filename>', methods=['GET'])
def download_search_result(filename):
    """下载指定的搜索结果文件"""
    if '..' in filename or '/' in filename or '\\' in filename:
        return (jsonify({'error': '非法的文件名'}), 400)
    file_path = os.path.join(PAPER_SEARCH_DIR, filename)
    if not state_exists(file_path):
        return (jsonify({'error': f'文件 {filename} 不存在'}), 404)
    return send_file(file_path, mimetype='text/csv; charset=utf-8', as_attachment=True, download_name=filename)
