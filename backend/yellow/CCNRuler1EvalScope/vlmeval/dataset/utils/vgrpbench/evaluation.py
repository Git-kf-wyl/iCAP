# Private iCAP Yellow implementation. Do not publish.
import ast
import os
import json
import numpy as np
import pandas as pd
from collections import defaultdict
from .score import evaluate_single_puzzle

def get_eval(judge, content):
    """
    Generate evaluation using the judge model.
    
    Args:
        judge: The evaluation model
        content: Input content for the evaluation
        
    Returns:
        The generated evaluation output
    """
    return judge.generate(content)

def VGRPBench_atomeval(model, prompt, line):
    """
    Perform atomic evaluation for a VGRPBench puzzle.

    Args:
        model: The evaluation model
        prompt: Input prompt for evaluation
        line: Dictionary containing puzzle information

    Returns:
        dict: Evaluation scores
    """
    print('raw output', prompt)
    output = get_eval(model, prompt)
    print('formatted output', output)
    scores = parse_score(line, output)
    return scores

def parse_score(line, output):
    """
    Parse the score from the model's output for a VGRPBench puzzle.
    
    Args:
        line: Dictionary-like object containing puzzle information
        output: The model's output string
        
    Returns:
        dict: Dictionary with perception_correct and answer_correct results
    """
    category = line['category']
    puzzle_type = category.split('_')[0]
    puzzle_data = line['states']
    puzzle_data = ast.literal_eval(puzzle_data)
    evaluation_result = evaluate_single_puzzle(output, puzzle_data, puzzle_type)
    return evaluation_result

def VGRPBench_score(data):
    """
    Calculate scores for VGRPBench puzzles by category.
    
    Args:
        data: DataFrame containing evaluation results
        
    Returns:
        pandas.DataFrame: Aggregated scores by category
    """
    cates = list(set(data['category']))
    ret = defaultdict(list)
    for c in cates:
        ret['category'].append(c)
        sub = data[data['category'] == c]
        perception_score = round(np.mean(sub['perception_correct']) * 100, 2)
        ret['Perception Score'].append(perception_score)
        answer_score = round(np.mean(sub['answer_correct']) * 100, 2)
        ret['Answer Score'].append(answer_score)
    return pd.DataFrame(ret)

def build_prompt(line):
    """
    Build a prompt from the prediction field in the data line.
    
    Args:
        line: Dictionary containing a 'prediction' field
        
    Returns:
        str: The prediction text to be used as a prompt
    """
    return line['prediction']

def VGRPBench_get_system_prompt(line):
    """
    Get the system prompt for a specific puzzle type in VGRPBench.
    
    Args:
        line: A data row containing a 'category' field that defines the puzzle type
        
    Returns:
        str: A formatted system prompt loaded from the corresponding filter_prompt.json file
    """
    puzzle_type = line['category'].split('_')[0]
    prompt_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'configs', 'formating-prompt', puzzle_type, 'filter_prompt.json')
    with open(prompt_file, 'r') as f:
        prompt = json.load(f)
    prompt = str(prompt) + 'According to the conversation history with the user feedback do the formatting for the current answer.'
    return prompt
