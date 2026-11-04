# Private iCAP Yellow implementation. Do not publish.
import importlib.util as iutil
import logging
import os
from typing import Optional

class TruncatingFileHandler(logging.FileHandler):
    """FileHandler that truncates log messages longer than MAX_LOG_LEN characters."""
    MAX_LOG_LEN = 300

    def emit(self, record):
        msg = str(record.msg) if not isinstance(record.msg, str) else record.msg
        if len(msg) > self.MAX_LOG_LEN and '"object":"chat.completion","created":' in msg:
            record.msg = msg[:self.MAX_LOG_LEN] + '... [truncated]'
        super().emit(record)
init_loggers = {}
detailed_format = '%(asctime)s - %(name)s - %(filename)s - %(funcName)s - %(lineno)d - %(levelname)s - %(message)s'
simple_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
detailed_formatter = logging.Formatter(detailed_format)
simple_formatter = logging.Formatter(simple_format)
DEFAULT_LEVEL = logging.DEBUG if os.getenv('LOG_LEVEL', 'INFO') == 'DEBUG' else logging.INFO
logging.basicConfig(format=simple_format, level=DEFAULT_LEVEL, force=True)
logging.getLogger('datasets').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('modelscope').setLevel(logging.ERROR)

def get_logger(log_file: Optional[str]=None, log_level: int=DEFAULT_LEVEL, file_mode: str='w', force=False):
    """Get logging logger

    Args:
        log_file: Log filename, if specified, file handler will be added to
            logger
        log_level: Logging level.
        file_mode: Specifies the mode to open the file, if filename is
            specified (if filemode is unspecified, it defaults to 'w').
    """
    logger_name = __name__.split('.')[0]
    logger = logging.getLogger(logger_name)
    logger.propagate = False
    if logger_name in init_loggers:
        if force:
            logger.setLevel(log_level)
            for handler in logger.handlers:
                handler.setLevel(log_level)
                handler.setFormatter(detailed_formatter if log_level == logging.DEBUG else simple_formatter)
            recreate_file_handler(logger, log_file, file_mode, log_level)
        return logger
    torch_dist = False
    is_worker0 = True
    if iutil.find_spec('torch') is not None:
        from modelscope.utils.torch_utils import is_dist, is_master
        torch_dist = is_dist()
        is_worker0 = is_master()
    if torch_dist:
        for handler in logger.root.handlers:
            if type(handler) is logging.StreamHandler:
                handler.setLevel(logging.ERROR)
    stream_handler = logging.StreamHandler()
    handlers = [stream_handler]
    if is_worker0 and log_file is not None:
        file_handler = TruncatingFileHandler(log_file, file_mode)
        handlers.append(file_handler)
    for handler in handlers:
        handler.setFormatter(detailed_formatter if log_level == logging.DEBUG else simple_formatter)
        handler.setLevel(log_level)
        logger.addHandler(handler)
    if is_worker0:
        logger.setLevel(log_level)
    else:
        logger.setLevel(logging.ERROR)
    init_loggers[logger_name] = True
    return logger

def configure_logging(debug: bool, log_file: Optional[str]=None):
    """Configure logging level based on the debug flag."""
    if log_file:
        get_logger(log_file=log_file, force=True)
    if debug:
        get_logger(log_level=logging.DEBUG, force=True)

def recreate_file_handler(logger, log_file, file_mode, log_level):
    """重新创建文件处理器，旧的处理器会被关闭并移除，确保文件从头写入。"""
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)
    if iutil.find_spec('torch') is not None:
        from modelscope.utils.torch_utils import is_master
        is_worker0 = is_master()
    else:
        is_worker0 = True
    if is_worker0 and log_file is not None:
        file_handler = TruncatingFileHandler(log_file, file_mode)
        file_handler.setFormatter(detailed_formatter if log_level == logging.DEBUG else simple_formatter)
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
