from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, 
    QListWidget, QListWidgetItem, QSizePolicy, QDialog, QDialogButtonBox, 
    QMessageBox, QMenu, QTabWidget, QCheckBox, QScrollArea, QFrame, QGridLayout, 
    QGraphicsDropShadowEffect, QProgressBar, QButtonGroup, QStackedWidget, QFileDialog, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QTimer, QObject, QRectF, Slot, QThread
from PySide6.QtGui import QPainter, QBrush, QColor, QPen, QFont, QPixmap
import os
import json
import urllib.request
import threading
from core.build_manager import BuildManager
from pathlib import Path
import shutil
import subprocess
import platform
import glob
import uuid

from services.download_service import DownloadService
from services.log_service import LogService
from core.minecraft_runner import MinecraftRunner

# Цвета из CSS
MC_DARK_GREEN = "#2d6135"
MC_GREEN = "#3a7d44"
MC_LIGHT_GREEN = "#4caf50"
MC_ACCENT = "#ffaa00"
MC_BLUE = "#3a7dcf"
MC_DARK_BLUE = "#2d5ca6"
MC_PURPLE = "#6a3dcf"
MC_RED = "#dc3545"
MC_YELLOW = "#ffc107"
MC_DARK = "#121212"
MC_DARKER = "#0a0a0a"
MC_GRAY = "#1e1e1e"
MC_LIGHT_GRAY = "#2d2d2d"
MC_TEXT = "#e0e0e0"
MC_TEXT_LIGHT = "#ffffff"
MC_TEXT_MUTED = "#b0b0b0"
MC_BORDER = "#333"
MC_PIXEL = "rgba(0, 0, 0, 0.15)"

# Заглушки для тестовых данных
VERSION_TYPES = ["release", "snapshot", "beta", "alpha"]
TYPE_LABELS = {"release": "Release", "snapshot": "Snapshot", "beta": "Beta", "alpha": "Alpha"}

MOJANG_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

class VersionCard(QFrame):
    installed_signal = Signal(dict)
    
    def __init__(self, version, installed=False, parent=None):
        super().__init__(parent)
        try:
            if not version or not isinstance(version, dict):
                LogService.log('ERROR', f"[UI] Некорректная версия для VersionCard: {version}", source="InstallationsTab")
                version = {"name": "Unknown", "type": "release"}
                
            self.version = version
            self.setObjectName("VersionCard")
            self.setFrameShape(QFrame.Shape.StyledPanel)
            
            # Стиль карточки версии
            self.setStyleSheet(f"""
                QFrame#VersionCard {{
                    background: {MC_GRAY};
                    border: 2px solid {MC_BORDER};
                    border-radius: 12px;
                    margin: 6px;
                }}
                QFrame#VersionCard:hover {{
                    border: 2px solid {MC_GREEN};
                    background: rgba(58, 125, 68, 0.1);
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                }}
                QLabel {{
                    color: {MC_TEXT};
                }}
                QPushButton {{
                    background: {MC_GREEN};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background: {MC_DARK_GREEN};
                }}
                QPushButton:disabled {{
                    background: #444;
                    color: #aaa;
                }}
                QProgressBar {{
                    height: 6px;
                    border-radius: 3px;
                    background: rgba(0, 0, 0, 0.3);
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {MC_GREEN}, stop:1 {MC_LIGHT_GREEN});
                    border-radius: 3px;
                }}
            """)
            
            # Drop shadow
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(16)
            shadow.setOffset(0, 4)
            shadow.setColor(QColor(0, 0, 0, 100))
            self.setGraphicsEffect(shadow)
            
            # Анимация увеличения
            self.anim = QPropertyAnimation(self, b"geometry")
            self.anim.setDuration(120)
            self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            self._orig_geom = None
            self.enterEvent = self._on_enter
            self.leaveEvent = self._on_leave
            
            layout = QHBoxLayout(self)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(15)
            
            # Информация о версии
            info = QVBoxLayout()
            info.setSpacing(4)
            
            name = QLabel(f"<b>{version['name']}</b>")
            name.setStyleSheet(f"font-size: 16px; color: {MC_TEXT_LIGHT};")
            
            vtype = QLabel(TYPE_LABELS.get(version["type"], version["type"]))
            vtype.setStyleSheet(f"font-size: 14px; color: {MC_TEXT_MUTED};")
            
            date = QLabel(version.get("date", ""))
            date.setStyleSheet(f"font-size: 12px; color: {MC_TEXT_MUTED};")
            
            info.addWidget(name)
            info.addWidget(vtype)
            info.addWidget(date)
            layout.addLayout(info)
            
            layout.addStretch()
            
            # Кнопка установки
            self.install_btn = QPushButton("Установить" if not installed else "Установлено")
            self.install_btn.setEnabled(not installed)
            self.install_btn.clicked.connect(self.start_install)
            layout.addWidget(self.install_btn)
            
            # Статус
            self.status_label = QLabel("Установлено" if installed else "Не установлено")
            self.status_label.setStyleSheet(f"font-size: 14px; color: {MC_GREEN if installed else MC_TEXT_MUTED};")
            layout.addWidget(self.status_label)
            
            # Прогресс-бар
            self.progress = QProgressBar()
            self.progress.setMinimum(0)
            self.progress.setMaximum(100)
            self.progress.setValue(0)
            self.progress.setVisible(False)
            self.progress.setFixedWidth(100)
            layout.addWidget(self.progress)
            
            self.timer = None
            
        except Exception as e:
            LogService.log('ERROR', f"[UI] Ошибка создания VersionCard: {e}", source="InstallationsTab")
            # Создаем минимальный виджет с ошибкой
            self.version = {"name": "Error", "type": "release"}
            layout = QHBoxLayout(self)
            error_label = QLabel("Ошибка создания карточки")
            error_label.setStyleSheet(f"color: {MC_RED};")
            layout.addWidget(error_label)

    def _on_enter(self, event):
        try:
            if not self._orig_geom:
                self._orig_geom = self.geometry()
            rect = self.geometry().adjusted(-6, -6, 6, 6)
            self.anim.stop()
            self.anim.setStartValue(self.geometry())
            self.anim.setEndValue(rect)
            self.anim.start()
        except Exception as e:
            LogService.log('ERROR', f"[UI] Ошибка в _on_enter: {e}", source="InstallationsTab")

    def _on_leave(self, event):
        try:
            if self._orig_geom:
                self.anim.stop()
                self.anim.setStartValue(self.geometry())
                self.anim.setEndValue(self._orig_geom)
                self.anim.start()
        except Exception as e:
            LogService.log('ERROR', f"[UI] Ошибка в _on_leave: {e}", source="InstallationsTab")

    def start_install(self):
        try:
            self.install_btn.setEnabled(False)
            self.progress.setVisible(True)
            self.progress.setValue(0)
            self.status_label.setText("Установка...")
            self.status_label.setStyleSheet(f"color: {MC_BLUE};")
            
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._on_progress)
            self.timer.start(30)
            
        except Exception as e:
            LogService.log('ERROR', f"[UI] Ошибка при запуске установки: {e}", source="InstallationsTab")

    def _on_progress(self):
        try:
            val = self.progress.value() + 2
            if val >= 100:
                self.progress.setValue(100)
                self.progress.setVisible(False)
                self.status_label.setText("Установлено")
                self.status_label.setStyleSheet(f"color: {MC_GREEN};")
                self.install_btn.setText("Установлено")
                self.install_btn.setEnabled(False)
                if self.timer:
                    self.timer.stop()
                self.installed_signal.emit(self.version)
            else:
                self.progress.setValue(val)
        except Exception as e:
            LogService.log('ERROR', f"[UI] Ошибка в _on_progress: {e}", source="InstallationsTab")

