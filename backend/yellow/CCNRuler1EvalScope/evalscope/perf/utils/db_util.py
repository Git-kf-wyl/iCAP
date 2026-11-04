# Private iCAP Yellow implementation. Do not publish.
import base64
import json
import os
import pickle
import re
import sqlite3
import sys
from datetime import datetime
from tabulate import tabulate
from typing import Dict, List
from evalscope.perf.arguments import Arguments
from evalscope.perf.utils.benchmark_util import BenchmarkData, BenchmarkMetrics
from evalscope.utils.logger import get_logger
logger = get_logger()

def encode_data(data) -> str:
    """Encodes data using base64 and pickle."""
    return base64.b64encode(pickle.dumps(data)).decode('utf-8')

def write_json_file(data, output_path):
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def transpose_results(data):
    headers = data.keys()
    rows = zip(*data.values())
    return [dict(zip(headers, row)) for row in rows]

def create_result_table(cursor):
    cursor.execute('CREATE TABLE IF NOT EXISTS result(\n                      request TEXT,\n                      start_time REAL,\n                      chunk_times TEXT,\n                      success INTEGER,\n                      response_messages TEXT,\n                      completed_time REAL,\n                      latency REAL,\n                      first_chunk_latency REAL,\n                      n_chunks INTEGER,\n                      chunk_time REAL,\n                      prompt_tokens INTEGER,\n                      completion_tokens INTEGER,\n                      max_gpu_memory_cost REAL)')

def insert_benchmark_data(cursor: sqlite3.Cursor, benchmark_data: BenchmarkData):
    request = encode_data(benchmark_data.request)
    chunk_times = json.dumps(benchmark_data.chunk_times)
    response_messages = encode_data(benchmark_data.response_messages)
    common_columns = (request, benchmark_data.start_time, chunk_times, benchmark_data.success, response_messages, benchmark_data.completed_time)
    if benchmark_data.success:
        additional_columns = (benchmark_data.query_latency, benchmark_data.first_chunk_latency, benchmark_data.n_chunks, benchmark_data.n_chunks_time, benchmark_data.prompt_tokens, benchmark_data.completion_tokens, benchmark_data.max_gpu_memory_cost)
        query = 'INSERT INTO result(\n                      request, start_time, chunk_times, success, response_messages,\n                      completed_time, latency, first_chunk_latency,\n                      n_chunks, chunk_time, prompt_tokens, completion_tokens, max_gpu_memory_cost\n                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
        cursor.execute(query, common_columns + additional_columns)
    else:
        query = 'INSERT INTO result(\n                      request, start_time, chunk_times, success, response_messages, completed_time\n                   ) VALUES (?, ?, ?, ?, ?, ?)'
        cursor.execute(query, common_columns)

def get_output_path(args: Arguments) -> str:
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(args.outputs_dir, current_time, f'{args.name or args.model_id}')
    output_path = re.sub('[<>:"|?*]', '_', output_path)
    if not os.path.exists(output_path):
        os.makedirs(output_path, exist_ok=True)
    logger.info(f'Save the result to: {output_path}')
    return output_path

def get_result_db_path(args: Arguments):
    result_db_path = os.path.join(args.outputs_dir, 'benchmark_data.db')
    logger.info(f'Save the data base to: {result_db_path}')
    if os.path.exists(result_db_path):
        logger.warning('The db file exists, delete it and start again!.')
        sys.exit(1)
    return result_db_path

def calculate_percentiles(data: List[float], percentiles: List[int]) -> Dict[int, float]:
    """
    Calculate the percentiles for a specific list of data.

    :param data: List of values for a specific metric.
    :param percentiles: List of percentiles to calculate.
    :return: Dictionary of calculated percentiles.
    """
    results = {}
    n_success_queries = len(data)
    data.sort()
    for percentile in percentiles:
        try:
            idx = int(n_success_queries * percentile / 100)
            value = data[idx] if data[idx] is not None else float('nan')
            results[percentile] = round(value, 4)
        except IndexError:
            results[percentile] = float('nan')
    return results

