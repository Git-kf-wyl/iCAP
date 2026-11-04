# Private iCAP Yellow implementation. Do not publish.
"""
Copied from https://github.com/allenai/allennlp-semparse
Modified from https://github.com/naver-ai/tablevqabench
"""
import re
import unicodedata
import time
from abc import ABCMeta, abstractmethod
from math import isinf, isnan
VWTQ_PROMPT = 'You are asked to answer questions asked on an image.\nYou should answer the question with a single word.\nExample: \nQuestion: what was the only year mr. wu competed in the olympic games?\nAnswer: 2004\nQuestion: which township in pope county, arkansas has the least amount of water area?\nAnswer: Freeman\nIf you have multiple answers, please separate them with || marks. Example: Apple||Banana||Tomato\n\nQuestion: {question}\nAnswer:'
VTABFACT_PROMPT = 'You are asked to answer whether the statement is True or False based on given image\nYou should only answer True or False.\nExample: \nStatement: the milwaukee buck win 6 game in the 2010 - 11 season\nAnswer: True\nStatement: only the top team score above the average of 8.8\nAnswer: False\n\nStatement: {question}\nAnswer:'
FINTABNETQA_PROMPT = 'You are asked to answer questions asked on a image.\nYou should answer the question within a single word or few words.\nIf units can be known, the answer should include units such as $, %, million and etc.\nExample: \nQuestion: What were the total financing originations for the fiscal year ended October 31, 2004?\nAnswer: $3,852 million\nQuestion: What is the time period represented in the table?\nAnswer: October 31\nQuestion: What was the percentage of net sales for selling, general and administrative expenses in 2006?\nAnswer: 34.2%\nQuestion: {question}\nAnswer:'

def evaluate_tabfact(data, score_keys):
    num_examples = 0
    num_correct = 0
    manual_check = 0
    start_time = time.time()
    for instance in data:
        if instance['prediction'] is None:
            instance['prediction'] = 'none'
        pred = instance['prediction'].lower()
        gt = instance['answer']
        num_examples += 1
        if 'true' in pred and 'false' in pred:
            manual_check += 1
            score = None
        elif 'true' in pred and gt == '1':
            num_correct += 1
            score = 1
        elif 'false' in pred and gt == '0':
            num_correct += 1
            score = 1
        else:
            score = 0
        instance['scores'] = {score_keys[0]: score}
    if manual_check > 0:
        print(f'the number of not properly parsed samples: {manual_check}')
    end_time = time.time()
    elapsed_time = end_time - start_time
    Accuracy = round((num_correct + 1e-09) / (num_examples + 1e-09), 8) * 100
    meta = {'evaluators': 'correctness', 'score_info': [score_keys[0]], 'evaluated_time': elapsed_time, 'total_num_sample': len(data), 'average_scores': [Accuracy]}
    return meta

def evaluate_wtq(data, score_keys):
    num_examples = 0
    num_correct = 0
    start_time = time.time()
    for instance in data:
        pred = instance['prediction'].replace('||', '|')
        gt = instance['answer']
        original_strings = tsv_unescape_list(gt)
        target_values = to_value_list(original_strings)
        predicted_strings = tsv_unescape_list(pred)
        predicted_values = to_value_list(predicted_strings)
        correct = check_denotation(target_values, predicted_values)
        num_examples += 1
        score = 0
        if correct:
            num_correct += 1
            score = 1
        instance['scores'] = {score_keys[0]: score}
    end_time = time.time()
    elapsed_time = end_time - start_time
    Accuracy = round((num_correct + 1e-09) / (num_examples + 1e-09), 8) * 100
    meta = {'evaluators': 'correctness', 'score_info': [score_keys[0]], 'evaluated_time': elapsed_time, 'total_num_sample': len(data), 'average_scores': [Accuracy]}
    return meta

def evaluate_fintabnet(data, score_keys):
    num_examples = 0
    num_correct, _num_correct = (0, 0)
    start_time = time.time()
    for instance in data:
        pred, preds = fintabnet_normalize(instance['prediction'])
        gt, gts = fintabnet_normalize(instance['answer'])
        correct = 1 if gt == pred else 0
        _correct = any((_pred == _gt for _pred in preds for _gt in gts))
        num_examples += 1
        score, _score = (0, 0)
        if correct:
            num_correct += 1
            score = 1
        if _correct:
            _num_correct += 1
            _score = 1
        instance['scores'] = {score_keys[0]: _score, 'exact_score': score}
    end_time = time.time()
    elapsed_time = end_time - start_time
    Accuracy = round((num_correct + 1e-09) / (num_examples + 1e-09), 8) * 100
    _Accuracy = round((_num_correct + 1e-09) / (num_examples + 1e-09), 8) * 100
    meta = {'evaluators': 'correctness', 'score_info': ['relieved_accuracy', score_keys[0]], 'evaluated_time': elapsed_time, 'total_num_sample': len(data), 'average_scores': [_Accuracy, Accuracy]}
    return meta