class InstalledVersionWidget(QWidget):
    remove_requested = Signal(dict)
    launch_requested = Signal(dict)
    
    def __init__(self, version, parent=None):
        super().__init__(parent)
        self.version = version
        self.build_name = version.get('name', '')
        self.status = version.get('status', 'unknown')
        self.progress = version.get('progress', 0)
        self.message = version.get('message', '')
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.setStyleSheet("""
            QWidget {
                background: #23272e;
                border-radius: 14px;
                border: 2px solid #333;
            }
        """)
        # Название и иконка
        title_layout = QHBoxLayout()
        title = QLabel(f"<b>{self.build_name}</b>")
        title.setStyleSheet("font-size: 16px; color: #fff;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)
        # Версия и лоадер
        sub = QLabel(f"{self.version.get('minecraft_version', '')} - {self.version.get('loader', '')}")
        sub.setStyleSheet("color: #aaa; font-size: 13px;")
        layout.addWidget(sub)
        # Статус
        self.status_label = QLabel(self._get_status_text(self.status))
        self.status_label.setStyleSheet(f"color: {self._get_status_color(self.status)}; font-size: 13px;")
        layout.addWidget(self.status_label)
        # Кнопки
        btns = QHBoxLayout()
        self.launch_btn = QPushButton("Запустить")
        self.launch_btn.setEnabled(self.status in ("ready", "Готово к запуску"))
        self.launch_btn.clicked.connect(self._on_launch)
        btns.addWidget(self.launch_btn)
        del_btn = QPushButton("Удалить")
        del_btn.setStyleSheet("background: #dc3545; color: #fff;")
        del_btn.clicked.connect(self._on_delete)
        btns.addWidget(del_btn)
        layout.addLayout(btns)
    def _get_status_text(self, status):
        if status == "ready": return "Готово к запуску"
        if status == "downloading": return "Загрузка..."
        if status == "installing": return "Установка..."
        if status == "error": return "Ошибка"
        return "Неизвестно"
    def _get_status_color(self, status):
        if status == "ready": return "#4caf50"
        if status == "downloading": return "#ffaa00"
        if status == "installing": return "#3a7dcf"
        if status == "error": return "#dc3545"
        return "#aaa"
    def update_status(self, status, progress=0, message=""):
        self.status = status
        self.progress = progress
        self.message = message
        self.status_label.setText(self._get_status_text(status))
        self.status_label.setStyleSheet(f"color: {self._get_status_color(status)}; font-size: 13px;")
        self.launch_btn.setEnabled(status == "ready")
    def _on_launch(self):
        self.launch_requested.emit(self.version)
    def _on_delete(self):
        self.remove_requested.emit(self.version)

class LoaderUpdater(QObject):
    update = Signal(list)

class RoundedPanel(QWidget):
    def __init__(self, parent=None, radius=18, bg_color=MC_GRAY, border_color=MC_BORDER, border_width=2):
        super().__init__(parent)
        self.radius = radius
        self.bg_color = QColor(bg_color)
        self.border_color = QColor(border_color)
        self.border_width = border_width
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        
        # Добавляем эффект размытия фона
        self.setGraphicsEffect(QGraphicsDropShadowEffect(
            blurRadius=15, 
            xOffset=0, 
            yOffset=4, 
            color=QColor(0, 0, 0, 100)
        ))

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.rect())
            rect.adjust(self.border_width/2, self.border_width/2, -self.border_width/2, -self.border_width/2)
            
            # Рисуем фон с прозрачностью
            painter.setBrush(QBrush(QColor(self.bg_color.red(), self.bg_color.green(), self.bg_color.blue(), 200)))
            painter.setPen(QPen(self.border_color, self.border_width))
            painter.drawRoundedRect(rect, self.radius, self.radius)
        except Exception as e:
            LogService.log('ERROR', f"[UI] Ошибка отрисовки RoundedPanel: {e}", source="InstallationsTab")

class BuildWorker(QObject):
    progress = Signal(int, str)
    finished = Signal()
    error = Signal(str)
    log_msg = Signal(str)

    def __init__(self, build_manager, build_config):
        super().__init__()
        self.build_manager = build_manager
        self.build_config = build_config
        self.is_running = False
        LogService.log('INFO', f"[WORKER] BuildWorker создан для сборки: {build_config.get('name', 'Unknown')}", source="InstallationsTab")

    def run(self):
        print('BuildWorker.run called')
        self.is_running = True
        
        def progress_callback(*args):
            # Универсальная обработка: поддержка 1, 2 или 3 аргументов
            if not self.is_running:
                return
            if len(args) == 3:
                current, total, message = args
            elif len(args) == 2:
                current, message = args
                total = None
            elif len(args) == 1:
                current = args[0]
                total = None
                message = None
            else:
                return
            print(f"PROGRESS: {current}/{total if total is not None else '-'} - {message}")
            self.progress.emit(current, message)
            
        def log_callback(msg):
            if self.is_running:
                print(f"LOG: {msg}")
                self.log_msg.emit(msg)
            
        try:
            success = self.build_manager.create_build(self.build_config, progress_callback, log_callback)
            if success:
                self.finished.emit()
            else:
                self.error.emit("Ошибка создания сборки")
        except Exception as e:
            print(f"EXCEPTION in BuildWorker.run: {e}")
            self.log_msg.emit(f"Критическая ошибка: {e}")
            self.error.emit(str(e))
        finally:
            self.is_running = False
    
    def stop(self):
        """Остановка процесса создания сборки"""
        self.is_running = False

