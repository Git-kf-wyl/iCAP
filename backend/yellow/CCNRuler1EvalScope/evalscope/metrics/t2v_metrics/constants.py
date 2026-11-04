# Private iCAP Yellow implementation. Do not publish.
import os
from modelscope.utils.file_utils import get_model_cache_root
CACHE_DIR = get_model_cache_root()
os.environ['TORCH_HOME'] = CACHE_DIR
CONTEXT_LEN = 2048
SYSTEM_MSG = "A chat between a curious user and an artificial intelligence assistant. The assistant gives helpful, detailed, and polite answers to the user's questions."
IGNORE_INDEX = -100
IMAGE_TOKEN_INDEX = -200
DEFAULT_IMAGE_TOKEN = '<image>'
