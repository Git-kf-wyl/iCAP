# Private iCAP Yellow implementation. Do not publish.
"""
The logic in this file largely borrows from Qwen2.5-Math codebase at https://github.com/QwenLM/Qwen2.5-Math:
"""
import re
import regex
from latex2sympy2 import latex2sympy
from math import isclose
from sympy import N, simplify
from sympy.parsing.latex import parse_latex
from sympy.parsing.sympy_parser import parse_expr as _parse_expr
import ast

def parse_expr(value):
    # Model text must not become arbitrary Python when SymPy parses expressions.
    tree=ast.parse(str(value),mode="eval")
    for node in ast.walk(tree):
        if isinstance(node,(ast.Attribute,ast.Subscript,ast.Lambda,ast.ListComp,ast.DictComp,ast.SetComp,ast.GeneratorExp,ast.NamedExpr)):
            raise ValueError("unsupported mathematical expression")
        if isinstance(node,ast.Name) and (node.id.startswith("_") or node.id in {"open","eval","exec","compile","globals","locals","getattr","setattr","input","breakpoint"}):
            raise ValueError("unsupported symbol")
        if isinstance(node,ast.Constant) and isinstance(node.value,(str,bytes)):
            raise ValueError("string literals are not mathematical expressions")
    return _parse_expr(value)
from word2number import w2n

def convert_word_number(text: str) -> str:
    try:
        text = str(w2n.word_to_num(text))
    except Exception:
        pass
    return text

def _fix_fracs(string):
    substrs = string.split('\\frac')
    new_str = substrs[0]
    if len(substrs) > 1:
        substrs = substrs[1:]
        for substr in substrs:
            new_str += '\\frac'
            if len(substr) > 0 and substr[0] == '{':
                new_str += substr
            else:
                try:
                    assert len(substr) >= 2
                except Exception:
                    return string
                a = substr[0]
                b = substr[1]
                if b != '{':
                    if len(substr) > 2:
                        post_substr = substr[2:]
                        new_str += '{' + a + '}{' + b + '}' + post_substr
                    else:
                        new_str += '{' + a + '}{' + b + '}'
                elif len(substr) > 2:
                    post_substr = substr[2:]
                    new_str += '{' + a + '}' + b + post_substr
                else:
                    new_str += '{' + a + '}' + b
    string = new_str
    return string

def _fix_a_slash_b(string):
    if len(string.split('/')) != 2:
        return string
    a = string.split('/')[0]
    b = string.split('/')[1]
    try:
        if 'sqrt' not in a:
            a = int(a)
        if 'sqrt' not in b:
            b = int(b)
        assert string == '{}/{}'.format(a, b)
        new_string = '\\frac{' + str(a) + '}{' + str(b) + '}'
        return new_string
    except Exception:
        return string

def _fix_sqrt(string):
    _string = re.sub('\\\\sqrt(\\w+)', '\\\\sqrt{\\1}', string)
    return _string

def strip_answer_string(string):
    string = str(string).strip()
    string = string.replace('\n', '')
    string = string.rstrip('.')
    string = string.replace('\\!', '')
    string = re.sub('\\\\begin\\{array\\}\\{.*?\\}', '\\\\begin{pmatrix}', string)
    string = re.sub('\\\\end\\{array\\}', '\\\\end{pmatrix}', string)
    string = string.replace('bmatrix', 'pmatrix')
    string = string.replace('tfrac', 'frac')
    string = string.replace('dfrac', 'frac')
    string = string.replace('\\neq', '\\ne').replace('\\leq', '\\le').replace('\\geq', '\\ge')
    string = string.replace('\\left', '')
    string = string.replace('\\right', '')
    string = string.replace('\\{', '{')
    string = string.replace('\\}', '}')

    def replace_match(match):
        word = match.group(1).lower()
        if convert_word_number(word) == word:
            return match.group(0)
        else:
            return convert_word_number(word)
    string = re.sub('\\\\text\\{([a-zA-Z]+)\\}', replace_match, string)
    string = re.sub('(cm|inches)\\}\\^2', '\\1}', string)
    _string = re.sub('\\\\text{.*?}$', '', string).strip()
    if _string != '' and _string != string:
        string = _string
    string = string.replace('^{\\circ}', '')
    string = string.replace('^\\circ', '')
    string = string.replace('\\$', '')
    string = string.replace('$', '')
    string = string.replace('\\(', '').replace('\\)', '')
    string = convert_word_number(string)
    string = re.sub('\\\\text\\{(.*?)\\}', '\\1', string)
    for key in ['x=', 'y=', 'z=', 'x\\in', 'y\\in', 'z\\in', 'x\\to', 'y\\to', 'z\\to']:
        string = string.replace(key, '')
    string = string.replace('\\emptyset', '{}')
    string = string.replace('(-\\infty,\\infty)', '\\mathbb{R}')
    string = string.replace('\\%', '')
    string = string.replace('\\%', '')
    string = string.replace('%', '')
    string = string.replace(' .', ' 0.')
    string = string.replace('{.', '{0.')
    if string.startswith('{') and string.endswith('}') and string.isalnum() or (string.startswith('(') and string.endswith(')') and string.isalnum()) or (string.startswith('[') and string.endswith(']') and string.isalnum()):
        string = string[1:-1]
    string = string.replace('infinity', '\\infty')
    if '\\infty' not in string:
        string = string.replace('inf', '\\infty')
    string = string.replace('+\\inity', '\\infty')
    string = string.replace('and', '')
    string = string.replace('\\mathbf', '')
    string = re.sub('\\\\mbox{.*?}', '', string)
    string.replace("'", '')
    string.replace('"', '')
    if 'j' in string and 'i' not in string:
        string = string.replace('j', 'i')
    string = re.sub('(\\d+)\\.0*([^\\d])', '\\1\\2', string)
    string = re.sub('(\\d+)\\.0*$', '\\1', string)
    if len(string) == 0:
        return string
    if string[0] == '.':
        string = '0' + string
    if len(string.split('=')) == 2:
        if len(string.split('=')[0]) <= 2:
            string = string.split('=')[1]
    string = _fix_sqrt(string)
    string = string.replace(' ', '')
    string = _fix_fracs(string)
    string = _fix_a_slash_b(string)
    string = re.sub('\\\\(?=\\-?\\d+(\\\\|\\)|,|\\]|$))', '', string)
    string = re.sub('thgrade$', '', string)
    if re.fullmatch('(\\s*-?\\d+\\s*,)*\\s*-?\\d+\\s*', string):
        try:
            integer_list = list(map(int, string.split(',')))
        except Exception:
            integer_list = list(map(int, '-1,-1'.split(',')))
        sorted_list = sorted(integer_list)
        string = ','.join(map(str, sorted_list))
    return string

