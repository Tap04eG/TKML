#!/usr/bin/env python3
"""
Тестовый скрипт для проверки создания сборки
"""

import sys
import os
import logging
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src" / "python"))

from loguru import logger
from src.python.core.config_manager import ConfigManager
from src.python.core.minecraft_manager import MinecraftManager
from src.python.core.build_manager import BuildManager, BuildStatus

def setup_logging():
    """Настройка логирования"""
    # Удаляем стандартный обработчик
    logger.remove()
    
    # Добавляем обработчик для файла
    logger.add(
        "logs/build_test.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        rotation="10 MB",
        retention="7 days"
    )
    
    # Добавляем обработчик для консоли
    logger.add(
        sys.stdout,
        level="INFO",
        format="{time:HH:mm:ss} | {level} | {message}"
    )

def test_build_creation():
    """Тест создания сборки"""
    try:
        logger.info("=== НАЧАЛО ТЕСТА СОЗДАНИЯ СБОРКИ ===")
        
        # Инициализация менеджеров
        logger.info("Инициализация ConfigManager...")
        config_manager = ConfigManager()
        
        logger.info("Инициализация MinecraftManager...")
        minecraft_manager = MinecraftManager(config_manager)
        
        logger.info("Инициализация BuildManager...")
        build_manager = BuildManager(config_manager, minecraft_manager)
        
        # Тестовая конфигурация сборки
        test_config = {
            'name': 'Test Build',
            'minecraft_version': '1.20.1',
            'loader': 'Vanilla',
            'loader_version': None
        }
        
        logger.info(f"Тестовая конфигурация: {test_config}")
        
        # Функция обратного вызова для прогресса
        def progress_callback(value, text):
            logger.info(f"Прогресс: {value}% - {text}")
        
        # Создание сборки
        logger.info("Начало создания сборки...")
        result = build_manager.create_build(test_config, progress_callback)
        
        if result is True:
            logger.success("Сборка успешно создана!")
        else:
            logger.error(f"Ошибка создания сборки: {result}")
            
        # Проверяем состояние сборки
        state = build_manager.get_build_state(test_config['name'])
        logger.info(f"Состояние сборки: {state}")
        
        # Получаем список сборок
        builds = build_manager.get_builds()
        logger.info(f"Всего сборок: {len(builds)}")
        for build in builds:
            logger.info(f"  - {build.get('name')}: {build.get('status', 'unknown')}")
            
        logger.info("=== ТЕСТ ЗАВЕРШЕН ===")
        
    except Exception as e:
        logger.exception("Критическая ошибка в тесте")
        return False
        
    return True

def test_fabric_build():
    """Тест создания сборки с Fabric"""
    try:
        logger.info("=== НАЧАЛО ТЕСТА СОЗДАНИЯ FABRIC СБОРКИ ===")
        
        # Инициализация менеджеров
        config_manager = ConfigManager()
        minecraft_manager = MinecraftManager(config_manager)
        build_manager = BuildManager(config_manager, minecraft_manager)
        
        # Тестовая конфигурация сборки с Fabric
        test_config = {
            'name': 'Test Fabric Build',
            'minecraft_version': '1.20.1',
            'loader': 'Fabric',
            'loader_version': '0.14.21'
        }
        
        logger.info(f"Тестовая конфигурация Fabric: {test_config}")
        
        def progress_callback(value, text):
            logger.info(f"Прогресс Fabric: {value}% - {text}")
        
        # Создание сборки
        logger.info("Начало создания Fabric сборки...")
        result = build_manager.create_build(test_config, progress_callback)
        
        if result is True:
            logger.success("Fabric сборка успешно создана!")
        else:
            logger.error(f"Ошибка создания Fabric сборки: {result}")
            
        logger.info("=== ТЕСТ FABRIC ЗАВЕРШЕН ===")
        
    except Exception as e:
        logger.exception("Критическая ошибка в тесте Fabric")
        return False
        
    return True

if __name__ == "__main__":
    # Создаем папку для логов
    Path("logs").mkdir(exist_ok=True)
    
    # Настраиваем логирование
    setup_logging()
    
    logger.info("Запуск тестов создания сборок")
    
    # Тест 1: Vanilla сборка
    success1 = test_build_creation()
    
    # Тест 2: Fabric сборка
    success2 = test_fabric_build()
    
    if success1 and success2:
        logger.success("Все тесты прошли успешно!")
    else:
        logger.error("Некоторые тесты завершились с ошибками")
        
    logger.info("Тесты завершены. Проверьте логи в logs/build_test.log") 