def fintabnet_normalize(s):
    s = normalize(s)
    remove_words = ['dollar', 'gallons', 'square feet', 'shares', 'mbtu', 'mbpd', 'mbbls', 'mmbtu', 'unit', 'gwh', 'year', 'mmcf', 'mile', 'mboe']
    s = re.sub('[\\$\\(\\),]', '', s)
    pattern = '\\b(' + '|'.join(remove_words) + ')s?\\b'
    s = re.sub(pattern, '', s, flags=re.IGNORECASE)
    unit_conversion = {' \\bthousand\\b': 'e3', ' \\bmillion\\b': 'e6', ' \\bbillion\\b': 'e9', '\\bthousand\\b': 'e3', '\\bmillion\\b': 'e6', '\\bbillion\\b': 'e9', ' ?%': 'e-2'}
    s_unit_free = s
    for pattern, value in unit_conversion.items():
        s = re.sub(pattern, value, s)
        s_unit_free = re.sub(pattern, '', s_unit_free)
    try:
        return (float(s), [float(s), float(s_unit_free)])
    except ValueError:
        return (s, [s, s_unit_free])

def normalize(x):
    if not isinstance(x, str):
        x = x.decode('utf8', errors='ignore')
    x = ''.join((c for c in unicodedata.normalize('NFKD', x) if unicodedata.category(c) != 'Mn'))
    x = re.sub('[‘’´`]', "'", x)
    x = re.sub('[“”]', '"', x)
    x = re.sub('[‐‑‒–—−]', '-', x)
    while True:
        old_x = x
        x = re.sub('((?<!^)\\[[^\\]]*\\]|\\[\\d+\\]|[•♦†‡*#+])*$', '', x.strip())
        x = re.sub('(?<!^)( \\([^)]*\\))*$', '', x.strip())
        x = re.sub('^"([^"]*)"$', '\\1', x.strip())
        if x == old_x:
            break
    if x and x[-1] == '.':
        x = x[:-1]
    x = re.sub('\\s+', ' ', x, flags=re.U).lower().strip()
    return x

class Value(object):
    __metaclass__ = ABCMeta
    _normalized = None

    @abstractmethod
    def match(self, other):
        """Return True if the value matches the other value.

        Args:
            other (Value)
        Returns:
            a boolean
        """
        pass

    @property
    def normalized(self):
        return self._normalized

class StringValue(Value):

    def __init__(self, content):
        assert isinstance(content, str)
        self._normalized = normalize(content)
        self._hash = hash(self._normalized)

    def __eq__(self, other):
        return isinstance(other, StringValue) and self.normalized == other.normalized

    def __hash__(self):
        return self._hash

    def __str__(self):
        return 'S' + str([self.normalized])

    def __repr__(self):
        return self.__str__()

    def match(self, other):
        assert isinstance(other, Value)
        return self.normalized == other.normalized

class NumberValue(Value):

    def __init__(self, amount, original_string=None):
        assert isinstance(amount, (int, float))
        if abs(amount - round(amount)) < 1e-06:
            self._amount = int(amount)
        else:
            self._amount = float(amount)
        if not original_string:
            self._normalized = str(self._amount)
        else:
            self._normalized = normalize(original_string)
        self._hash = hash(self._amount)

    @property
    def amount(self):
        return self._amount

    def __eq__(self, other):
        return isinstance(other, NumberValue) and self.amount == other.amount

    def __hash__(self):
        return self._hash

    def __str__(self):
        return 'N({})'.format(self.amount) + str([self.normalized])

    def __repr__(self):
        return self.__str__()

    def match(self, other):
        assert isinstance(other, Value)
        if self.normalized == other.normalized:
            return True
        if isinstance(other, NumberValue):
            return abs(self.amount - other.amount) < 1e-06
        return False

    @staticmethod
    def parse(text):
        """Try to parse into a number.

        Return:
            the number (int or float) if successful; otherwise None.
        """
        try:
            return int(text)
        except ValueError:
            try:
                amount = float(text)
                assert not isnan(amount) and (not isinf(amount))
                return amount
            except ValueError:
                return None