def extract_answer_new(text):
    match = re.search('\\\\boxed\\{(.*?)\\}', text)
    if match:
        return match.group(1)
    return ''

def extract_answer(pred_str, use_last_number=True):
    pred_str = pred_str.replace('ки', '')
    if 'final answer is $' in pred_str and '$. I hope' in pred_str:
        tmp = pred_str.split('final answer is $', 1)[1]
        pred = tmp.split('$. I hope', 1)[0].strip()
    elif 'boxed' in pred_str:
        ans = pred_str.split('boxed')[-1]
        if len(ans) == 0:
            return ''
        elif ans[0] == '{':
            stack = 1
            a = ''
            for c in ans[1:]:
                if c == '{':
                    stack += 1
                    a += c
                elif c == '}':
                    stack -= 1
                    if stack == 0:
                        break
                    a += c
                else:
                    a += c
        else:
            a = ans.split('$')[0].strip()
        pred = a
    elif 'he answer is' in pred_str:
        pred = pred_str.split('he answer is')[-1].strip()
    elif 'final answer is' in pred_str:
        pred = pred_str.split('final answer is')[-1].strip()
    elif '答案是' in pred_str:
        pred = pred_str.split('答案是')[1].strip().split('\n\n')[0].strip()
    elif use_last_number:
        pattern = '-?\\d*\\.?\\d+'
        pred = re.findall(pattern, pred_str.replace(',', ''))
        if len(pred) >= 1:
            pred = pred[-1]
        else:
            pred = ''
    else:
        pred = ''
    pred = re.sub('\\n\\s*', '', pred)
    if pred != '' and pred[0] == ':':
        pred = pred[1:]
    if pred != '' and pred[-1] == '.':
        pred = pred[:-1]
    if pred != '' and pred[-1] == '/':
        pred = pred[:-1]
    pred = strip_answer_string(pred)
    return pred

def choice_answer_clean(pred: str):
    pred = pred.strip('\n').rstrip('.').rstrip('/').strip(' ').lstrip(':')
    tmp = re.findall('\\b(A|B|C|D|E)\\b', pred.upper())
    if tmp:
        pred = tmp
    else:
        pred = [pred.strip().strip('.')]
    pred = pred[-1]
    pred = pred.rstrip('.').rstrip('/')
    return pred

def parse_digits(num):
    num = regex.sub(',', '', str(num))
    try:
        return float(num)
    except Exception:
        if num.endswith('%'):
            num = num[:-1]
            if num.endswith('\\'):
                num = num[:-1]
            try:
                return float(num) / 100
            except Exception:
                pass
    return None

def is_digit(num):
    return parse_digits(num) is not None

def str_to_pmatrix(input_str):
    input_str = input_str.strip()
    matrix_str = re.findall('\\{.*,.*\\}', input_str)
    pmatrix_list = []
    for m in matrix_str:
        m = m.strip('{}')
        pmatrix = '\\begin{pmatrix}' + m.replace(',', '\\') + '\\end{pmatrix}'
        pmatrix_list.append(pmatrix)
    return ', '.join(pmatrix_list)

