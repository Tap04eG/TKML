"""
Система логирования лаунчера
Настройка и управление логами
"""

import sys
from pathlib import Path
from loguru import logger
import datetime


def setup_logger(minecraft_path=None):
    """Настройка системы логирования"""
    try:
        logger.remove()
        if minecraft_path is None:
            log_dir = Path.home() / ".tmkl" / "logs"
        else:
            log_dir = Path(minecraft_path) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "tmkl.log"
        logger.add(
            log_file,
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            level="DEBUG"
        )
        logger.info("Система логирования инициализирована")
    except Exception as e:
        print(f"Ошибка инициализации логгера: {e}")

    # Директория для JSONL логов (для UI)
    jsonl_dir = Path(__file__).parent.parent.parent / ".." / "logs"
    jsonl_dir = jsonl_dir.resolve()
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    jsonl_file = jsonl_dir / f"launcher_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    # Логирование в JSONL для UI
    logger.add(
        jsonl_file,
        level="DEBUG",
        serialize=True,
        encoding="utf-8"
    )
    # Логирование ошибок в отдельный файл
    logger.add(
        log_dir.joinpath("errors_{time:YYYY-MM-DD}.log"),
        rotation="1 day",
        retention="90 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        level="ERROR"
    ) 