class DateValue(Value):

    def __init__(self, year, month, day, original_string=None):
        """Create a new DateValue. Placeholders are marked as -1."""
        assert isinstance(year, int)
        assert isinstance(month, int) and (month == -1 or 1 <= month <= 12)
        assert isinstance(day, int) and (day == -1 or 1 <= day <= 31)
        assert not year == month == day == -1
        self._year = year
        self._month = month
        self._day = day
        if not original_string:
            self._normalized = '{}-{}-{}'.format(year if year != -1 else 'xx', month if month != -1 else 'xx', day if day != '-1' else 'xx')
        else:
            self._normalized = normalize(original_string)
        self._hash = hash((self._year, self._month, self._day))

    @property
    def ymd(self):
        return (self._year, self._month, self._day)

    def __eq__(self, other):
        return isinstance(other, DateValue) and self.ymd == other.ymd

    def __hash__(self):
        return self._hash

    def __str__(self):
        return 'D(%d,%d,%d)' % (self._year, self._month, self._day) + str([self._normalized])
    __repr__ = __str__

    def match(self, other):
        assert isinstance(other, Value)
        if self.normalized == other.normalized:
            return True
        if isinstance(other, DateValue):
            return self.ymd == other.ymd
        return False

    @staticmethod
    def parse(text):
        """Try to parse into a date.

        Return:
            tuple (year, month, date) if successful; otherwise None.
        """
        try:
            ymd = text.lower().split('-')
            assert len(ymd) == 3
            year = -1 if ymd[0] in ('xx', 'xxxx') else int(ymd[0])
            month = -1 if ymd[1] == 'xx' else int(ymd[1])
            day = -1 if ymd[2] == 'xx' else int(ymd[2])
            assert not year == month == day == -1
            assert month == -1 or 1 <= month <= 12
            assert day == -1 or 1 <= day <= 31
            return (year, month, day)
        except:
            return None

def to_value(original_string, corenlp_value=None):
    """Convert the string to Value object.

    Args:
        original_string (basestring): Original string
        corenlp_value (basestring): Optional value returned from CoreNLP
    Returns:
        Value
    """
    if isinstance(original_string, Value):
        return original_string
    if not corenlp_value:
        corenlp_value = original_string
    amount = NumberValue.parse(corenlp_value)
    if amount is not None:
        return NumberValue(amount, original_string)
    ymd = DateValue.parse(corenlp_value)
    if ymd is not None:
        if ymd[1] == ymd[2] == -1:
            return NumberValue(ymd[0], original_string)
        else:
            return DateValue(ymd[0], ymd[1], ymd[2], original_string)
    return StringValue(original_string)

def to_value_list(original_strings, corenlp_values=None):
    """Convert a list of strings to a list of Values

    Args:
        original_strings (list[basestring])
        corenlp_values (list[basestring or None])
    Returns:
        list[Value]
    """
    assert isinstance(original_strings, (list, tuple, set))
    if corenlp_values is not None:
        assert isinstance(corenlp_values, (list, tuple, set))
        assert len(original_strings) == len(corenlp_values)
        return list(set((to_value(x, y) for x, y in zip(original_strings, corenlp_values))))
    else:
        return list(set((to_value(x) for x in original_strings)))

def check_denotation(target_values, predicted_values):
    """Return True if the predicted denotation is correct.

    Args:
        target_values (list[Value])
        predicted_values (list[Value])
    Returns:
        bool
    """
    if len(target_values) != len(predicted_values):
        return False
    for target in target_values:
        if not any((target.match(pred) for pred in predicted_values)):
            return False
    return True

def tsv_unescape(x):
    """Unescape strings in the TSV file.
    Escaped characters include:
        newline (0x10) -> backslash + n
        vertical bar (0x7C) -> backslash + p
        backslash (0x5C) -> backslash + backslash

    Args:
        x (str or unicode)
    Returns:
        a unicode
    """
    return x.replace('\\n', '\n').replace('\\p', '|').replace('\\\\', '\\')

def tsv_unescape_list(x):
    """Unescape a list in the TSV file.
    List items are joined with vertical bars (0x5C)

    Args:
        x (str or unicode)
    Returns:
        a list of unicodes
    """
    return [tsv_unescape(y) for y in x.split('|')]
