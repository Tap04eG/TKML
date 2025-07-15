#!/usr/bin/env python3
"""
Тестовый скрипт для проверки создания сборки
"""

import sys
import os
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src" / "python"))

from src.python.core.config_manager import ConfigManager
from src.python.core.minecraft_manager import MinecraftManager
from src.python.core.build_manager import BuildManager, BuildStatus
from src.python.services.log_service import LogService

def setup_logging():
    """Настройка логирования"""
    LogService.setup_file_logging()

def test_build_creation():
    """Тест создания сборки"""
    try:
        LogService.log('INFO', "=== НАЧАЛО ТЕСТА СОЗДАНИЯ СБОРКИ ===")
        
        # Инициализация менеджеров
        LogService.log('INFO', "Инициализация ConfigManager...")
        config_manager = ConfigManager()
        
        LogService.log('INFO', "Инициализация MinecraftManager...")
        minecraft_manager = MinecraftManager(config_manager)
        
        LogService.log('INFO', "Инициализация BuildManager...")
        build_manager = BuildManager(config_manager, minecraft_manager)
        
        # Тестовая конфигурация сборки
        test_config = {
            'name': 'Test Build',
            'minecraft_version': '1.20.1',
            'loader': 'Vanilla',
            'loader_version': None
        }
        
        LogService.log('INFO', f"Тестовая конфигурация: {test_config}")
        
        # Функция обратного вызова для прогресса
        def progress_callback(value, text):
            LogService.log('INFO', f"Прогресс: {value}% - {text}")
        
        # Создание сборки
        LogService.log('INFO', "Начало создания сборки...")
        result = build_manager.create_build(test_config, progress_callback)
        
        if result is True:
            LogService.log('SUCCESS', "Сборка успешно создана!")
        else:
            LogService.log('ERROR', f"Ошибка создания сборки: {result}")
            
        # Проверяем состояние сборки
        state = build_manager.get_build_state(test_config['name'])
        LogService.log('INFO', f"Состояние сборки: {state}")
        
        # Получаем список сборок
        builds = build_manager.get_builds()
        LogService.log('INFO', f"Всего сборок: {len(builds)}")
        for build in builds:
            LogService.log('INFO', f"  - {build.get('name')}: {build.get('status', 'unknown')}")
            
        LogService.log('INFO', "=== ТЕСТ ЗАВЕРШЕН ===")
        
    except Exception as e:
        LogService.log('CRITICAL', "Критическая ошибка в тесте")
        return False
        
    return True

def test_fabric_build():
    """Тест создания сборки с Fabric"""
    try:
        LogService.log('INFO', "=== НАЧАЛО ТЕСТА СОЗДАНИЯ FABRIC СБОРКИ ===")
        
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
        
        LogService.log('INFO', f"Тестовая конфигурация Fabric: {test_config}")
        
        def progress_callback(value, text):
            LogService.log('INFO', f"Прогресс Fabric: {value}% - {text}")
        
        # Создание сборки
        LogService.log('INFO', "Начало создания Fabric сборки...")
        result = build_manager.create_build(test_config, progress_callback)
        
        if result is True:
            LogService.log('SUCCESS', "Fabric сборка успешно создана!")
        else:
            LogService.log('ERROR', f"Ошибка создания Fabric сборки: {result}")
            
        LogService.log('INFO', "=== ТЕСТ FABRIC ЗАВЕРШЕН ===")
        
    except Exception as e:
        LogService.log('CRITICAL', "Критическая ошибка в тесте Fabric")
        return False
        
    return True

if __name__ == "__main__":
    # Создаем папку для логов
    Path("logs").mkdir(exist_ok=True)
    
    # Настраиваем логирование
    setup_logging()
    
    LogService.log('INFO', "Запуск тестов создания сборок")
    
    # Тест 1: Vanilla сборка
    success1 = test_build_creation()
    
    # Тест 2: Fabric сборка
    success2 = test_fabric_build()
    
    if success1 and success2:
        LogService.log('SUCCESS', "Все тесты прошли успешно!")
    else:
        LogService.log('ERROR', "Некоторые тесты завершились с ошибками")
        
    LogService.log('INFO', "Тесты завершены. Проверьте логи в logs/build_test.log") 