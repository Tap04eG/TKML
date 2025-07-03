from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QTabWidget, QTextEdit, QHBoxLayout, QApplication, QLineEdit, QComboBox
from PySide6.QtCore import Qt, QTimer
from pathlib import Path
import shutil
import os
import subprocess
import json
import glob
from PySide6.QtGui import QTextCursor, QGuiApplication
from loguru import logger

class SettingsTab(QWidget):
    def __init__(self, config_manager, build_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.build_manager = build_manager
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        # Вкладка выбора пути
        self.path_tab = QWidget()
        path_layout = QVBoxLayout(self.path_tab)
        self.path_label = QLabel(f"Папка Minecraft: {self.config_manager.get('minecraft_path')}")
        path_layout.addWidget(self.path_label)
        self.choose_btn = QPushButton("Изменить папку Minecraft")
        self.choose_btn.clicked.connect(self.choose_path)
        path_layout.addWidget(self.choose_btn)
        self.tabs.addTab(self.path_tab, "Путь к Minecraft")
        # Вкладка логов
        self.logs_tab = QWidget()
        logs_layout = QVBoxLayout(self.logs_tab)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        logs_layout.addWidget(self.log_view)
        log_btns_layout = QHBoxLayout()
        self.btn_open_log2 = QPushButton("Открыть лог")
        self.btn_copy_log2 = QPushButton("Скопировать логи")
        self.btn_open_log2.clicked.connect(self.open_log_file)
        self.btn_copy_log2.clicked.connect(self.copy_log_file)
        log_btns_layout.addWidget(self.btn_open_log2)
        log_btns_layout.addWidget(self.btn_copy_log2)
        log_btns_layout.addStretch()
        logs_layout.addLayout(log_btns_layout)
        self.tabs.addTab(self.logs_tab, "Логи")
        # Таймер для автообновления логов
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.update_log_view)
        self.log_timer.start(2000)

    def choose_path(self):
        current_path = str(self.config_manager.get('minecraft_path'))
        new_path = QFileDialog.getExistingDirectory(self, "Выберите папку Minecraft", current_path)
        if not new_path:
            return
        new_path = Path(new_path)
        has_mc_structure = any((new_path / d).exists() for d in ["versions", "saves"]) or (new_path / "launcher_profiles.json").exists()
        if has_mc_structure:
            reply = QMessageBox.warning(self, "Внимание", "В выбранной папке уже есть структура Minecraft. Продолжить использовать её?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        old_path = Path(current_path)
        if old_path.exists() and old_path != new_path:
            try:
                for item in old_path.iterdir():
                    dest = new_path / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка миграции", f"Ошибка при переносе данных: {e}")
                return
        self.config_manager.set("minecraft_path", str(new_path))
        self.path_label.setText(f"Папка Minecraft: {new_path}")
        QMessageBox.information(self, "Готово", "Путь к папке Minecraft изменён. Перезапустите приложение для применения изменений.")

    def open_log_file(self):
        log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../logs/launcher.log'))
        logger.info(f"[UI] Открытие файла лога: {log_path}")
        try:
            os.startfile(log_path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть лог: {e}")

    def copy_log_file(self):
        log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../logs/launcher.log'))
        logger.info(f"[UI] Копирование содержимого лога в буфер обмена: {log_path}")
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                log_text = f.read()
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(log_text)
            QMessageBox.information(self, "Логи скопированы", "Содержимое лога скопировано в буфер обмена.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось скопировать лог: {e}")

    def update_log_view(self):
        log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../logs/launcher.log'))
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                log_text = f.read()
            self.log_view.setPlainText(log_text)
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)
        except Exception as e:
            self.log_view.setPlainText(f"Ошибка чтения лога: {e}") 