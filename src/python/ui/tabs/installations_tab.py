from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, 
    QListWidget, QListWidgetItem, QSizePolicy, QDialog, QDialogButtonBox, 
    QMessageBox, QMenu, QTabWidget, QCheckBox, QScrollArea, QFrame, QGridLayout, 
    QGraphicsDropShadowEffect, QProgressBar, QButtonGroup, QStackedWidget, QApplication, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QTimer, QObject, QRectF, Slot, QThread, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon, QPainter, QBrush, QColor, QPen, QFont, QGuiApplication
import os
import json
import urllib.request
import threading
from src.python.core.build_manager import BuildManager, BuildStatus
from loguru import logger

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

ICON_PATHS = {
    "release": "src/python/ui/icons/release.svg",
    "snapshot": "src/python/ui/icons/snapshot.svg",
    "beta": "src/python/ui/icons/beta.svg",
    "alpha": "src/python/ui/icons/alpha.svg"
}

MOJANG_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

def get_icon(version_type):
    try:
        if not version_type:
            return QIcon()
            
        path = ICON_PATHS.get(str(version_type))
        if path and os.path.exists(path):
            return QIcon(path)
        return QIcon()  # Пустая иконка-заглушка
    except Exception as e:
        logger.error(f"[UI] Ошибка получения иконки для {version_type}: {e}")
        return QIcon()  # Пустая иконка-заглушка

class VersionCard(QFrame):
    installed_signal = Signal(dict)
    
    def __init__(self, version, installed=False, parent=None):
        super().__init__(parent)
        try:
            if not version or not isinstance(version, dict):
                logger.error(f"[UI] Некорректная версия для VersionCard: {version}")
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
            
            # Иконка версии
            icon = QLabel()
            icon.setPixmap(get_icon(version["type"]).pixmap(48, 48))
            layout.addWidget(icon)
            
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
            logger.exception(f"[UI] Ошибка создания VersionCard: {e}")
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
            logger.error(f"[UI] Ошибка в _on_enter: {e}")

    def _on_leave(self, event):
        try:
            if self._orig_geom:
                self.anim.stop()
                self.anim.setStartValue(self.geometry())
                self.anim.setEndValue(self._orig_geom)
                self.anim.start()
        except Exception as e:
            logger.error(f"[UI] Ошибка в _on_leave: {e}")

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
            logger.error(f"[UI] Ошибка при запуске установки: {e}")

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
            logger.error(f"[UI] Ошибка в _on_progress: {e}")

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
        icon = QLabel()
        icon.setPixmap(get_icon(self.version.get('type', 'release')).pixmap(32, 32))
        title_layout.addWidget(icon)
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
            logger.error(f"[UI] Ошибка отрисовки RoundedPanel: {e}")

class BuildWorker(QObject):
    progress = Signal(int, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, build_manager, build_config):
        super().__init__()
        self.build_manager = build_manager
        self.build_config = build_config
        logger.info(f"[WORKER] BuildWorker создан для сборки: {build_config.get('name', 'Unknown')}")

    def run(self):
        try:
            logger.info(f"[WORKER] Начало выполнения BuildWorker для сборки: {self.build_config.get('name', 'Unknown')}")
            
            def progress_callback(value, text):
                try:
                    # Проверяем, что мы все еще в правильном потоке
                    if not hasattr(self, 'build_config'):
                        logger.error("[WORKER] BuildWorker потерял конфигурацию")
                        return
                        
                    # Обновляем состояние сборки через BuildManager
                    build_name = self.build_config.get('name', '')
                    if not build_name:
                        logger.error("[WORKER] Пустое имя сборки в конфигурации")
                        return
                        
                    # Определяем статус на основе прогресса
                    if value <= 10:
                        status = BuildStatus.DOWNLOADING
                    elif value <= 90:
                        status = BuildStatus.INSTALLING
                    else:
                        status = BuildStatus.READY
                        
                    # Обновляем состояние сборки
                    try:
                        self.build_manager.set_build_state(build_name, status, value, text)
                    except Exception as e:
                        logger.error(f"[WORKER] Ошибка обновления состояния сборки: {e}")
                    
                    # Отправляем сигнал прогресса
                    try:
                        self.progress.emit(value, text)
                    except Exception as e:
                        logger.error(f"[WORKER] Ошибка отправки сигнала прогресса: {e}")
                        
                except Exception as e:
                    logger.error(f"[WORKER] Критическая ошибка в progress_callback: {e}")
            
            logger.info(f"[WORKER] Вызов create_build для: {self.build_config.get('name', 'Unknown')}")
            success = self.build_manager.create_build(self.build_config, progress_callback)
            
            if success is True:
                logger.info(f"[WORKER] Сборка успешно создана: {self.build_config.get('name', 'Unknown')}")
                try:
                    self.finished.emit()
                except Exception as e:
                    logger.error(f"[WORKER] Ошибка отправки сигнала finished: {e}")
            else:
                error_msg = str(success) if success else "Неизвестная ошибка при создании сборки"
                logger.error(f"[WORKER] Ошибка создания сборки: {error_msg}")
                try:
                    self.error.emit(error_msg)
                except Exception as e:
                    logger.error(f"[WORKER] Ошибка отправки сигнала error: {e}")
                
        except Exception as e:
            logger.exception(f"[WORKER] Критическая ошибка в BuildWorker: {e}")
            try:
                self.error.emit(str(e))
            except Exception as emit_error:
                logger.error(f"[WORKER] Ошибка отправки сигнала ошибки: {emit_error}")

