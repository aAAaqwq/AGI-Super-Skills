"""
core/logger.py — 统一日志模块
- 控制台 + 滚动文件双输出
- 按模块获取独立 logger
- 实盘/模拟均通过此模块记录审计日志
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
_DEFAULT_FILE = os.path.join(_LOG_DIR, "bb-scalper.log")

_configured = False
_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str, level: int = logging.INFO,
               log_file: Optional[str] = None) -> logging.Logger:
    """
    获取（或创建）一个命名 logger。

    Args:
        name: 模块名，如 "trade_exec"、"binance_client"
        level: 日志级别
        log_file: 覆盖默认日志文件路径

    Returns:
        logging.Logger 实例
    """
    global _configured
    if not _configured:
        os.makedirs(_LOG_DIR, exist_ok=True)
        _configured = True

    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(f"bbscalper.{name}")
    logger.setLevel(level)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(level)
    logger.addHandler(ch)

    # 滚动文件输出（默认 5MB × 5 个备份）
    try:
        fh = RotatingFileHandler(log_file or _DEFAULT_FILE,
                                 maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(level)
        logger.addHandler(fh)
    except OSError as e:
        logger.warning("无法创建日志文件 %s: %s", log_file or _DEFAULT_FILE, e)

    _loggers[name] = logger
    return logger
