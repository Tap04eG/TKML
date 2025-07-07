#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправлений крашей
"""

import sys
import os
import time
import threading
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src" / "python"))

from core.config_manager import ConfigManager
from core.build_manager import BuildManager, BuildStatus
from core.minecraft_manager import MinecraftManager
from ui.tabs.installations_tab import InstallationsTab
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from loguru import logger

def test_build_manager_safety():
    """Тестирование безопасности BuildManager"""
    print("=== Тестирование BuildManager ===")
    
    try:
        # Инициализация
        config_manager = ConfigManager()
        minecraft_manager = MinecraftManager(config_manager)
        build_manager = BuildManager(config_manager, minecraft_manager)
        
        # Тест 1: Получение сборок с пустой папкой
        builds = build_manager.get_builds()
        print(f"✓ Получено сборок: {len(builds)}")
        
        # Тест 2: Установка состояний сборок
        build_manager.set_build_state("test_build", BuildStatus.DOWNLOADING, 50, "Тестирование...")
        state = build_manager.get_build_state("test_build")
        print(f"✓ Состояние сборки: {state}")
        
        # Тест 3: Очистка состояния
        build_manager.clear_build_state("test_build")
        state = build_manager.get_build_state("test_build")
        print(f"✓ Состояние после очистки: {state}")
        
        print("✓ BuildManager тесты пройдены")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в BuildManager: {e}")
        return False

def test_ui_safety():
    """Тестирование безопасности UI"""
    print("\n=== Тестирование UI ===")
    
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Инициализация
        config_manager = ConfigManager()
        minecraft_manager = MinecraftManager(config_manager)
        build_manager = BuildManager(config_manager, minecraft_manager)
        
        # Создание вкладки
        tab = InstallationsTab(build_manager, minecraft_manager)
        print("✓ Вкладка создана")
        
        # Тест 1: Обновление списка сборок
        tab.update_my_builds()
        print("✓ Обновление списка сборок выполнено")
        
        # Тест 2: Автообновление
        tab.auto_update_builds()
        print("✓ Автообновление выполнено")
        
        # Тест 3: Обработка ошибок
        tab.handle_build_error("test_build", "Тестовая ошибка")
        print("✓ Обработка ошибок работает")
        
        # Очистка
        tab.closeEvent(None)
        print("✓ Закрытие вкладки выполнено")
        
        print("✓ UI тесты пройдены")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в UI: {e}")
        logger.exception("UI тест ошибка")
        return False

def test_corrupted_data():
    """Тестирование обработки поврежденных данных"""
    print("\n=== Тестирование поврежденных данных ===")
    
    try:
        # Инициализация
        config_manager = ConfigManager()
        minecraft_manager = MinecraftManager(config_manager)
        build_manager = BuildManager(config_manager, minecraft_manager)
        
        # Тест 1: Некорректные данные сборки
        from ui.tabs.installations_tab import InstalledVersionWidget
        
        # Создаем виджет с некорректными данными
        bad_data = None
        widget = InstalledVersionWidget(bad_data)
        print("✓ Виджет с None данными создан")
        
        bad_data = "not_a_dict"
        widget = InstalledVersionWidget(bad_data)
        print("✓ Виджет с некорректными данными создан")
        
        bad_data = {"name": "", "status": "invalid_status"}
        widget = InstalledVersionWidget(bad_data)
        print("✓ Виджет с пустым именем создан")
        
        # Тест 2: Обновление статуса с некорректными данными
        widget.update_status(None, "not_a_number", None)
        print("✓ Обновление с некорректными данными выполнено")
        
        print("✓ Тесты поврежденных данных пройдены")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в тестах поврежденных данных: {e}")
        logger.exception("Тест поврежденных данных ошибка")
        return False

def main():
    """Основная функция тестирования"""
    print("Начало тестирования исправлений крашей...")
    
    # Настройка логирования
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    tests = [
        test_build_manager_safety,
        test_ui_safety,
        test_corrupted_data
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Критическая ошибка в тесте {test.__name__}: {e}")
    
    print(f"\n=== Результаты ===")
    print(f"Пройдено тестов: {passed}/{total}")
    
    if passed == total:
        print("✓ Все тесты пройдены успешно!")
        return 0
    else:
        print("✗ Некоторые тесты не пройдены")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 