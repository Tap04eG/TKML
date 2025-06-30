"""
Система логирования лаунчера
Настройка и управление логами
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logger():
    """Настройка системы логирования"""
    # Удаляем стандартный обработчик
    logger.remove()
    
    # Создаем директорию для логов
    log_dir = Path.home() / ".tmkl" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Настраиваем логирование в файл
    logger.add(
        log_dir / "tmkl_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        level="DEBUG"
    )
    
    # Настраиваем логирование в консоль
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
        level="INFO"
    )
    
    # Настраиваем логирование ошибок в отдельный файл
    logger.add(
        log_dir / "errors_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="90 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        level="ERROR"
    )
    
    logger.info("Система логирования инициализирована") 