class InstallationsTab(QWidget):
    progress_update = Signal(int, str)
    request_update_builds = Signal()
    request_add_build = Signal(dict)
    request_handle_error = Signal(str, str)
    request_remove_build = Signal(dict)
    
    def __init__(self, build_manager, minecraft_manager, get_nick_func=None, parent=None):
        super().__init__(parent)
        self.build_manager = build_manager
        self.minecraft_manager = minecraft_manager
        self.get_nick_func = get_nick_func or (lambda: "Player")
        self.threads = []  # Для хранения активных QThread
        self.build_widgets = {}  # Словарь для хранения виджетов сборок
        self.current_build_name = None  # Имя выбранной сборки
        self.setup_ui()
        self.update_my_builds()
        
        # Таймер для автообновления
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.auto_update_builds)
        self.update_timer.start(2000)  # Обновление каждые 2 секунды
        
        # Сигналы для потокобезопасного обновления UI
        self.request_update_builds.connect(self.update_my_builds)
        self.request_add_build.connect(self.add_build_to_list)
        self.request_handle_error.connect(self.handle_build_error)
        self.request_remove_build.connect(self.remove_build)
        
        # Основной стиль вкладки
        self.setStyleSheet(f"""
            QWidget {{
                background: {MC_DARK};
                color: {MC_TEXT};
                font-family: 'Rubik', Arial, sans-serif;
            }}
            QPushButton.sidebar-tab {{
                border-radius: 8px;
                padding: 14px 18px;
                font-size: 16px;
                color: {MC_TEXT_MUTED};
                background: {MC_GRAY};
                border: 2px solid {MC_BORDER};
                margin-bottom: 8px;
                text-align: left;
                font-weight: 500;
            }}
            QPushButton.sidebar-tab:checked {{
                background: {MC_BLUE};
                color: {MC_TEXT_LIGHT};
                border: 2px solid {MC_BLUE};
                font-weight: bold;
            }}
            QPushButton.sidebar-tab:hover {{
                background: {MC_GREEN};
                color: {MC_TEXT_LIGHT};
            }}
        """)
        LogService.subscribe(self._ui_log_subscriber)

    def _ui_log_subscriber(self, log_entry):
        # Фильтруем логи по source (build_name)
        if self.current_build_name and log_entry.get('source') == self.current_build_name:
            self.log_text.append(log_entry['message'])

    def select_build(self, build_name):
        # Вызывается при выборе сборки пользователем
        self.current_build_name = build_name
        self.log_text.clear()
        # Можно подгрузить последние логи из LogService.get_recent() и отфильтровать по source
        for log in LogService.get_recent(200):
            if log.get('source') == build_name:
                self.log_text.append(log['message'])

    def handle_build_error(self, build_name, error_message):
        """Stub for handling build errors. Implement logic if needed. Arguments are likely build name/id and error message."""
        pass

    def add_build_to_list(self, build_info):
        """Stub for adding a build to the list. Implement logic if needed. Argument is likely a dict with build info."""
        pass

    def auto_update_builds(self):
        """Stub for auto-update builds. Implement logic if needed."""
        pass

    def remove_build(self, build_info):
        """Stub for removing a build from the list. Implement logic if needed. Argument is likely a dict with build info."""
        pass

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(0)
        
        # Sidebar с вкладками
        sidebar = QVBoxLayout()
        sidebar.setSpacing(0)
        sidebar.setContentsMargins(0, 0, 24, 0)
        self.btn_my = QPushButton("Мои сборки")
        self.btn_my.setCheckable(True)
        self.btn_my.setProperty("class", "sidebar-tab")
        self.btn_create = QPushButton("Создать сборку")
        self.btn_create.setCheckable(True)
        self.btn_create.setProperty("class", "sidebar-tab")
        self.btn_ready = QPushButton("Готовые сборки")
        self.btn_ready.setCheckable(True)
        self.btn_ready.setProperty("class", "sidebar-tab")
        sidebar.addWidget(self.btn_my)
        sidebar.addWidget(self.btn_create)
        sidebar.addWidget(self.btn_ready)
        sidebar.addStretch()
        self.sidebar_btns = [self.btn_my, self.btn_create, self.btn_ready]
        main_layout.addLayout(sidebar)
        
        # Контейнер для контента вкладок
        self.tabs_content = QStackedWidget()
        main_layout.addWidget(self.tabs_content)
        
        # Вкладка 'Мои сборки' с прокруткой и сеткой
        self.my_builds_tab = QWidget()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(18)
        self.grid_layout.setContentsMargins(18, 18, 18, 18)
        self.scroll_area.setWidget(self.grid_container)
        vbox = QVBoxLayout(self.my_builds_tab)
        vbox.addWidget(self.scroll_area)
        self.tabs_content.addWidget(self.my_builds_tab)
        
        # Вкладка 'Создать сборку'
        self.create_tab = QWidget()
        self.setup_create_tab()
        self.tabs_content.addWidget(self.create_tab)
        
        # Вкладка 'Готовые сборки'
        self.ready_tab = RoundedPanel()
        ready_layout = QVBoxLayout(self.ready_tab)
        ready_layout.addWidget(QLabel("Готовые сборки (скоро)", alignment=Qt.AlignmentFlag.AlignCenter))
        self.tabs_content.addWidget(self.ready_tab)
        
        # Логика переключения вкладок
        self.btn_my.clicked.connect(lambda: self.set_active_tab(0))
        self.btn_create.clicked.connect(lambda: self.set_active_tab(1))
        self.btn_ready.clicked.connect(lambda: self.set_active_tab(2))
        self.set_active_tab(0)
        
        # Обработка смены лоадера
        loader_updater = LoaderUpdater()
        
        def update_loader_versions(versions):
            self.loader_ver_combo.clear()
            if versions:
                self.loader_ver_combo.addItems(versions)
            else:
                self.loader_ver_combo.addItem('Версии не найдены')
            update_build_name()
        
        loader_updater.update.connect(update_loader_versions)
        
        def on_loader_changed(text):
            if text == "Vanilla":
                self.loader_ver_combo.clear()
                self.loader_ver_combo.setVisible(False)
                update_build_name()
            elif text == "Fabric":
                self.loader_ver_combo.clear()
                self.loader_ver_combo.setVisible(True)
                mc_version = self.version_combo.currentText()
                def fetch_fabric_versions():
                    versions = self.minecraft_manager.get_fabric_loader_versions(mc_version)
                    loader_updater.update.emit(versions)
                    update_build_name()
                threading.Thread(target=fetch_fabric_versions).start() if mc_version else None
            elif text == "Forge":
                self.loader_ver_combo.clear()
                self.loader_ver_combo.setVisible(True)
                mc_version = self.version_combo.currentText()
                def fetch_forge_versions():
                    versions = self.minecraft_manager.get_forge_loader_versions(mc_version)
                    loader_updater.update.emit(versions)
                    update_build_name()
                threading.Thread(target=fetch_forge_versions).start() if mc_version else None
            elif text == "Quilt":
                self.loader_ver_combo.clear()
                self.loader_ver_combo.setVisible(True)
                mc_version = self.version_combo.currentText()
                def fetch_quilt_versions():
                    versions = self.minecraft_manager.get_quilt_loader_versions(mc_version)
                    loader_updater.update.emit(versions)
                    update_build_name()
                threading.Thread(target=fetch_quilt_versions).start() if mc_version else None
            elif text == "NeoForge":
                self.loader_ver_combo.clear()
                self.loader_ver_combo.setVisible(True)
                mc_version = self.version_combo.currentText()
                def fetch_neoforge_versions():
                    versions = self.minecraft_manager.get_neoforge_loader_versions(mc_version)
                    loader_updater.update.emit(versions)
                    update_build_name()
                threading.Thread(target=fetch_neoforge_versions).start() if mc_version else None
            elif text == "Paper":
                self.loader_ver_combo.clear()
                self.loader_ver_combo.setVisible(True)
                mc_version = self.version_combo.currentText()
                def fetch_paper_versions():
                    versions = self.minecraft_manager.get_paper_versions(mc_version)
                    loader_updater.update.emit(versions)
                    update_build_name()
                threading.Thread(target=fetch_paper_versions).start() if mc_version else None
                self.loader_combo.setToolTip("Paper — только для серверов. Нельзя запускать моды, только плагины!")
            elif text == "Purpur":
                self.loader_ver_combo.clear()
                self.loader_ver_combo.setVisible(True)
                mc_version = self.version_combo.currentText()
                def fetch_purpur_versions():
                    versions = self.minecraft_manager.get_purpur_versions(mc_version)
                    loader_updater.update.emit(versions)
                    update_build_name()
                threading.Thread(target=fetch_purpur_versions).start() if mc_version else None
                self.loader_combo.setToolTip("Purpur — только для серверов. Нельзя запускать моды, только плагины!")
            else:
                self.loader_ver_combo.clear()
                self.loader_ver_combo.addItems(["0.14.21", "0.14.20", "0.14.19"])
                self.loader_ver_combo.setVisible(True)
                update_build_name()
        
        self.loader_combo.currentTextChanged.connect(on_loader_changed)
        
        # При смене версии Minecraft, если выбран Fabric, обновлять список версий лоадера
        def on_mc_version_changed():
            on_loader_changed(self.loader_combo.currentText())
        self.version_combo.currentTextChanged.connect(lambda _: on_mc_version_changed())
        
        # Всплывающая подсказка при наведении на Paper/Purpur
        def show_loader_tooltip(index):
            text = self.loader_combo.itemText(index)
            if text == "Paper":
                self.loader_combo.setToolTip("Paper — только для серверов. Нельзя запускать моды, только плагины!")
            elif text == "Purpur":
                self.loader_combo.setToolTip("Purpur — только для серверов. Нельзя запускать моды, только плагины!")
            else:
                self.loader_combo.setToolTip("")
        
        self.loader_combo.highlighted.connect(show_loader_tooltip)
        
        # Автоматическое формирование названия сборки
        def update_build_name():
            mc_version = self.version_combo.currentText()
            loader = self.loader_combo.currentText()
            
            if not mc_version:
                return
            
            if loader == "Vanilla":
                build_name = f"Minecraft {mc_version}"
            else:
                build_name = f"Minecraft {mc_version} with {loader}"
            
            self.name_edit.setText(build_name)
        
        # Подключаем обновление названия к изменениям в комбобоксах
        self.version_combo.currentTextChanged.connect(lambda _: update_build_name())
        self.loader_combo.currentTextChanged.connect(lambda _: update_build_name())
        self.loader_ver_combo.currentTextChanged.connect(lambda _: update_build_name())
        
        # Скрыть loader_ver_combo при инициализации, если выбран Vanilla
        if self.loader_combo.currentText() == "Vanilla":
            self.loader_ver_combo.setVisible(False)
        
        # Инициализируем название при загрузке
        if self.version_combo.count() > 0:
            update_build_name()

    def setup_create_tab(self):
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtGui import QPixmap
        form_outer = QVBoxLayout(self.create_tab)
        form_outer.setContentsMargins(24, 24, 24, 24)
        form_outer.setSpacing(18)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)
        # Превью и кнопка выбора картинки
        img_layout = QVBoxLayout()
        self.image_preview = QLabel()
        self.image_preview.setFixedSize(120, 120)
        self.image_preview.setStyleSheet(f"""
            background: {MC_GRAY};
            border: 2.5px solid {MC_BORDER};
            border-radius: 8px;
            font-size: 16px;
            color: {MC_TEXT_MUTED};
            qproperty-alignment: AlignCenter;
        """)
        self.image_preview.setText("Нет картинки")
        img_layout.addWidget(self.image_preview)
        self.select_img_btn = QPushButton("Выбрать картинку")
        self.select_img_btn.setStyleSheet(f"padding: 6px 16px; margin-top: 8px;")
        img_layout.addWidget(self.select_img_btn)
        self.selected_image_path = None
        def choose_image():
            file, _ = QFileDialog.getOpenFileName(self.create_tab, "Выберите картинку", "", "Images (*.png *.jpg *.jpeg *.bmp)")
            if file:
                self.selected_image_path = file
                pixmap = QPixmap(file)
                if not pixmap.isNull():
                    self.image_preview.setPixmap(pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    self.image_preview.setText("Ошибка картинки")
        self.select_img_btn.clicked.connect(choose_image)
        top_layout.addLayout(img_layout)
        
        # Поля формы
        fields_layout = QVBoxLayout()
        fields_layout.setSpacing(14)
        
        # Поле названия сборки
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Название сборки")
        self.name_edit.setStyleSheet(f"""
            font-size: 16px;
            padding: 10px;
            border-radius: 8px;
            border: 2px solid {MC_BORDER};
            background: {MC_GRAY};
            color: {MC_TEXT_LIGHT};
        """)
        fields_layout.addWidget(self.name_edit)
        
        # Комбобокс версии Minecraft
        self.version_combo = QComboBox()
        all_versions = self.minecraft_manager.get_available_versions()
        release_versions = [v["id"] for v in all_versions if v["type"] == "release"]
        self.version_combo.addItems(release_versions)
        self.version_combo.setStyleSheet(f"""
            QComboBox {{
                background: {MC_GRAY};
                border: 2px solid {MC_BORDER};
                border-radius: 8px;
                color: {MC_TEXT_LIGHT};
                font-size: 16px;
                padding: 10px;
            }}
            QComboBox::drop-down {{
                border: none;
                background: transparent;
            }}
            QComboBox QAbstractItemView {{
                background: {MC_GRAY};
                color: {MC_TEXT_LIGHT};
                border: 2px solid {MC_BORDER};
                selection-background-color: rgba(58, 125, 207, 0.3);
                selection-color: {MC_TEXT_LIGHT};
                outline: 0;
            }}
        """)
        
        # Комбобокс лоадера
        self.loader_combo = QComboBox()
        self.loader_combo.addItems(["Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"])
        self.loader_combo.setStyleSheet(self.version_combo.styleSheet())
        
        # Комбобокс версии лоадера
        self.loader_ver_combo = QComboBox()
        self.loader_ver_combo.addItems(["0.14.21", "0.14.20", "0.14.19"])
        self.loader_ver_combo.setStyleSheet(self.version_combo.styleSheet())
        
        fields_layout.addWidget(self.version_combo)
        fields_layout.addWidget(self.loader_combo)
        fields_layout.addWidget(self.loader_ver_combo)
        top_layout.addLayout(fields_layout)
        form_outer.addLayout(top_layout)
        
        # Логи процесса
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(120)
        self.log_text.setStyleSheet(f"""
            background: {MC_GRAY};
            border: 2px solid {MC_BORDER};
            border-radius: 8px;
            color: {MC_TEXT_LIGHT};
            font-size: 14px;
            padding: 8px;
        """)
        form_outer.addWidget(self.log_text)
        form_outer.addStretch()
        
        # Кнопка создания и прогресс-бар
        create_btn = QPushButton("Создать сборку")
        create_btn.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {MC_BLUE}, stop:1 {MC_PURPLE});
            color: white;
            border-radius: 8px;
            font-weight: bold;
            font-size: 18px;
            padding: 12px 24px;
            border: none;
        """)
        create_btn.setMinimumHeight(48)
        create_btn.clicked.connect(self.create_build)
        form_outer.addWidget(create_btn)
        
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setStyleSheet(f"""
            height: 8px;
            border-radius: 4px;
            background: {MC_GRAY};
            border: 1px solid {MC_BORDER};
        """)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        form_outer.addWidget(self.progress)

    @Slot(int, str)
    def _on_progress_update(self, value, text):
        try:
            assert threading.current_thread() == threading.main_thread(), "_on_progress_update: UI update not in main thread!"
            
            LogService.log('DEBUG', f"[UI] Обновление прогресса: {value}% - {text}", source="InstallationsTab")
            
            # Проверяем, что прогресс-бар доступен
            if not hasattr(self, 'progress') or not self.progress:
                LogService.log('WARNING', "[UI] Прогресс-бар недоступен", source="InstallationsTab")
                return
                
            # Обновляем прогресс-бар
            try:
                if value >= 0:
                    self.progress.setValue(value)
                    self.progress.setVisible(True)
                else:
                    # Отрицательное значение означает ошибку
                    self.progress.setVisible(False)
                    
                # Обновляем текст статуса если есть
                # status_label может не существовать в этом классе
                        
            except Exception as e:
                LogService.log('ERROR', f"[UI] Ошибка обновления прогресс-бара: {e}", source="InstallationsTab")
                
        except Exception as e:
            LogService.log('CRITICAL', f"[UI] Критическая ошибка в _on_progress_update: {e}", source="InstallationsTab")

    def _is_library_needed(self, library: dict, current_os: str) -> bool:
        """
        Проверяет, нужна ли библиотека для текущей ОС на основе правил
        """
        rules = library.get("rules", [])
        if not rules:
            return True  # если нет правил - нужна всегда
            
        for rule in rules:
            action = rule.get("action", "allow")
            os_rule = rule.get("os", {})
            
            # Проверяем ОС
            if "name" in os_rule:
                rule_os = os_rule["name"]
                if rule_os == current_os:
                    # Библиотека для нашей ОС
                    if action == "allow":
                        return True
                    elif action == "disallow":
                        return False
                else:
                    # Библиотека для другой ОС
                    if action == "allow":
                        return False
                    elif action == "disallow":
                        return True
                        
            # Проверяем архитектуру (если указана)
            if "arch" in os_rule:
                import platform
                current_arch = platform.machine().lower()
                rule_arch = os_rule["arch"]
                
                if current_arch == rule_arch:
                    if action == "allow":
                        return True
                    elif action == "disallow":
                        return False
                else:
                    if action == "allow":
                        return False
                    elif action == "disallow":
                        return True
        
        # Если правила не сработали - библиотека нужна
        return True

    def update_my_builds(self):
        from pathlib import Path
        import os
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QScrollArea, QWidget, QVBoxLayout, QHBoxLayout
        # Удаляем старый scroll_area, если есть
        if hasattr(self, 'scroll_area') and self.scroll_area:
            layout = self.my_builds_tab.layout() or QVBoxLayout(self.my_builds_tab)
            layout.removeWidget(self.scroll_area)
            self.scroll_area.deleteLater()
            self.scroll_area = None
        # Создаём scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(f"background: transparent; border: none;")
        content_widget = QWidget()
        vbox = QVBoxLayout(content_widget)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(16)
        # Получить список сборок из папки versions
        versions_path = self.build_manager.config_manager.get_versions_path()
        builds = []
        for folder in os.listdir(versions_path):
            build_dir = Path(versions_path) / folder
            if build_dir.is_dir():
                builds.append(folder)
        if not builds:
            vbox.addWidget(QLabel("У вас пока нет сборок", alignment=Qt.AlignmentFlag.AlignCenter))
        else:
            for build in builds:
                build_dir = Path(versions_path) / build
                # Картинка
                img_path = None
                for ext in ('.png', '.jpg', '.jpeg', '.bmp'):
                    candidate = build_dir / f"{build}{ext}"
                    if candidate.exists():
                        img_path = candidate
                        break
                # Проверка целостности сборки
                errors = []
                json_path = build_dir / f"{build}.json"
                jar_path = build_dir / f"{build}.jar"
                if not json_path.exists():
                    errors.append("Нет JSON-файла версии")
                if not jar_path.exists():
                    errors.append("Нет jar-файла версии")
                missing_libs = []
                if json_path.exists():
                    import json
                    import platform
                    with open(json_path, encoding="utf-8") as f:
                        version_json = json.load(f)
                    libs_dir = Path(self.build_manager.config_manager.get('minecraft_path')) / "libraries"
                    
                    # Определяем текущую ОС
                    current_os = platform.system().lower()
                    if current_os == "windows":
                        current_os = "windows"
                    elif current_os == "linux":
                        current_os = "linux" 
                    elif current_os == "darwin":
                        current_os = "osx"
                    else:
                        current_os = "windows"  # fallback
                    
                    for lib in version_json.get('libraries', []):
                        # Проверяем, нужна ли библиотека для текущей ОС
                        if not self._is_library_needed(lib, current_os):
                            continue
                            
                        artifact = lib.get('downloads', {}).get('artifact')
                        if artifact:
                            lib_path = libs_dir / artifact['path']
                            if not lib_path.exists():
                                # Подробное логирование отсутствующей библиотеки
                                url = artifact.get('url', 'нет url')
                                sha1 = artifact.get('sha1', 'нет sha1')
                                LogService.log('WARNING', f"[MISSING LIB] Build: {build} | Path: {lib_path} | URL: {url} | SHA1: {sha1}", source=build)
                                missing_libs.append(str(lib_path))
                    if missing_libs:
                        errors.append(f"Нет библиотек: {len(missing_libs)} шт.")
                # Карточка
                card = QFrame()
                card.setStyleSheet(f"""
                    QFrame {{
                        background: {MC_GRAY};
                        border: 2px solid {MC_BORDER};
                        border-radius: 12px;
                        margin: 0px;
                        padding: 10px 18px;
                    }}
                """)
                card_layout = QHBoxLayout(card)
                card_layout.setContentsMargins(10, 8, 10, 8)
                card_layout.setSpacing(18)
                # Картинка превью
                img_label = QLabel()
                img_label.setFixedSize(64, 64)
                if img_path:
                    pixmap = QPixmap(str(img_path))
                    img_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    img_label.setText("Нет\nкартинки")
                    img_label.setStyleSheet(f"color: {MC_TEXT_MUTED}; font-size: 12px;")
                card_layout.addWidget(img_label)
                # Если есть ошибки — выводим предупреждение
                if errors:
                    err_label = QLabel("<br>".join(errors))
                    err_label.setStyleSheet("color: #e74c3c; font-size: 13px; font-weight: bold;")
                    card_layout.addWidget(err_label)
                # Вертикальный layout для названия и кнопок
                info_vbox = QVBoxLayout()
                info_vbox.setSpacing(8)
                # Название
                name_label = QLabel(f"<b>{build}</b>")
                name_label.setStyleSheet(f"font-size: 18px; color: {MC_TEXT_LIGHT};")
                info_vbox.addWidget(name_label)
                # Горизонтальный layout для кнопок
                btns_hbox = QHBoxLayout()
                btns_hbox.setSpacing(12)
                # Кнопка Играть
                play_btn = QPushButton("Играть")
                play_btn.setObjectName("playBtn")
                play_btn.setStyleSheet(
                    "QPushButton#playBtn {"
                    "padding: 8px 18px;"
                    "border-radius: 8px;"
                    "background: #3a7d44;"
                    "color: white;"
                    "font-weight: bold;"
                    "border: none;"
                    "}"
                )
                def launch_selected_build():
                    import shutil
                    import threading
                    print("[DEBUG] Играть нажата")
                    LogService.log('DEBUG', "[DEBUG] Играть нажата", source=build)
                    build_dir = Path(versions_path) / build
                    json_path = build_dir / f"{build}.json"
                    jar_path = build_dir / f"{build}.jar"
                    print(f"[DEBUG] build_dir: {build_dir}, json_path: {json_path}, jar_path: {jar_path}")
                    LogService.log('DEBUG', f"[DEBUG] build_dir: {build_dir}, json_path: {json_path}, jar_path: {jar_path}", source=build)
                    # Проверка наличия java
                    java_path_setting = self.build_manager.config_manager.get('java_path', 'auto')
                    java_path = None
                    if java_path_setting and java_path_setting != 'auto':
                        java_path = shutil.which(java_path_setting)
                    if not java_path:
                        # Пробуем найти java в PATH
                        java_path = shutil.which('java')
                    if not java_path and platform.system() == 'Windows':
                        # Пробуем найти javaw.exe/java.exe в Program Files на всех дисках
                        candidates = []
                        drives = [f'{chr(d)}:' for d in range(67, 91) if os.path.exists(f'{chr(d)}:')]  # C: ... Z:
                        for drive in drives:
                            for pf_base in ['Program Files', 'Program Files (x86)']:
                                pf = os.path.join(drive + '\\', pf_base)
                                if os.path.exists(pf):
                                    candidates += glob.glob(os.path.join(pf, 'Java', '*', 'bin', 'java.exe'))
                                    candidates += glob.glob(os.path.join(pf, 'Java', '*', 'bin', 'javaw.exe'))
                        if candidates:
                            java_path = candidates[0]
                    print(f"[DEBUG] java_path: {java_path}")
                    LogService.log('DEBUG', f"[DEBUG] java_path: {java_path}", source=build)
                    if java_path:
                        # Сохраняем найденный путь для будущих запусков
                        self.build_manager.config_manager.set('java_path', java_path)
                    if not java_path:
                        LogService.log('ERROR', '[ERROR] Java не найдена! Установите Java 17+ и добавьте в PATH или настройте путь в настройках.', source=build)
                        print('[ERROR] Java не найдена!')
                        return
                    # Проверка jar-файла
                    if not json_path.exists() or not jar_path.exists():
                        LogService.log('ERROR', f'[ERROR] Не найден json или jar-файл: {json_path}, {jar_path}', source=build)
                        print(f'[ERROR] Не найден json или jar-файл: {json_path}, {jar_path}')
                        return
                    try:
                        with open(json_path, encoding="utf-8") as f:
                            version_json = json.load(f)
                        print("[DEBUG] version_json загружен")
                        LogService.log('DEBUG', "[DEBUG] version_json загружен", source=build)
                        # 1. Собираем classpath
                        libraries = []
                        libs_dir = Path(self.build_manager.config_manager.get('minecraft_path')) / "libraries"
                        # Определяем текущую ОС
                        current_os = platform.system().lower()
                        if current_os == "windows":
                            current_os = "windows"
                        elif current_os == "linux":
                            current_os = "linux" 
                        elif current_os == "darwin":
                            current_os = "osx"
                        else:
                            current_os = "windows"  # fallback
                        print(f"[DEBUG] current_os: {current_os}")
                        LogService.log('DEBUG', f"[DEBUG] current_os: {current_os}", source=build)
                        for lib in version_json.get("libraries", []):
                            # Проверяем, нужна ли библиотека для текущей ОС
                            if not self._is_library_needed(lib, current_os):
                                continue
                            artifact = lib.get("downloads", {}).get("artifact")
                            if artifact:
                                lib_path = libs_dir / artifact["path"]
                                if not lib_path.exists():
                                    LogService.log('WARNING', f'[WARNING] Библиотека не найдена: {lib_path}', source=build)
                                    print(f'[WARNING] Библиотека не найдена: {lib_path}')
                                libraries.append(str(lib_path))
                        classpath = os.pathsep.join(libraries + [str(jar_path)])
                        print(f"[DEBUG] classpath: {classpath}")
                        LogService.log('DEBUG', f"[DEBUG] classpath: {classpath}", source=build)
                        # 2. Получаем mainClass
                        main_class = version_json.get("mainClass")
                        print(f"[DEBUG] mainClass: {main_class}")
                        LogService.log('DEBUG', f"[DEBUG] mainClass: {main_class}", source=build)
                        if not main_class:
                            LogService.log('ERROR', '[ERROR] mainClass не найден в json', source=build)
                            print('[ERROR] mainClass не найден в json')
                            return
                        # 3. Формируем переменные для подстановки (ОФФЛАЙН-РЕЖИМ)
                        nick = self.get_nick_func() if callable(self.get_nick_func) else "Player"
                        offline_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, str(nick)))
                        args = {
                            "auth_player_name": nick,
                            "version_name": build,
                            "game_directory": str(build_dir),
                            "assets_root": str(Path(self.build_manager.config_manager.get('minecraft_path')) / "assets"),
                            "assets_index_name": version_json.get("assetIndex", {}).get("id", ""),
                            "auth_uuid": offline_uuid,
                            "auth_access_token": "0",  # Оффлайн-режим
                            "clientid": "",
                            "auth_xuid": "",
                            "user_type": "legacy",  # Оффлайн-режим
                            "user_properties": "{}",
                            "version_type": version_json.get("type", "release"),
                            "resolution_width": 854,
                            "resolution_height": 480,
                            "natives_directory": str(build_dir / "natives"),
                            "launcher_name": "TKML",
                            "launcher_version": "1.0",
                            "classpath": classpath,
                        }
                        for k, v in version_json.items():
                            if k not in args:
                                args[k] = v
                        # 4. Собираем JVM arguments
                        memory_mb = self.build_manager.config_manager.get('memory_mb', 0)
                        jvm_args = []
                        if memory_mb and str(memory_mb).isdigit() and int(memory_mb) > 0:
                            jvm_args.append(f'-Xmx{int(memory_mb)}M')
                        for item in version_json.get("arguments", {}).get("jvm", []):
                            if isinstance(item, str):
                                jvm_args.append(item)
                            elif isinstance(item, dict):
                                rules = item.get("rules")
                                allowed = True
                                if rules:
                                    allowed = False
                                    for rule in rules:
                                        if rule.get("action") == "allow":
                                            os_rule = rule.get("os", {})
                                            if not os_rule or os_rule.get("name") == "windows":
                                                allowed = True
                                        if rule.get("action") == "disallow":
                                            os_rule = rule.get("os", {})
                                            if os_rule.get("name") == "windows":
                                                allowed = False
                                if allowed:
                                    value = item.get("value")
                                    if isinstance(value, list):
                                        jvm_args.extend(value)
                                    else:
                                        jvm_args.append(value)
                        print(f"[DEBUG] jvm_args: {jvm_args}")
                        LogService.log('DEBUG', f"[DEBUG] jvm_args: {jvm_args}", source=build)
                        def safe_format(s):
                            try:
                                return s.replace('${', '{').format_map(DefaultDictEmpty(args))
                            except Exception as e:
                                LogService.log('ERROR', f'[ERROR] Ошибка подстановки аргумента: {e}', source=build)
                                print(f'[ERROR] Ошибка подстановки аргумента: {e}')
                                return s
                        class DefaultDictEmpty(dict):
                            def __missing__(self, key):
                                return ''
                        jvm_args = [safe_format(v) if isinstance(v, str) else v for v in jvm_args]
                        # 5. Собираем game arguments
                        game_args = []
                        for item in version_json.get("arguments", {}).get("game", []):
                            if isinstance(item, str):
                                game_args.append(item)
                            elif isinstance(item, dict):
                                rules = item.get("rules")
                                allowed = True
                                if rules:
                                    allowed = False
                                    for rule in rules:
                                        if rule.get("action") == "allow":
                                            allowed = True
                                        if rule.get("action") == "disallow":
                                            allowed = False
                                if allowed:
                                    value = item.get("value")
                                    if isinstance(value, list):
                                        game_args.extend(value)
                                    else:
                                        game_args.append(value)
                        game_args = [arg for arg in game_args if not (isinstance(arg, str) and arg.strip().startswith("--demo"))]
                        game_args = [safe_format(v) if isinstance(v, str) else v for v in game_args]
                        
                        # Фильтруем пустые quick play аргументы
                        filtered_game_args = []
                        skip_next = False
                        for i, arg in enumerate(game_args):
                            if skip_next:
                                skip_next = False
                                continue
                            
                            if isinstance(arg, str) and arg.startswith("--quickPlay"):
                                # Проверяем следующий аргумент
                                if i + 1 < len(game_args) and isinstance(game_args[i + 1], str):
                                    next_arg = game_args[i + 1]
                                    # Если следующий аргумент пустой или равен пустой строке, пропускаем оба
                                    if not next_arg or next_arg.strip() == "":
                                        skip_next = True
                                        continue
                            
                            filtered_game_args.append(arg)
                        
                        game_args = filtered_game_args
                        print(f"[DEBUG] game_args: {game_args}")
                        LogService.log('DEBUG', f"[DEBUG] game_args: {game_args}", source=build)
                        # 6. Запуск Minecraft через MinecraftRunner в отдельном потоке
                        def run_mc():
                            print("[DEBUG] Запуск MinecraftRunner.run")
                            LogService.log('DEBUG', "[DEBUG] Запуск MinecraftRunner.run", source=build)
                            MinecraftRunner.run(
                                java_path=java_path,
                                main_class=main_class,
                                classpath=classpath,
                                natives_dir=str(build_dir / "natives"),
                                game_dir=str(build_dir),
                                assets_dir=str(Path(self.build_manager.config_manager.get('minecraft_path')) / "assets"),
                                assets_index=version_json.get("assetIndex", {}).get("id", ""),
                                username=str(nick),
                                uuid_=offline_uuid,
                                width=854,
                                height=480,
                                extra_jvm_args=jvm_args,
                                extra_game_args=game_args,
                                log_callback=lambda msg: LogService.log('INFO', msg, source=build)
                            )
                        threading.Thread(target=run_mc, daemon=True).start()
                    except Exception as e:
                        LogService.log('ERROR', f'[ERROR] Ошибка запуска: {e}', source=build)
                        print(f'[ERROR] Ошибка запуска: {e}')
                play_btn.clicked.connect(launch_selected_build)
                btns_hbox.addWidget(play_btn)
                # Кнопка Настройки
                settings_btn = QPushButton("Настройки")
                settings_btn.setObjectName("settingsBtn")
                settings_btn.setStyleSheet(
                    "QPushButton#settingsBtn {"
                    "padding: 8px 18px;"
                    "border-radius: 8px;"
                    "background: #3a7dcf;"
                    "color: white;"
                    "font-weight: bold;"
                    "border: none;"
                    "}"
                )
                settings_btn.clicked.connect(lambda _, b=build: print(f'Настройки: {b}'))
                btns_hbox.addWidget(settings_btn)
                btns_hbox.addStretch()
                info_vbox.addLayout(btns_hbox)
                info_vbox.addStretch()
                card_layout.addLayout(info_vbox)
                vbox.addWidget(card)
        vbox.addStretch()
        self.scroll_area.setWidget(content_widget)
        # Очищаем и добавляем scroll_area в my_builds_tab
        layout = self.my_builds_tab.layout() or QVBoxLayout(self.my_builds_tab)
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
        layout.addWidget(self.scroll_area)

    def create_build(self):
        from PySide6.QtCore import QThread
        print('create_build (InstallationsTab) called')
        name = self.name_edit.text().strip()
        mc_version = self.version_combo.currentText()
        loader = self.loader_combo.currentText()
        loader_version = self.loader_ver_combo.currentText() if self.loader_ver_combo.isVisible() else ""
        print(f'mc_version: {mc_version}, loader: {loader}, loader_version: {loader_version}')
        if not name:
            LogService.log('WARNING', 'Укажите название сборки!', source='InstallationsTab')
            return
        if not mc_version:
            LogService.log('WARNING', 'Выберите версию Minecraft!', source='InstallationsTab')
            return
        build_config = {
            "name": name,
            "minecraft_version": mc_version,
            "loader": loader,
            "loader_version": loader_version,
            "notes": ""
        }
        self.build_worker = BuildWorker(self.build_manager, build_config)
        self.build_thread = QThread()
        self.build_worker.moveToThread(self.build_thread)
        self.build_worker.progress.connect(self._on_progress_update)
        # log_msg теперь через LogService.log
        self.build_worker.finished.connect(self._on_build_finished)
        self.build_worker.error.connect(self._on_build_error)
        self.build_thread.started.connect(self.build_worker.run)
        self.build_worker.finished.connect(self.build_thread.quit)
        self.build_worker.error.connect(self.build_thread.quit)
        self.build_thread.finished.connect(self.build_worker.deleteLater)
        self.build_thread.finished.connect(self.build_thread.deleteLater)
        self.build_thread.start()
        self.progress.setVisible(True)
        self.progress.setValue(0)
        from PySide6.QtWidgets import QPushButton
        sender = self.sender()
        if isinstance(sender, QPushButton):
            sender.setEnabled(False)
            sender.setText("Создание сборки...")

    def _on_build_finished(self):
        LogService.log('INFO', "Сборка создана успешно!", source=self.current_build_name or 'InstallationsTab')
        self.progress.setValue(100)
        self.progress.setVisible(False)
        from PySide6.QtWidgets import QPushButton
        sender = self.sender()
        if isinstance(sender, QPushButton):
            sender.setEnabled(True)
            sender.setText("Создать сборку")
        self.update_my_builds()

    def _on_build_error(self, error_message):
        LogService.log('ERROR', f"Ошибка создания сборки: {error_message}", source=self.current_build_name or 'InstallationsTab')
        self.progress.setVisible(False)
        from PySide6.QtWidgets import QPushButton
        sender = self.sender()
        if isinstance(sender, QPushButton):
            sender.setEnabled(True)
            sender.setText("Создать сборку")

    def set_active_tab(self, idx):
        for i, btn in enumerate(self.sidebar_btns):
            btn.setChecked(i == idx)
        self.tabs_content.setCurrentIndex(idx)