def get_percentile_results(result_db_path: str) -> Dict[str, List[float]]:
    """
    Compute and return quantiles for various metrics from the database results.

    :param result_db_path: Path to the SQLite database file.
    :return: Dictionary of percentiles for various metrics.
    """

    def inter_token_latencies(chunk_times_json: str) -> List[float]:
        try:
            chunk_times = json.loads(chunk_times_json)
            return [t2 - t1 for t1, t2 in zip(chunk_times[:-1], chunk_times[1:])]
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f'Error parsing chunk times: {e}')
            return []
    query_sql = 'SELECT start_time, chunk_times, success, completed_time, latency, first_chunk_latency, n_chunks, chunk_time, prompt_tokens, completion_tokens FROM result WHERE success=1'
    percentiles = [10, 25, 50, 66, 75, 80, 90, 95, 98, 99]
    with sqlite3.connect(result_db_path) as con:
        rows = con.execute(query_sql).fetchall()
    if len(rows) < len(percentiles):
        logger.info('Too little data to calculate quantiles!')
        return {}
    CHUNK_TIMES_INDEX = 1
    LATENCY_INDEX = 4
    FIRST_CHUNK_LATENCY_INDEX = 5
    PROMPT_TOKENS_INDEX = 8
    COMPLETION_TOKENS_INDEX = 9
    inter_token_latencies_all = []
    for row in rows:
        inter_token_latencies_all.extend(inter_token_latencies(row[CHUNK_TIMES_INDEX]))
    metrics = {'TTFT (s)': [row[FIRST_CHUNK_LATENCY_INDEX] for row in rows], 'ITL (s)': inter_token_latencies_all, 'Latency (s)': [row[LATENCY_INDEX] for row in rows], 'Input tokens': [row[PROMPT_TOKENS_INDEX] for row in rows], 'Output tokens': [row[COMPLETION_TOKENS_INDEX] for row in rows], 'Throughput(tokens/s)': [row[COMPLETION_TOKENS_INDEX] / row[LATENCY_INDEX] if row[LATENCY_INDEX] > 0 else float('nan') for row in rows]}
    results = {'Percentile': [f'{p}%' for p in percentiles]}
    for metric_name, data in metrics.items():
        metric_percentiles = calculate_percentiles(data, percentiles)
        results[metric_name] = [metric_percentiles[p] for p in percentiles]
    return results

def summary_result(args: Arguments, metrics: BenchmarkMetrics, result_db_path: str):
    result_path = os.path.dirname(result_db_path)
    write_json_file(args.to_dict(), os.path.join(result_path, 'benchmark_args.json'))
    data = metrics.create_message()
    data.update({'Expected number of requests': args.number, 'Result DB path': result_db_path})
    write_json_file(data, os.path.join(result_path, 'benchmark_summary.json'))
    table = tabulate(list(data.items()), headers=['Key', 'Value'], tablefmt='grid')
    logger.info('\nBenchmarking summary:\n' + table)
    percentile_result = get_percentile_results(result_db_path)
    if percentile_result:
        write_json_file(transpose_results(percentile_result), os.path.join(result_path, 'benchmark_percentile.json'))
        table = tabulate(percentile_result, headers='keys', tablefmt='pretty')
        logger.info('\nPercentile results:\n' + table)
    if args.dataset.startswith('speed_benchmark'):
        speed_benchmark_result(result_db_path)

def speed_benchmark_result(result_db_path: str):
    query_sql = '\n        SELECT\n            prompt_tokens,\n            ROUND(AVG(completion_tokens / latency), 2) AS avg_completion_token_per_second,\n            ROUND(AVG(max_gpu_memory_cost), 2)\n        FROM\n            result\n        WHERE\n            success = 1 AND latency > 0\n        GROUP BY\n            prompt_tokens\n    '
    with sqlite3.connect(result_db_path) as con:
        cursor = con.cursor()
        cursor.execute(query_sql)
        rows = cursor.fetchall()
    headers = ['Prompt Tokens', 'Speed(tokens/s)', 'GPU Memory(GB)']
    data = [dict(zip(headers, row)) for row in rows]
    table = tabulate(data, headers='keys', tablefmt='pretty')
    logger.info('\nSpeed Benchmark Results:\n' + table)
    result_path = os.path.dirname(result_db_path)
    write_json_file(data, os.path.join(result_path, 'speed_benchmark.json'))