class InstallationsTab(QWidget):
    progress_update = Signal(int, str)
    request_update_builds = Signal()
    request_add_build = Signal(dict)
    request_handle_error = Signal(str, str)
    request_remove_build = Signal(dict)
    
    def __init__(self, build_manager, minecraft_manager, parent=None):
        super().__init__(parent)
        self.build_manager = build_manager
        self.minecraft_manager = minecraft_manager
        self.threads = []  # Для хранения активных QThread
        self.build_widgets = {}  # Словарь для хранения виджетов сборок
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
                font-family: 'Rubik';
            }}
            QPushButton {{
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
            }}
            QLineEdit, QComboBox {{
                background: {MC_GRAY};
                border: 2px solid {MC_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                color: {MC_TEXT_LIGHT};
                font-size: 16px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 2px solid {MC_BLUE};
            }}
            QLabel {{
                color: {MC_TEXT};
            }}
            QProgressBar {{
                height: 8px;
                border-radius: 4px;
                background: {MC_GRAY};
                border: 1px solid {MC_BORDER};
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {MC_BLUE}, stop:1 {MC_PURPLE});
                border-radius: 4px;
            }}
        """)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(20)
        
        # Кастомные вкладки-кнопки
        tabs_layout = QHBoxLayout()
        tabs_layout.setSpacing(10)
        self.tab_btns = []
        
        self.btn_my = QPushButton("Мои сборки")
        self.btn_create = QPushButton("Создать сборку")
        self.btn_ready = QPushButton("Готовые сборки")
        
        for btn in [self.btn_my, self.btn_create, self.btn_ready]:
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 17px;
                    padding: 10px 32px;
                    border: 2px solid {MC_BORDER};
                    border-radius: 8px;
                    background: {MC_GRAY};
                    color: {MC_TEXT};
                    font-weight: bold;
                }}
                QPushButton:checked {{
                    border: 2px solid {MC_BLUE};
                    background: rgba(58, 125, 207, 0.2);
                    color: {MC_TEXT_LIGHT};
                }}
            """)
            tabs_layout.addWidget(btn)
            self.tab_btns.append(btn)
        
        tabs_layout.addStretch()
        main_layout.addLayout(tabs_layout)
        
        # Группа кнопок для эксклюзивного выбора
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        for btn in self.tab_btns:
            self.btn_group.addButton(btn)
        
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
        self.btn_my.clicked.connect(lambda: self.tabs_content.setCurrentWidget(self.my_builds_tab))
        self.btn_create.clicked.connect(lambda: self.tabs_content.setCurrentWidget(self.create_tab))
        self.btn_ready.clicked.connect(lambda: self.tabs_content.setCurrentWidget(self.ready_tab))
        self.btn_my.setChecked(True)
        self.tabs_content.setCurrentWidget(self.my_builds_tab)
        
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

        # Кнопка ручного обновления списка
        refresh_btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить список")
        self.btn_refresh.clicked.connect(self.update_my_builds)
        refresh_btn_layout.addWidget(self.btn_refresh)
        refresh_btn_layout.addStretch()
        main_layout.addLayout(refresh_btn_layout)

    def setup_create_tab(self):
        form_outer = QVBoxLayout(self.create_tab)
        form_outer.setContentsMargins(24, 24, 24, 24)
        form_outer.setSpacing(18)
        
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)
        
        # Иконка сборки
        icon = QLabel("Иконка")
        icon_size = 4 * 48 + 3 * 14  # 4 поля по 48px + 3 отступа по 14px
        icon.setFixedSize(icon_size, icon_size)
        icon.setStyleSheet(f"""
            background: {MC_GRAY};
            border: 2.5px solid {MC_BORDER};
            border-radius: 0px;
            font-size: 20px;
            color: {MC_TEXT_MUTED};
            qproperty-alignment: AlignCenter;
        """)
        top_layout.addWidget(icon)
        
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
            
            logger.debug(f"[UI] Обновление прогресса: {value}% - {text}")
            
            # Проверяем, что прогресс-бар доступен
            if not hasattr(self, 'progress') or not self.progress:
                logger.warning("[UI] Прогресс-бар недоступен")
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
                logger.error(f"[UI] Ошибка обновления прогресс-бара: {e}")
                
        except Exception as e:
            logger.exception(f"[UI] Критическая ошибка в _on_progress_update: {e}")

    def update_my_builds(self):
        assert threading.current_thread() == threading.main_thread(), "update_my_builds: UI update not in main thread!"
        """Полное обновление списка сборок"""
        try:
            logger.debug("[UI] Начало обновления списка сборок")
            # Очистить сетку
            for i in reversed(range(self.grid_layout.count())):
                item = self.grid_layout.itemAt(i)
                if item is not None:
                    w = item.widget()
                    if w:
                        w.setParent(None)
                        w.deleteLater()
            
            self.build_widgets.clear()
            
            builds = self.build_manager.get_builds()
            logger.debug(f"[UI] Получено сборок: {len(builds)}")
            
            if not builds:
                no_builds_label = QLabel("У вас пока нет сборок", alignment=Qt.AlignmentFlag.AlignCenter)
                no_builds_label.setStyleSheet(f"color: {MC_TEXT_MUTED}; font-size: 16px; padding: 40px;")
                self.grid_layout.addWidget(no_builds_label, 0, 0)
                return
            
            for build in builds:
                try:
                    if not build or not isinstance(build, dict):
                        logger.warning(f"[UI] Некорректная сборка: {build}")
                        continue
                        
                    build_name = build.get("name")
                    if not build_name:
                        logger.warning(f"[UI] Сборка без имени: {build}")
                        continue
                        
                    widget = InstalledVersionWidget(build)
                    widget.remove_requested.connect(self.remove_build)
                    widget.launch_requested.connect(lambda b=build: self._on_launch_build(b))
                    # Найти свободное место в сетке
                    count = self.grid_layout.count()
                    cols = max(1, self.width() // 340)  # 340px на карточку с отступами
                    row, col = divmod(count, cols)
                    self.grid_layout.addWidget(widget, row, col)
                    self.build_widgets[build_name] = widget
                    logger.debug(f"[UI] Добавлен виджет для сборки: {build_name}")
                    
                except Exception as e:
                    logger.error(f"[UI] Ошибка создания виджета для сборки {build}: {e}")
                    continue
                    
            logger.debug(f"[UI] Обновление списка сборок завершено")
            
        except Exception as e:
            logger.exception("[UI] Критическая ошибка при обновлении списка сборок")
    
    def auto_update_builds(self):
        assert threading.current_thread() == threading.main_thread(), "auto_update_builds: UI update not in main thread!"
        try:
            logger.debug("[UI] Автообновление состояний сборок")
            builds = self.build_manager.get_builds()
            
            for build in builds:
                try:
                    build_name = build.get("name")
                    if not build_name or build_name not in self.build_widgets:
                        continue
                        
                    widget = self.build_widgets[build_name]
                    if widget and not widget.isHidden():
                        widget.update_status(
                            build.get("status", "ready"),
                            build.get("progress", 0),
                            build.get("message", "")
                        )
                        
                except Exception as e:
                    logger.error(f"[UI] Ошибка обновления виджета {build.get('name', 'unknown')}: {e}")
                    continue
                    
        except Exception as e:
            logger.exception("[UI] Критическая ошибка при автообновлении сборок")
    
    def remove_build(self, build):
        assert threading.current_thread() == threading.main_thread(), "remove_build: UI update not in main thread!"
        try:
            if not build or not isinstance(build, dict):
                logger.error(f"[UI] Некорректная сборка для удаления: {build}")
                return
                
            build_name = build.get("name")
            if not build_name:
                logger.error(f"[UI] Сборка без имени для удаления: {build}")
                return
                
            logger.info(f"[UI] Нажата кнопка 'Удалить сборку': {build_name}")
            reply = QMessageBox.question(
                self, 
                "Удалить сборку", 
                f"Удалить сборку {build_name}?", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    if self.build_manager.delete_build(build_name):
                        self.build_manager.clear_build_state(build_name)
                        self.update_my_builds()
                        logger.info(f"[UI] Сборка успешно удалена: {build_name}")
                    else:
                        QMessageBox.warning(self, "Ошибка", f"Не удалось удалить сборку {build_name}")
                        logger.error(f"[UI] Не удалось удалить сборку: {build_name}")
                except Exception as e:
                    logger.error(f"[UI] Ошибка при удалении сборки {build_name}: {e}")
                    QMessageBox.critical(self, "Ошибка", f"Ошибка при удалении сборки: {str(e)}")
                    
        except Exception as e:
            logger.exception(f"[UI] Критическая ошибка при удалении сборки: {e}")

    def create_build(self):
        try:
            logger.info("[UI] Начало создания сборки")
            
            # Проверяем, что все необходимые компоненты доступны
            if not hasattr(self, 'build_manager') or not self.build_manager:
                logger.error("[UI] BuildManager недоступен")
                QMessageBox.critical(self, "Ошибка", "BuildManager недоступен")
                return
                
            if not hasattr(self, 'name_edit') or not self.name_edit:
                logger.error("[UI] Поле имени недоступно")
                QMessageBox.critical(self, "Ошибка", "Поле имени недоступно")
                return
                
            if not hasattr(self, 'version_combo') or not self.version_combo:
                logger.error("[UI] Комбобокс версии недоступен")
                QMessageBox.critical(self, "Ошибка", "Комбобокс версии недоступен")
                return
                
            name = self.name_edit.text().strip()
            mc_version = self.version_combo.currentText()
            loader = self.loader_combo.currentText() if hasattr(self, 'loader_combo') else "Vanilla"
            loader_version = self.loader_ver_combo.currentText() if hasattr(self, 'loader_ver_combo') and self.loader_ver_combo.isVisible() else None
            
            logger.info(f"[UI] Параметры сборки: name={name}, mc_version={mc_version}, loader={loader}, loader_version={loader_version}")
            
            if not name or not mc_version:
                QMessageBox.warning(self, "Ошибка", "Пожалуйста, заполните название и версию Minecraft")
                return
            
            # Проверяем уникальность имени
            try:
                existing_builds = self.build_manager.get_builds()
                existing_names = [build.get("name", "") for build in existing_builds]
                if name in existing_names:
                    QMessageBox.warning(self, "Ошибка", f"Сборка с именем '{name}' уже существует")
                    return
            except Exception as e:
                logger.error(f"[UI] Ошибка проверки существующих сборок: {e}")
                QMessageBox.critical(self, "Ошибка", f"Ошибка проверки существующих сборок: {str(e)}")
                return
            
            build_config = {
                'name': name,
                'minecraft_version': mc_version,
                'loader': loader,
                'loader_version': loader_version
            }
            
            logger.info(f"[UI] Конфигурация сборки создана: {build_config}")
            
            # Создаем временную сборку для отображения в списке
            temp_build = {
                'name': name,
                'minecraft_version': mc_version,
                'loader': loader,
                'status': 'downloading',
                'progress': 0,
                'message': 'Подготовка к созданию...'
            }
            
            # Добавляем временную сборку в список через сигнал
            try:
                self.request_add_build.emit(temp_build)
                logger.debug(f"[UI] Временная сборка добавлена в список: {name}")
            except Exception as e:
                logger.error(f"[UI] Ошибка добавления временной сборки: {e}")
            
            # Создаем и настраиваем worker
            try:
                worker = BuildWorker(self.build_manager, build_config)
                thread = QThread()
                worker.moveToThread(thread)
                
                # Подключаем сигналы
                worker.progress.connect(self._on_progress_update)
                worker.finished.connect(thread.quit)
                worker.finished.connect(worker.deleteLater)
                worker.finished.connect(lambda: self._on_progress_update(0, ""))
                worker.finished.connect(self.request_update_builds.emit)
                worker.error.connect(lambda msg: self._on_progress_update(-1, msg))
                worker.error.connect(lambda msg: self.request_handle_error.emit(name, msg))
                
                thread.started.connect(worker.run)
                thread.finished.connect(thread.deleteLater)
                thread.finished.connect(lambda: self.threads.remove(thread) if thread in self.threads else None)
                
                # Добавляем поток в список и запускаем
                if not hasattr(self, 'threads'):
                    self.threads = []
                self.threads.append(thread)
                
                logger.info(f"[UI] Поток создан и добавлен в список, всего потоков: {len(self.threads)}")
                thread.start()
                
                # Обновляем UI
                if hasattr(self, 'progress'):
                    self.progress.setValue(0)
                    self.progress.setVisible(True)
                    
                logger.info(f"[UI] Создание сборки запущено: {name}")
                
            except Exception as e:
                logger.exception(f"[UI] Ошибка создания потока для сборки: {e}")
                QMessageBox.critical(self, "Ошибка", f"Ошибка создания потока: {str(e)}")
            
        except Exception as e:
            logger.exception("[UI] Критическая ошибка при создании сборки")
            QMessageBox.critical(self, "Ошибка", f"Неожиданная ошибка при создании сборки: {str(e)}")
    
    def closeEvent(self, event):
        """Обработка закрытия вкладки"""
        try:
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
                logger.debug("[UI] Таймер автообновления остановлен")
                
            # Очищаем потоки
            if hasattr(self, 'threads'):
                for thread in self.threads:
                    try:
                        if thread.isRunning():
                            thread.quit()
                            thread.wait(1000)  # Ждем максимум 1 секунду
                    except Exception as e:
                        logger.error(f"[UI] Ошибка при остановке потока: {e}")
                        
            super().closeEvent(event)
            
        except Exception as e:
            logger.exception("[UI] Ошибка при закрытии вкладки")
            super().closeEvent(event)
    
    @Slot(dict)
    def add_build_to_list(self, build):
        assert threading.current_thread() == threading.main_thread(), "add_build_to_list: UI update not in main thread!"
        try:
            if not build or not isinstance(build, dict):
                logger.error(f"[UI] Некорректная сборка для добавления: {build}")
                return
                
            build_name = build.get("name")
            if not build_name:
                logger.error(f"[UI] Сборка без имени: {build}")
                return
                
            logger.info(f"[UI] Добавление сборки в список: {build_name}")
            
            # Проверяем, не существует ли уже виджет для этой сборки
            if build_name in self.build_widgets:
                logger.warning(f"[UI] Виджет для сборки {build_name} уже существует")
                return
            
            widget = InstalledVersionWidget(build)
            widget.remove_requested.connect(lambda b=build: self.request_remove_build.emit(b))
            widget.launch_requested.connect(lambda b=build: self._on_launch_build(b))
            # Найти свободное место в сетке
            count = self.grid_layout.count()
            cols = max(1, self.width() // 340)  # 340px на карточку с отступами
            row, col = divmod(count, cols)
            self.grid_layout.addWidget(widget, row, col)
            self.build_widgets[build_name] = widget
            logger.debug(f"[UI] Виджет добавлен для сборки: {build_name}")
            
        except Exception as e:
            logger.exception(f"[UI] Критическая ошибка при добавлении сборки в список: {e}")
    
    @Slot(str, str)
    def handle_build_error(self, build_name, error_msg):
        assert threading.current_thread() == threading.main_thread(), "handle_build_error: UI update not in main thread!"
        try:
            if not build_name:
                logger.error(f"[UI] Пустое имя сборки в ошибке: {error_msg}")
                return
                
            logger.error(f"[UI] Ошибка создания сборки '{build_name}': {error_msg}")
            QMessageBox.critical(self, "Ошибка создания сборки", f"Не удалось создать сборку '{build_name}': {error_msg}")
            
            # Удаляем временную сборку из списка
            if build_name in self.build_widgets:
                try:
                    widget = self.build_widgets[build_name]
                    if widget:
                        widget.setParent(None)
                        widget.deleteLater()
                    del self.build_widgets[build_name]
                    logger.debug(f"[UI] Временная сборка удалена из списка: {build_name}")
                except Exception as e:
                    logger.error(f"[UI] Ошибка при удалении временной сборки {build_name}: {e}")
                    
        except Exception as e:
            logger.exception(f"[UI] Критическая ошибка при обработке ошибки сборки: {e}")

    def _on_launch_build(self, build):
        name = build.get('name')
        if not name:
            return
        self.build_manager.launch_build(name)
        # Можно добавить обновление статуса/индикатор запуска

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_my_builds()  # Перерисовать сетку при изменении размера окна