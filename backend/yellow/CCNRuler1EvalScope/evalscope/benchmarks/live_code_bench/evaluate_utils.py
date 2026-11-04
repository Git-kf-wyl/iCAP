# Private iCAP Yellow implementation. Do not publish.
import json
import multiprocessing
import numpy as np
from collections import defaultdict
from evalscope.utils.logger import get_logger
from .pass_k_utils import compute_metrics_from_results
logger = get_logger()

def codegen_check_correctness(sample, generation, timeout, debug=True):
    from code_sandbox import check
    return check(sample,generation,timeout,debug)


def evaluate_generations_by_problem(problem_generations: list, sample: list, debug: bool, timeout: int):
    """Evaluate each problem.

    Args:
        problem_generations:
        sample:
        debug:
        timeout
    """
    res = []
    metadata = []
    for o_idx, o in enumerate(problem_generations):
        curr_res = [-2]
        try:
            curr_res, curr_metadata = codegen_check_correctness(sample, o, timeout=timeout, debug=debug)
            if debug:
                logger.info(f'\nSuccessful compilation of task {o_idx}!')
            fixed = []
            for e in curr_res:
                if isinstance(e, np.ndarray):
                    e = e.item(0)
                if isinstance(e, np.bool_):
                    e = bool(e)
                fixed.append(e)
            curr_res = fixed
            if not np.all(curr_res):
                if debug:
                    logger.info(f'Results were not True for all test cases curr_res={curr_res!r}\n')
        except Exception as e:
            if debug:
                logger.info(f'Compilation failed, test framework exception = {repr(e)}{e}\n')
            curr_metadata = {}
        finally:
            assert isinstance(curr_res, list)
            assert isinstance(curr_metadata, dict)
            res.append(curr_res)
            metadata.append(curr_metadata)
    if debug:
        for i, r in enumerate(problem_generations):
            logger.info(f'Sample\n{r}\nResult\n{res[i]}')
            logger.info('*' * 30 + '\n\n')
    return (res, metadata)

def evaluate_generations(samples_list: list, generations_list: list[list[str]], debug: bool=False, num_process_evaluate: int=16, timeout=6):
    """We take the list of code generations and try to compile them and the run
    their corresponding unit tests which are retrieved from the APPS dataset.

    Args:
        generations: list of code generations (same order as samples in APPS
            dataset)
        level: difficulty level used in the generation, can be "all",
            "introductory", "interview" or "competition"

    Returns:
        results: dictionary of results, key is the problem index, value is
            a list of results for each generation
        [-2] = compile error, [-1] = runtime error [False] = failed test
            case [True] = passed test case
    """
    results = {}
    metadata = {}
    for index in range(len(generations_list)):
        problem_generations = generations_list[index]
        sample = samples_list[index]
        result, meta = evaluate_generations_by_problem(problem_generations, sample, debug, timeout)
        results[index] = result
        metadata[index] = meta
    assert len(results) == len(generations_list), f'results = {len(results)} inputs = {len(generations_list)} results={results!r}'
    return (results, metadata)

def codegen_metrics(samples_list, generations_list, k_list=[1, 5, 10, 20, 40, 50, 75, 100, 125, 150, 200, 500, 1000], num_process_evaluate=16, timeout=6, debug=False):
    samples_linear = []
    generations_linear = []
    remap_index = []
    results = defaultdict(list)
    metadatas = defaultdict(list)
    for idx, (sample, generation_list) in enumerate(zip(samples_list, generations_list)):
        assert isinstance(generation_list, list), generations_list[0]
        for generation in generation_list:
            assert isinstance(generation, str), generations_list[0]
            samples_linear.append(sample)
            generations_linear.append([generation])
            remap_index.append(idx)
    results_linear, metadatas_linear = evaluate_generations(samples_linear, generations_linear, debug=debug, num_process_evaluate=num_process_evaluate, timeout=timeout)
    for idx, sub_results in sorted(results_linear.items(), key=lambda x: x[0]):
        results[remap_index[idx]].append(sub_results[0])
    for idx, sub_metadatas in sorted(metadatas_linear.items(), key=lambda x: x[0]):
        metadatas[remap_index[idx]].append(sub_metadatas[0])
    metrics = compute_metrics_from_results(results, k_list=k_list)
    final_metadata = []
    for key in sorted(list(metadatas.keys())):
        final_metadata.append(metadatas[key])
    for i in range(len(final_metadata)):
        if type(final_metadata[i]) is not list:
            final_metadata[i] = [json.dumps(final_metadata[i])]
        else:
            final_metadata[i] = [json.dumps(x) for x in final_metadata[i]]
        assert len(final_metadata[i]) == len(generations_list[0]), f'len(final_metadata[i])={len(final_metadata[i])!r}'
    return [metrics, results, final_metadata]
