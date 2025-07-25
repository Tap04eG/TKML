#!/usr/bin/env python3
"""
TMKL - The Minecraft Launcher
Главный файл лаунчера Minecraft
"""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTranslator, QLocale
from PySide6.QtGui import QFont
import logging
import shutil
from datetime import datetime

# Добавляем путь к модулям проекта
sys.path.append(str(Path(__file__).parent))

from ui.main_window import MainWindow
from core.config_manager import ConfigManager
from utils.theme_manager import ThemeManager
from services.log_service import LogService

class TMKLLauncher:
    """Главный класс лаунчера TMKL"""
    
    def __init__(self):
        """Инициализация лаунчера"""
        self.app = None
        self.main_window = None
        self.config_manager = None
        self.theme_manager = None
        
    def setup_application(self):
        """Настройка приложения"""
        # Создаем QApplication
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("TMKL - The Minecraft Launcher")
        self.app.setApplicationVersion("1.0.0")
        self.app.setOrganizationName("TMKL Team")
        
        # Настраиваем шрифт
        font = QFont("Segoe UI", 9)
        self.app.setFont(font)
        
        # Применяем стиль
        self.app.setStyleSheet("""
    QWidget {
        background-color: #2d2d2d;
        color: #e0e0e0;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 12pt;
    }
    QPushButton {
        background-color: #3a3a3a;
        border: 1px solid #4a4a4a;
        border-radius: 5px;
        padding: 8px 16px;
        min-width: 80px;
    }
    QPushButton:hover {
        background-color: #4a4a4a;
    }
    QPushButton:pressed {
        background-color: #2a2a2a;
    }
    QPushButton.primary {
        background-color: #2ecc71;
        color: #ffffff;
        font-weight: bold;
    }
    QPushButton.primary:hover {
        background-color: #27ae60;
    }
    QPushButton.primary:pressed {
        background-color: #219653;
    }
    QLineEdit, QTextEdit, QPlainTextEdit {
        background-color: #3a3a3a;
        border: 1px solid #4a4a4a;
        border-radius: 4px;
        padding: 6px;
        selection-background-color: #2ecc71;
    }
    QCheckBox, QRadioButton {
        spacing: 8px;
    }
    QCheckBox::indicator, QRadioButton::indicator {
        width: 16px;
        height: 16px;
    }
    QCheckBox::indicator:checked {
        background-color: #2ecc71;
        border: 1px solid #27ae60;
    }
    QScrollBar:vertical {
        border: none;
        background: #3a3a3a;
        width: 10px;
    }
    QScrollBar::handle:vertical {
        background: #4a4a4a;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: #5a5a5a;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QTabWidget::pane {
        border: 1px solid #4a4a4a;
    }
    QTabBar::tab {
        background: #3a3a3a;
        color: #e0e0e0;
        padding: 8px 12px;
        border: none;
    }
    QTabBar::tab:selected {
        background: #2ecc71;
        color: #ffffff;
    }
""")
        
    def setup_managers(self):
        """Инициализация менеджеров"""
        # Инициализируем менеджер конфигурации
        self.config_manager = ConfigManager()
        # Настраиваем логирование с путём к Minecraft
        # setup_logger(self.config_manager.get("minecraft_path"))
        # Инициализируем менеджер тем
        self.theme_manager = ThemeManager(self.config_manager)
        
    def setup_translations(self):
        """Настройка переводов (пока только ru)"""
        translator = QTranslator()
        locale = QLocale.system().name()
        
        # Пока используем ru, позже добавим en
        # translator.load(f"translations/tmkl_{locale}")
        # self.app.installTranslator(translator)
        
    def create_main_window(self):
        """Создание главного окна"""
        self.main_window = MainWindow(self.config_manager, self.theme_manager)
        self.main_window.show()
        
    def run(self):
        """Запуск лаунчера"""
        try:
            # Настройка приложения
            self.setup_application()
            
            # Инициализация менеджеров
            self.setup_managers()
            
            # Настройка переводов
            self.setup_translations()
            
            # Создание главного окна
            self.create_main_window()
            
            # Применение темы
            if self.theme_manager:
                self.theme_manager.apply_theme(self.app)
            
            # Запуск главного цикла
            if self.app:
                return self.app.exec()
            return 1
            
        except Exception as e:
            print(f"Ошибка запуска лаунчера: {e}")
            return 1


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    LogService.setup_file_logging(log_dir="logs", log_filename="launcher.log")
    LogService.setup_stdout_logging()

# --- Архивация логов ---
def archive_logs():
    logs_dir = Path("logs")
    old_dir = logs_dir / "old"
    now = datetime.now()
    date_str = now.strftime("%d-%m-%y")
    time_str = now.strftime("%H-%M-%S")
    archive_path = old_dir / date_str / time_str
    archive_path.mkdir(parents=True, exist_ok=True)
    for log_file in logs_dir.glob("*.log"):
        shutil.move(str(log_file), archive_path / log_file.name)
    for jsonl_file in logs_dir.glob("*.jsonl"):
        shutil.move(str(jsonl_file), archive_path / jsonl_file.name)

archive_logs()

setup_logging()
LogService.log('INFO', "Приложение запущено", source="Main")

def main():
    """Точка входа в приложение"""
    launcher = TMKLLauncher()
    sys.exit(launcher.run())

def excepthook(type, value, tb):
    sys.__excepthook__(type, value, tb)
sys.excepthook = excepthook

if __name__ == "__main__":
    main() 