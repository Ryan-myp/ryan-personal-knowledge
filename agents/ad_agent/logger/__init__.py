"""
logging/__init__.py - 结构化日志系统

使用 structlog 风格的 JSON 结构化日志，便于 log aggregation 和查询。
"""

import logging
import json
import time
import sys
from typing import Any, Optional
from contextlib import contextmanager


class JSONFormatter(logging.Formatter):
    """
    JSON 结构化日志格式化器。
    
    每条日志输出为单行 JSON，便于 log aggregation（ELK/Loki 等）。
    """
    
    def __init__(self, include_time=True, include_level=True, include_logger=True):
        super().__init__()
        self.include_time = include_time
        self.include_level = include_level
        self.include_logger = include_logger
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        
        # 附加自定义字段
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        
        # 异常信息
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class LogContext:
    """
    日志上下文管理器。
    
    用法：
        with LogContext(tool="meta_create_campaign", campaign_id="123"):
            result = handler.execute(ctx, input_data)
    """
    
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._logger = logging.getLogger(__name__)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
    
    def info(self, msg: str, **extra):
        self._log("info", msg, **extra)
    
    def warning(self, msg: str, **extra):
        self._log("warning", msg, **extra)
    
    def error(self, msg: str, **extra):
        self._log("error", msg, **extra)
    
    def debug(self, msg: str, **extra):
        self._log("debug", msg, **extra)
    
    def _log(self, level: str, msg: str, **extra):
        merged = {**self._kwargs, **extra}
        self._logger.log(
            getattr(logging, level.upper()),
            msg,
            extra={"extra_data": merged} if merged else None,
        )


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    output: str = None,
) -> logging.Logger:
    """
    初始化日志系统。
    
    Args:
        level: 日志级别（DEBUG/INFO/WARNING/ERROR）
        json_format: 是否使用 JSON 格式
        output: 日志输出文件路径（None 表示 stdout）
    
    Returns:
        根 logger
    """
    fmt = JSONFormatter() if json_format else None
    handlers = []
    
    if output:
        fh = logging.FileHandler(output)
        fh.setFormatter(fmt)
        handlers.append(fh)
    
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    handlers.append(sh)
    
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))
    
    for h in handlers:
        root.addHandler(h)
    
    # 抑制第三方库噪音
    for noisy in ["urllib3", "requests", "google.auth"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
    
    logger = logging.getLogger("ad_agent")
    logger.info("Logging initialized", extra={"level": level, "json": json_format})
    return logger


@contextmanager
def log_time(logger: logging.Logger, label: str, **extra):
    """
    计时上下文管理器，自动记录耗时。
    
    用法：
        with log_time(logger, "api_call", tool="meta_create_campaign"):
            result = client.create_campaign(...)
    """
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        logger.debug(
            f"{label} completed",
            extra={"extra_data": {**extra, "elapsed_ms": round(elapsed * 1000, 2)}},
        )
