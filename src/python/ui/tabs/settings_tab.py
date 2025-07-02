from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QTabWidget, QTextEdit, QHBoxLayout, QApplication, QLineEdit, QComboBox
from PySide6.QtCore import Qt, QTimer
from pathlib import Path
import shutil
import os
import subprocess
import json
import glob
from PySide6.QtGui import QTextCursor

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
        path_layout.addStretch()
        self.tabs.addTab(self.path_tab, "Путь к Minecraft")
        # Вкладка логов
        self.logs_tab = QWidget()
        logs_layout = QVBoxLayout(self.logs_tab)
        filter_layout = QHBoxLayout()
        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "INFO", "WARNING", "ERROR"])
        self.level_combo.currentTextChanged.connect(self.update_log_view)
        filter_layout.addWidget(QLabel("Уровень:"))
        filter_layout.addWidget(self.level_combo)
        self.event_combo = QComboBox()
        self.event_combo.addItems(["ALL", "download_file", "download_file_attempt", "download_file_error"])
        self.event_combo.currentTextChanged.connect(self.update_log_view)
        filter_layout.addWidget(QLabel("Событие:"))
        filter_layout.addWidget(self.event_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по логам...")
        self.search_edit.textChanged.connect(self.update_log_view)
        filter_layout.addWidget(self.search_edit)
        logs_layout.addLayout(filter_layout)
        self.log_content = QTextEdit()
        self.log_content.setReadOnly(True)
        logs_layout.addWidget(self.log_content)
        btns_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Копировать лог")
        self.copy_btn.clicked.connect(self.copy_log)
        btns_layout.addWidget(self.copy_btn)
        self.open_folder_btn = QPushButton("Открыть папку")
        self.open_folder_btn.clicked.connect(self.open_log_folder)
        btns_layout.addWidget(self.open_folder_btn)
        logs_layout.addLayout(btns_layout)
        self.tabs.addTab(self.logs_tab, "Логи приложения")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.log_file = self._get_latest_log_file()
        self._setup_auto_update()

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

    def _on_tab_changed(self, idx):
        if self.tabs.tabText(idx) == "Логи приложения":
            self.update_log_view()

    def _get_latest_log_file(self):
        log_dir = (Path(__file__).parent.parent.parent / ".." / "logs").resolve()
        files = sorted(glob.glob(str(log_dir / "launcher_*.jsonl")), reverse=True)
        return files[0] if files else None

    def _setup_auto_update(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_log_view)
        self.timer.start(1500)

    def update_log_view(self):
        if not self.log_file or not Path(self.log_file).exists():
            self.log_content.setPlainText("Лог-файл не найден.")
            return
        level = self.level_combo.currentText()
        event = self.event_combo.currentText()
        query = self.search_edit.text().lower()
        lines = []
        html_lines = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    lvl = entry.get("level", "").upper()
                    evt = entry.get("event", "")
                    msg = entry.get("message") or entry.get("msg") or ""
                    if (level == "ALL" or lvl == level) and (event == "ALL" or evt == event) and (query in msg.lower()):
                        color = "#ffffff"
                        if evt == "download_file":
                            color = "#4caf50"  # green
                        elif evt == "download_file_attempt":
                            color = "#2196f3"  # blue
                        elif evt == "download_file_error" or lvl == "ERROR":
                            color = "#f44336"  # red
                        html_lines.append(f'<span style="color:{color}">[{entry.get("time", "")}] [{lvl}] [{evt}] {msg}</span>')
                except Exception:
                    continue
        self.log_content.setHtml("<br>".join(html_lines))
        self.log_content.moveCursor(QTextCursor.End)

    def copy_log(self):
        text = self.log_content.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    def open_log_folder(self):
        if not self.log_file:
            return
        folder = str(Path(self.log_file).parent)
        if os.name == 'nt':
            os.startfile(folder)
        elif os.name == 'posix':
            subprocess.Popen(['xdg-open', folder])
        else:
            QMessageBox.information(self, "Открыть папку", f"Путь: {folder}") 