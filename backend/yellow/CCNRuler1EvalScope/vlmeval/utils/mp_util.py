# Private iCAP Yellow implementation. Do not publish.
from multiprocessing import Pool
import os
from typing import Callable, Iterable, Sized, List
from rich.progress import BarColumn, MofNCompleteColumn, Progress, Task, TaskProgressColumn, TextColumn, TimeRemainingColumn
from rich.text import Text
import os.path as osp
import time
from vlmeval.utils.model_pool import ModelPool
import portalocker
from ..smp import load, dump
from evalscope.utils.logger import get_logger
logger = get_logger()

def model_pool_func(model_pool: ModelPool, message: List[dict], dataset=None):
    model = model_pool.get_model()
    try:
        return model.generate(message, dataset)
    finally:
        model_pool.release_model(model)

def track_progress_rich(func: Callable, tasks: Iterable=tuple(), nproc: int=1, save=None, keys=None, **kwargs) -> list:
    from concurrent.futures import ThreadPoolExecutor
    from tqdm import tqdm
    if save is not None:
        assert osp.exists(osp.dirname(save)) or osp.dirname(save) == ''
        if not osp.exists(save):
            dump({}, save)
    if keys is not None:
        assert len(keys) == len(tasks)
    if not callable(func):
        raise TypeError('func must be a callable object')
    if not isinstance(tasks, Iterable):
        raise TypeError(f'tasks must be an iterable object, but got {type(tasks)}')
    assert nproc > 0, 'nproc must be a positive number'
    res = load(save) if save is not None else {}
    results = [None for _ in range(len(tasks))]
    with ThreadPoolExecutor(max_workers=nproc) as executor:
        futures = []
        for inputs in tasks:
            if not isinstance(inputs, (tuple, list, dict)):
                inputs = (inputs,)
            if isinstance(inputs, dict):
                future = executor.submit(func, **inputs)
            else:
                future = executor.submit(func, *inputs)
            futures.append(future)
        unfinished = set(range(len(tasks)))
        pbar = tqdm(total=len(unfinished))
        logger.info(pbar)
        while len(unfinished):
            new_finished = set()
            for idx in unfinished:
                if futures[idx].done():
                    results[idx] = futures[idx].result()
                    new_finished.add(idx)
                    if keys is not None:
                        res[keys[idx]] = results[idx]
            if len(new_finished):
                if save is not None:
                    dump(res, save)
                pbar.update(len(new_finished))
                logger.info(pbar)
                for k in new_finished:
                    unfinished.remove(k)
            time.sleep(0.1)
        pbar.close()
    if save is not None:
        dump(res, save)
    return results

def track_progress(func: List, tasks: Iterable=tuple(), nproc: int=1, save=None, keys=None, **kwargs) -> list:
    from concurrent.futures import ThreadPoolExecutor
    from tqdm import tqdm
    if save is not None:
        assert osp.exists(osp.dirname(save)) or osp.dirname(save) == ''
        if not osp.exists(save):
            dump({}, save)
    if keys is not None:
        assert len(keys) == len(tasks)
    if not isinstance(tasks, Iterable):
        raise TypeError(f'tasks must be an iterable object, but got {type(tasks)}')
    assert nproc > 0, 'nproc must be a positive number'
    res = load(save) if save is not None else {}
    results = [None for _ in range(len(tasks))]
    model_adapters = []
    for fuc in func:
        model_adapters.append(fuc)
    model_pool = ModelPool(model_adapters, nproc)
    with ThreadPoolExecutor(max_workers=nproc * (len(func) if len(func) != 0 else 1)) as executor:
        futures = []
        for inputs in tasks:
            if not isinstance(inputs, (tuple, list, dict)):
                inputs = (inputs,)
            if isinstance(inputs, dict):
                future = executor.submit(model_pool_func, model_pool, **inputs)
            else:
                future = executor.submit(model_pool_func, model_pool, *inputs)
            futures.append(future)
        unfinished = set(range(len(tasks)))
        pbar = tqdm(total=len(unfinished))
        logger.info(pbar)
        while len(unfinished):
            new_finished = set()
            for idx in unfinished:
                if futures[idx].done():
                    results[idx] = futures[idx].result()
                    new_finished.add(idx)
                    if keys is not None:
                        res[keys[idx]] = results[idx]
            if len(new_finished):
                if save is not None:
                    dump(res, save)
                pbar.update(len(new_finished))
                logger.info(pbar)
                for k in new_finished:
                    unfinished.remove(k)
            time.sleep(0.1)
        pbar.close()
    if save is not None:
        dump(res, save)
    return results
