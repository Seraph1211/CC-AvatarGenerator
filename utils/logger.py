"""日志工具 - 按天截断。

使用示例：
  from utils.logger import get_logger
  logger = get_logger()                    # 默认隐藏 app 名称
  logger = get_logger(show_app_name=True)  # 显示 %(name)s 字段
  logger = get_logger(name="custom")       # 自定义 logger 名字

格式：
  - 默认：%(asctime)s | %(levelname)s | %(message)s
  - show_app_name=True：%(asctime)s | %(levelname)s | %(name)s | %(message)s
"""
import logging
import os
from datetime import datetime

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 全局缓存避免重复添加 handler
_LOGGER_CACHE: dict[str, logging.Logger] = {}


def get_logger(name: str = "app", show_app_name: bool = False) -> logging.Logger:
    """获取按天截断的 logger。

    Args:
        name: logger 名称（用于 %(name)s 字段）
        show_app_name: 是否在格式中显示 %(name)s 字段——日常使用通常为 False，
                       调试多模块协作时可设为 True 区分日志来源
    """
    cache_key = f"{name}::{show_app_name}"
    if cache_key in _LOGGER_CACHE:
        return _LOGGER_CACHE[cache_key]

    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # 按天截断的文件处理器
        log_file = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 格式：默认不显示 name（更干净），按需显示
        if show_app_name:
            fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        else:
            fmt = "%(asctime)s | %(levelname)s | %(message)s"
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    _LOGGER_CACHE[cache_key] = logger
    return logger


# 默认 logger——日常使用不显示 app 名称
logger = get_logger()
