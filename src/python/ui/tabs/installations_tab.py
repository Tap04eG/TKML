from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, 
    QListWidget, QListWidgetItem, QSizePolicy, QDialog, QDialogButtonBox, 
    QMessageBox, QMenu, QTabWidget, QCheckBox, QScrollArea, QFrame, QGridLayout, 
    QGraphicsDropShadowEffect, QProgressBar, QButtonGroup, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QTimer, QObject, QRectF, Slot, QThread
from PySide6.QtGui import QIcon, QPainter, QBrush, QColor, QPen, QFont
import os
import json
import urllib.request
import threading
from src.python.core.build_manager import BuildManager

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
    path = ICON_PATHS.get(version_type)
    if path and os.path.exists(path):
        return QIcon(path)
    return QIcon()  # Пустая иконка-заглушка

class VersionCard(QFrame):
    installed_signal = Signal(dict)
    
    def __init__(self, version, installed=False, parent=None):
        super().__init__(parent)
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

    def _on_enter(self, event):
        if not self._orig_geom:
            self._orig_geom = self.geometry()
        rect = self.geometry().adjusted(-6, -6, 6, 6)
        self.anim.stop()
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(rect)
        self.anim.start()

    def _on_leave(self, event):
        if self._orig_geom:
            self.anim.stop()
            self.anim.setStartValue(self.geometry())
            self.anim.setEndValue(self._orig_geom)
            self.anim.start()

    def start_install(self):
        self.install_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_label.setText("Установка...")
        self.status_label.setStyleSheet(f"color: {MC_BLUE};")
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_progress)
        self.timer.start(30)

    def _on_progress(self):
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

class InstalledVersionWidget(QWidget):
    remove_requested = Signal(dict)
    
    def __init__(self, version, parent=None):
        super().__init__(parent)
        self.version = version
        
        # Основной стиль виджета
        self.setStyleSheet(f"""
            QWidget {{
                background: {MC_GRAY};
                border-radius: 12px;
                border: 1px solid {MC_BORDER};
                padding: 8px;
            }}
            QLabel {{
                color: {MC_TEXT};
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 14px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Иконка версии
        icon = QLabel()
        icon.setPixmap(get_icon(version["type"]).pixmap(32, 32))
        layout.addWidget(icon)
        
        # Название и тип версии
        name = QLabel(f"<b>{version['name']}</b> [{TYPE_LABELS.get(version['type'], version['type'])}]")
        name.setStyleSheet(f"font-size: 14px; color: {MC_TEXT_LIGHT};")
        layout.addWidget(name)
        
        layout.addStretch()
        
        # Статус
        self.status = QLabel(version.get("status", "Установлено"))
        self.status.setStyleSheet(f"font-size: 13px; color: {MC_GREEN};")
        layout.addWidget(self.status)
        
        # Кнопка запуска
        self.launch_btn = QPushButton("Запустить")
        self.launch_btn.setStyleSheet(f"""
            QPushButton {{
                background: {MC_GREEN};
                color: white;
            }}
            QPushButton:hover {{
                background: {MC_DARK_GREEN};
            }}
        """)
        self.launch_btn.clicked.connect(self.launch)
        layout.addWidget(self.launch_btn)
        
        # Кнопка удаления
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: {MC_RED};
                color: white;
            }}
            QPushButton:hover {{
                background: #c82333;
            }}
        """)
        self.delete_btn.clicked.connect(self.delete)
        layout.addWidget(self.delete_btn)
    
    def launch(self):
        QMessageBox.information(self, "Запуск", f"Запуск версии {self.version['name']}")
    
    def delete(self):
        reply = QMessageBox.question(
            self, 
            "Удалить версию", 
            f"Удалить версию {self.version['name']}?", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        rect.adjust(self.border_width/2, self.border_width/2, -self.border_width/2, -self.border_width/2)
        
        # Рисуем фон с прозрачностью
        painter.setBrush(QBrush(QColor(self.bg_color.red(), self.bg_color.green(), self.bg_color.blue(), 200)))
        painter.setPen(QPen(self.border_color, self.border_width))
        painter.drawRoundedRect(rect, self.radius, self.radius)

class BuildWorker(QObject):
    progress = Signal(int, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, build_manager, build_config):
        super().__init__()
        self.build_manager = build_manager
        self.build_config = build_config

    def run(self):
        def progress_callback(value, text):
            print(f"PROGRESS: {value} {text}")
            self.progress.emit(value, text)
        try:
            self.build_manager.create_build(self.build_config, progress_callback)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class InstallationsTab(QWidget):
    progress_update = Signal(int, str)
    
    def __init__(self, build_manager, minecraft_manager, parent=None):
        super().__init__(parent)
        self.build_manager = build_manager
        self.minecraft_manager = minecraft_manager
        self.threads = []  # Для хранения активных QThread
        self.setup_ui()
        self.update_my_builds()
        
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
        
        # Вкладка 'Мои сборки'
        self.my_builds_tab = RoundedPanel()
        my_builds_layout = QVBoxLayout(self.my_builds_tab)
        my_builds_layout.addWidget(QLabel("Здесь будут отображаться ваши сборки", alignment=Qt.AlignmentFlag.AlignCenter))
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
        if value < 0:
            self.progress.setValue(0)
            self.progress.setVisible(False)
        else:
            self.progress.setValue(value)
            self.progress.setVisible(True)

    def update_my_builds(self):
        layout = self.my_builds_tab.layout() or QVBoxLayout(self.my_builds_tab)
        # Очистить layout
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
        builds = self.build_manager.get_builds()
        if not builds:
            layout.addWidget(QLabel("У вас пока нет сборок", alignment=Qt.AlignmentFlag.AlignCenter))
            return
        for build in builds:
            widget = InstalledVersionWidget(build)
            layout.addWidget(widget)

    def create_build(self):
        name = self.name_edit.text().strip()
        mc_version = self.version_combo.currentText()
        loader = self.loader_combo.currentText()
        loader_version = self.loader_ver_combo.currentText() if self.loader_ver_combo.isVisible() else None
        build_config = {
            'name': name,
            'minecraft_version': mc_version,
            'loader': loader,
            'loader_version': loader_version
        }
        worker = BuildWorker(self.build_manager, build_config)
        thread = QThread()
        worker.moveToThread(thread)
        worker.progress.connect(self._on_progress_update)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: self._on_progress_update(0, ""))
        worker.finished.connect(self.update_my_builds)  # Обновляем список сборок после создания
        worker.error.connect(lambda msg: self._on_progress_update(-1, msg))
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self.threads.remove(thread))
        self.threads.append(thread)
        thread.start()
        self.progress.setValue(0)
        self.progress.setVisible(True)