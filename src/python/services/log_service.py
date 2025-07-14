"""
LogService — сервис для логирования и подписки на логи
"""
import datetime
import inspect
import traceback
from typing import Callable, List, Dict, Optional, Any

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
        # Пишем в stdout (можно заменить на запись в файл)
        formatted = cls.format_log(log_entry)
        print(formatted)

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