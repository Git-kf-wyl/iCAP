# Private iCAP Yellow business implementation. Do not publish.
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

class Logger:
    """
    日志工具类，封装了logging模块的常用功能

    功能特点：
    1. 支持控制台和文件两种输出方式
    2. 支持按天分割日志文件
    3. 支持自定义日志格式
    4. 支持不同日志级别
    """

    def __init__(self, name: str='root', level: str='INFO', log_dir: Optional[str]=None, file_log: bool=True, console_log: bool=False, fmt: str='%(asctime)s - %(name)s - %(levelname)s - %(message)s', when: str='D', backup_count: int=7):
        """
        初始化日志工具

        :param name: 日志名称，默认为'root'
        :param level: 日志级别，默认为'INFO'
        :param log_dir: 日志目录，如果为None则不记录到文件
        :param file_log: 是否记录到文件
        :param console_log: 是否输出到控制台
        :param fmt: 日志格式
        :param when: 日志分割时间单位，'D'表示按天
        :param backup_count: 保留的日志文件数量
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level.upper())
        if not self.logger.handlers:
            formatter = logging.Formatter(fmt)
            if file_log and log_dir:
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                log_file = os.path.join(log_dir, f'{name}.log')
                file_handler = TimedRotatingFileHandler(filename=log_file, when=when, backupCount=backup_count, encoding='utf-8')
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            if console_log:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                self.logger.addHandler(console_handler)

    def debug(self, msg: str, *args, **kwargs):
        """记录debug级别日志"""
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """记录info级别日志"""
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """记录warning级别日志"""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """记录error级别日志"""
        self.logger.error(msg, *args, **kwargs)

    def exception(self, msg: str, *args, exc_info=True, **kwargs):
        """记录异常日志"""
        self.logger.exception(msg, *args, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """记录critical级别日志"""
        self.logger.critical(msg, *args, **kwargs)
