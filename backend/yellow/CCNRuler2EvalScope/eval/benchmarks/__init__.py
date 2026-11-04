# Private iCAP Yellow implementation. Do not publish.
import glob
import importlib
import os
from eval.benchmarks.benchmark import Benchmark, BenchmarkMeta
from eval.benchmarks.data_adapter import DataAdapter
from eval.utils import get_logger
logger = get_logger()
pattern = os.path.join(os.path.dirname(__file__), '*', '*_adapter.py')
files = glob.glob(pattern, recursive=False)
for file_path in files:
    if file_path.endswith('.py') and (not os.path.basename(file_path).startswith('_')):
        relative_path = os.path.relpath(file_path, os.path.dirname(__file__))
        module_path = relative_path[:-3].replace(os.path.sep, '.')
        full_path = f'eval.benchmarks.{module_path}'
        try:importlib.import_module(full_path)
        except ImportError as exc:logger.debug('Optional benchmark unavailable: %s (%s)',full_path,type(exc).__name__)
