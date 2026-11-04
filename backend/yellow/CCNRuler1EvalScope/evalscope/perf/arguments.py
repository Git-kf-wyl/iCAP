# Private iCAP Yellow implementation. Do not publish.
import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from evalscope.constants import DEFAULT_WORK_DIR

@dataclass
class Arguments:
    model: str
    model_id: Optional[str] = None
    attn_implementation: Optional[str] = None
    api: str = 'openai'
    tokenizer_path: Optional[str] = None
    port: int = 8877
    url: str = 'http://127.0.0.1:8877/v1/chat/completions'
    headers: Dict[str, Any] = field(default_factory=dict)
    connect_timeout: int = 600
    read_timeout: int = 600
    api_key: Optional[str] = None
    no_test_connection: bool = False
    number: int = 1000
    parallel: int = 1
    rate: int = -1
    log_every_n_query: int = 10
    debug: bool = False
    wandb_api_key: Optional[str] = None
    swanlab_api_key: Optional[str] = None
    name: Optional[str] = None
    outputs_dir: str = DEFAULT_WORK_DIR
    max_prompt_length: int = 131072
    min_prompt_length: int = 0
    prefix_length: int = 0
    prompt: Optional[str] = None
    query_template: Optional[str] = None
    apply_chat_template: Optional[bool] = None
    dataset: str = 'openqa'
    dataset_path: Optional[str] = None
    frequency_penalty: Optional[float] = None
    logprobs: Optional[bool] = None
    max_tokens: Optional[int] = 2048
    min_tokens: Optional[int] = None
    n_choices: Optional[int] = None
    seed: Optional[int] = 0
    stop: Optional[List[str]] = field(default_factory=list)
    stop_token_ids: Optional[List[str]] = field(default_factory=list)
    stream: Optional[bool] = True
    temperature: float = 0.0
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    extra_args: Optional[Dict[str, Any]] = None

    @staticmethod
    def from_args(args):
        args_dict = {k: v for k, v in vars(args).items() if v is not None}
        if 'func' in args_dict:
            del args_dict['func']
        return Arguments(**args_dict)

    def __post_init__(self):
        self.headers = self.headers or {}
        if self.api_key:
            self.headers['Authorization'] = f'Bearer {self.api_key}'
        self.model_id = os.path.basename(self.model)
        if self.api.startswith('local'):
            if self.dataset.startswith('speed_benchmark'):
                self.url = f'http://127.0.0.1:{self.port}/v1/completions'
            else:
                self.url = f'http://127.0.0.1:{self.port}/v1/chat/completions'
        if self.apply_chat_template is None:
            self.apply_chat_template = self.url.strip('/').endswith('chat/completions')

    def __str__(self):
        return json.dumps(self.to_dict(), indent=4, default=str, ensure_ascii=False)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

class ParseKVAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        if not values:
            setattr(namespace, self.dest, {})
        else:
            try:
                kv_dict = {}
                for kv in values:
                    parts = kv.split('=', 1)
                    if len(parts) != 2:
                        raise ValueError(f'Invalid key-value pair: {kv}')
                    key, value = parts
                    kv_dict[key.strip()] = value.strip()
                setattr(namespace, self.dest, kv_dict)
            except ValueError as e:
                parser.error(f'Error parsing key-value pairs: {e}')

def add_argument(parser: argparse.ArgumentParser):
    parser.add_argument('--model', type=str, required=True, help='The test model name.')
    parser.add_argument('--attn-implementation', required=False, default=None, help='Attention implementaion')
    parser.add_argument('--api', type=str, default='openai', help='Specify the service API')
    parser.add_argument('--tokenizer-path', type=str, required=False, default=None, help='Specify the tokenizer weight path')
    parser.add_argument('--url', type=str, default='http://127.0.0.1:8877/v1/chat/completions')
    parser.add_argument('--port', type=int, default=8877, help='The port for local inference')
    parser.add_argument('--headers', nargs='+', dest='headers', action=ParseKVAction, help='Extra HTTP headers')
    parser.add_argument('--api-key', type=str, required=False, default=None, help='The API key for authentication')
    parser.add_argument('--connect-timeout', type=int, default=600, help='The network connection timeout')
    parser.add_argument('--read-timeout', type=int, default=600, help='The network read timeout')
    parser.add_argument('--no-test-connection', action='store_false', default=False, help='Do not test the connection before starting the benchmark')
    parser.add_argument('-n', '--number', type=int, default=1000, help='How many requests to be made')
    parser.add_argument('--parallel', type=int, default=1, help='Set number of concurrency requests, default 1')
    parser.add_argument('--rate', type=int, default=-1, help='Number of requests per second. default None')
    parser.add_argument('--log-every-n-query', type=int, default=10, help='Logging every n query')
    parser.add_argument('--debug', action='store_true', default=False, help='Debug request send')
    parser.add_argument('--wandb-api-key', type=str, default=None, help='The wandb API key')
    parser.add_argument('--swanlab-api-key', type=str, default=None, help='The swanlab API key')
    parser.add_argument('--name', type=str, help='The wandb/swanlab db result name and result db name')
    parser.add_argument('--max-prompt-length', type=int, default=sys.maxsize, help='Maximum input prompt length')
    parser.add_argument('--min-prompt-length', type=int, default=0, help='Minimum input prompt length')
    parser.add_argument('--prefix-length', type=int, default=0, help='The prefix length')
    parser.add_argument('--prompt', type=str, required=False, default=None, help='Specified the request prompt')
    parser.add_argument('--query-template', type=str, default=None, help='Specify the query template')
    parser.add_argument('--apply-chat-template', type=argparse.BooleanOptionalAction, default=None, help='Apply chat template to the prompt')
    parser.add_argument('--outputs-dir', help='Outputs dir.', default='outputs')
    parser.add_argument('--dataset', type=str, default='openqa', help='Specify the dataset')
    parser.add_argument('--dataset-path', type=str, required=False, help='Path to the dataset file')
    parser.add_argument('--frequency-penalty', type=float, help='The frequency_penalty value', default=None)
    parser.add_argument('--logprobs', action='store_true', help='The logprobs', default=None)
    parser.add_argument('--max-tokens', type=int, help='The maximum number of tokens that can be generated', default=2048)
    parser.add_argument('--min-tokens', type=int, help='The minimum number of tokens that can be generated', default=None)
    parser.add_argument('--n-choices', type=int, help='How many completion choices to generate', default=None)
    parser.add_argument('--seed', type=int, help='The random seed', default=0)
    parser.add_argument('--stop', nargs='*', help='The stop tokens', default=None)
    parser.add_argument('--stop-token-ids', nargs='*', help='Set the stop token IDs', default=None)
    parser.add_argument('--stream', action=argparse.BooleanOptionalAction, help='Stream output with SSE', default=True)
    parser.add_argument('--temperature', type=float, help='The sample temperature', default=0.0)
    parser.add_argument('--top-p', type=float, help='Sampling top p', default=None)
    parser.add_argument('--top-k', type=int, help='Sampling top k', default=None)
    parser.add_argument('--extra-args', type=json.loads, default='{}', help='Extra arguments, should in JSON format')

def parse_args():
    parser = argparse.ArgumentParser(description='Benchmark LLM service performance.')
    add_argument(parser)
    return parser.parse_args()
