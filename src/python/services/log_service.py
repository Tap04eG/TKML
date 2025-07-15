"""
LogService — сервис для логирования и подписки на логи
"""
import datetime
import inspect
import traceback
from typing import Callable, List, Dict, Optional, Any
import sys
from pathlib import Path
try:
    from loguru import logger
except ImportError:
    logger = None

class LogService:
    _instance = None
    _subscribers: List[Callable[[Dict[str, Any]], None]] = []
    _recent_logs: List[Dict[str, Any]] = []
    _max_recent = 200
    _level = "INFO"
    _levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def log(cls, level: str, message: str, source: Optional[str] = None, stack: Optional[str] = None):
        now = datetime.datetime.now()
        date = now.strftime("%d-%m-%Y")
        time = now.strftime("%H:%M:%S")
        if source is None:
            # Определяем источник вызова (файл:строка)
            frame = inspect.currentframe()
            outer = inspect.getouterframes(frame, 3)
            if len(outer) > 2:
                src = outer[2]
                source = f"{src.filename.split('/')[-1]}:{src.lineno}"
            else:
                source = ""
        if stack is None and level in ("ERROR", "CRITICAL"):
            stack = traceback.format_exc()
            if stack == "NoneType: None\n":
                stack = None
        log_entry = {
            "date": date,
            "time": time,
            "level": level,
            "source": source or "",
            "message": message,
            "stack": stack,
        }
        # Храним последние N логов
        cls._recent_logs.append(log_entry)
        if len(cls._recent_logs) > cls._max_recent:
            cls._recent_logs.pop(0)
        # Вызываем подписчиков
        for cb in cls._subscribers:
            try:
                cb(log_entry)
            except Exception:
                pass
        # (stdout вывод убран, теперь только через подписчика при необходимости)

    @classmethod
    def subscribe(cls, callback: Callable[[Dict[str, Any]], None]):
        cls._subscribers.append(callback)

    @classmethod
    def get_recent(cls, n: int = 100) -> List[Dict[str, Any]]:
        return cls._recent_logs[-n:]

    @classmethod
    def set_level(cls, level: str):
        if level in cls._levels:
            cls._level = level

    @classmethod
    def format_log(cls, log_entry: Dict[str, Any]) -> str:
        stack_part = f"\n{log_entry['stack']}" if log_entry.get("stack") else ""
        return f"[{log_entry['date']} {log_entry['time']}] [{log_entry['level']}] [{log_entry['source']}] {log_entry['message']}{stack_part}"

    @classmethod
    def setup_file_logging(cls, log_dir=None, log_filename="tmkl.log"):
        """Добавляет подписчика, который пишет логи в файл через loguru."""
        if logger is None:
            return
        if log_dir is None:
            log_dir = Path.home() / ".tmkl" / "logs"
        else:
            log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / log_filename
        logger.remove()
        logger.add(
            log_file,
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            level="DEBUG"
        )
        # JSONL для UI
        jsonl_file = log_dir / f"launcher_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        logger.add(
            jsonl_file,
            level="DEBUG",
            serialize=True,
            encoding="utf-8"
        )
        # Ошибки отдельно
        logger.add(
            log_dir.joinpath("errors_{time:YYYY-MM-DD}.log"),
            rotation="1 day",
            retention="90 days",
            compression="zip",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            level="ERROR"
        )
        def file_log_subscriber(log_entry):
            if logger is None:
                return
            lvl = log_entry["level"].upper()
            msg = f"[{log_entry['source']}] {log_entry['message']}"
            if log_entry.get("stack"):
                msg += f"\n{log_entry['stack']}"
            if lvl == "DEBUG":
                logger.debug(msg)
            elif lvl == "INFO":
                logger.info(msg)
            elif lvl == "WARNING":
                logger.warning(msg)
            elif lvl == "ERROR":
                logger.error(msg)
            elif lvl == "CRITICAL":
                logger.critical(msg)
            else:
                logger.info(msg)
        cls.subscribe(file_log_subscriber)

    @classmethod
    def setup_stdout_logging(cls, min_level="INFO"):
        """Добавляет подписчика, который выводит логи в stdout (print)."""
        level_order = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        min_level_num = level_order.get(min_level.upper(), 20)
        def stdout_log_subscriber(log_entry):
            lvl = log_entry["level"].upper()
            if level_order.get(lvl, 0) < min_level_num:
                return
            formatted = cls.format_log(log_entry)
            print(formatted)
        cls.subscribe(stdout_log_subscriber) 