def math_equal(prediction, reference, include_percentage: bool=True, is_close: bool=True, timeout: bool=False) -> bool:
    """
    Exact match of math if and only if:
    1. numerical equal: both can convert to float and are equal
    2. symbolic equal: both can convert to sympy expression and are equal
    """
    if prediction is None or reference is None:
        return False
    if str(prediction.strip().lower()) == str(reference.strip().lower()):
        return True
    if reference in ['A', 'B', 'C', 'D', 'E'] and choice_answer_clean(prediction) == reference:
        return True
    try:
        if is_digit(prediction) and is_digit(reference):
            prediction = parse_digits(prediction)
            reference = parse_digits(reference)
            if include_percentage:
                gt_result = [reference / 100, reference, reference * 100]
            else:
                gt_result = [reference]
            for item in gt_result:
                try:
                    if is_close:
                        if numeric_equal(prediction, item):
                            return True
                    elif item == prediction:
                        return True
                except Exception:
                    continue
            return False
    except Exception:
        pass
    if not prediction and prediction not in [0, False]:
        return False
    reference = str(reference).strip()
    prediction = str(prediction).strip()
    if 'pmatrix' in prediction and 'pmatrix' not in reference:
        reference = str_to_pmatrix(reference)
    pred_str, ref_str = (prediction, reference)
    if prediction.startswith('[') and prediction.endswith(']') and (not reference.startswith('(')) or (prediction.startswith('(') and prediction.endswith(')') and (not reference.startswith('['))):
        pred_str = pred_str.strip('[]()')
        ref_str = ref_str.strip('[]()')
    for s in ['{', '}', '(', ')']:
        ref_str = ref_str.replace(s, '')
        pred_str = pred_str.replace(s, '')
    if pred_str.lower() == ref_str.lower():
        return True
    if regex.match('(\\(|\\[).+(\\)|\\])', prediction) is not None and regex.match('(\\(|\\[).+(\\)|\\])', reference) is not None:
        pred_parts = prediction[1:-1].split(',')
        ref_parts = reference[1:-1].split(',')
        if len(pred_parts) == len(ref_parts):
            if all([math_equal(pred_parts[i], ref_parts[i], include_percentage, is_close) for i in range(len(pred_parts))]):
                return True
    if (prediction.startswith('\\begin{pmatrix}') or prediction.startswith('\\begin{bmatrix}')) and (prediction.endswith('\\end{pmatrix}') or prediction.endswith('\\end{bmatrix}')) and (reference.startswith('\\begin{pmatrix}') or reference.startswith('\\begin{bmatrix}')) and (reference.endswith('\\end{pmatrix}') or reference.endswith('\\end{bmatrix}')):
        pred_lines = [line.strip() for line in prediction[len('\\begin{pmatrix}'):-len('\\end{pmatrix}')].split('\\\\') if line.strip()]
        ref_lines = [line.strip() for line in reference[len('\\begin{pmatrix}'):-len('\\end{pmatrix}')].split('\\\\') if line.strip()]
        matched = True
        if len(pred_lines) == len(ref_lines):
            for pred_line, ref_line in zip(pred_lines, ref_lines):
                pred_parts = pred_line.split('&')
                ref_parts = ref_line.split('&')
                if len(pred_parts) == len(ref_parts):
                    if not all([math_equal(pred_parts[i], ref_parts[i], include_percentage, is_close) for i in range(len(pred_parts))]):
                        matched = False
                        break
                else:
                    matched = False
                if not matched:
                    break
        else:
            matched = False
        if matched:
            return True
    if prediction.count('=') == 1 and reference.count('=') == 1:
        pred = prediction.split('=')
        pred = f'{pred[0].strip()} - ({pred[1].strip()})'
        ref = reference.split('=')
        ref = f'{ref[0].strip()} - ({ref[1].strip()})'
        if symbolic_equal(pred, ref) or symbolic_equal(f'-({pred})', ref):
            return True
    elif prediction.count('=') == 1 and len(prediction.split('=')[0].strip()) <= 2 and ('=' not in reference):
        if math_equal(prediction.split('=')[1], reference, include_percentage, is_close):
            return True
    elif reference.count('=') == 1 and len(reference.split('=')[0].strip()) <= 2 and ('=' not in prediction):
        if math_equal(prediction, reference.split('=')[1], include_percentage, is_close):
            return True
    if symbolic_equal(prediction, reference):
        return True
    return False

def numeric_equal(prediction: float, reference: float):
    return isclose(reference, prediction, rel_tol=0.0001)

def symbolic_equal(a, b):

    def _parse(s):
        for f in [parse_latex, parse_expr, latex2sympy]:
            try:
                return f(s.replace('\\\\', '\\'))
            except Exception:
                try:
                    return f(s)
                except Exception:
                    pass
        return s
    a = _parse(a)
    b = _parse(b)
    try:
        if str(a) == str(b) or a == b:
            return True
    except Exception:
        pass
    try:
        if a.equals(b) or simplify(a - b) == 0:
            return True
    except Exception:
        pass
    try:
        if abs(a.lhs - a.rhs).equals(abs(b.lhs - b.rhs)):
            return True
    except Exception:
        pass
    try:
        if numeric_equal(float(N(a)), float(N(b))):
            return True
    except Exception:
        pass
    try:
        if a.shape == b.shape:
            _a = a.applyfunc(lambda x: round(x, 3))
            _b = b.applyfunc(lambda x: round(x, 3))
            if _a.equals(_b):
                return True
    except Exception:
        pass
    return False
