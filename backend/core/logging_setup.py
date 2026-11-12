"""统一日志配置（§13）：控制台 + 轮转文件。

- 控制台输出（默认 INFO 及以上）
- 轮转文件 ``logs/app.log``（10MB × 5 备份，自动轮转）
- ERROR 日志可携带 error_id（由调用方在消息中拼接，如 ``id=%s``）
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"

_MAX_BYTES = 10 * 1024 * 1024  # 10MB
_BACKUP_COUNT = 5


def setup_logging(level: str | None = None) -> logging.Logger:
    """配置应用日志：控制台 + 轮转文件。返回 ``jiutian`` 根 logger。

    重复调用不会重复添加 handler（幂等）。
    """
    if level is None:
        level = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    logger = logging.getLogger("jiutian")
    logger.setLevel(getattr(logging, level, logging.INFO))
    logger.propagate = False

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 轮转文件（10MB × 5）
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "jiutian") -> logging.Logger:
    """获取子 logger（自动确保根配置已就绪）。

    用法：``logger = get_logger("agent")`` → ``jiutian.agent``。
    """
    setup_logging()
    if name == "jiutian" or name.startswith("jiutian."):
        return logging.getLogger(name)
    return logging.getLogger(f"jiutian.{name}")
