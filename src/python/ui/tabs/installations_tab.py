from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QListWidget, QListWidgetItem, QSizePolicy, QDialog, QDialogButtonBox, QMessageBox, QMenu, QTabWidget, QCheckBox, QScrollArea, QFrame, QGridLayout, QGraphicsDropShadowEffect, QProgressBar, QButtonGroup, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QTimer, QObject
from PySide6.QtGui import QIcon
import os
import json
import urllib.request
import threading

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
        self.setStyleSheet("""
            QFrame#VersionCard {
                border: 1px solid #d0d0d0;
                border-radius: 10px;
                background: palette(base);
                margin: 6px;
            }
            QFrame#VersionCard:hover {
                border: 2px solid #2196f3;
                background: #f0f8ff;
            }
        """)
        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(Qt.GlobalColor.gray)
        self.setGraphicsEffect(shadow)
        # Анимация увеличения
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(120)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._orig_geom = None
        self.enterEvent = self._on_enter
        self.leaveEvent = self._on_leave
        layout = QHBoxLayout(self)
        icon = QLabel()
        icon.setPixmap(get_icon(version["type"]).pixmap(48, 48))
        layout.addWidget(icon)
        info = QVBoxLayout()
        name = QLabel(f"<b>{version['name']}</b>")
        vtype = QLabel(TYPE_LABELS.get(version["type"], version["type"]))
        date = QLabel(version.get("date", ""))
        info.addWidget(name)
        info.addWidget(vtype)
        info.addWidget(date)
        layout.addLayout(info)
        layout.addStretch()
        self.install_btn = QPushButton("Установить" if not installed else "Установлено")
        self.install_btn.setEnabled(not installed)
        self.install_btn.clicked.connect(self.start_install)
        layout.addWidget(self.install_btn)
        self.status_label = QLabel("Установлено" if installed else "Не установлено")
        layout.addWidget(self.status_label)
        # Прогресс-бар
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
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
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_progress)
        self.timer.start(30)

    def _on_progress(self):
        val = self.progress.value() + 2
        if val >= 100:
            self.progress.setValue(100)
            self.progress.setVisible(False)
            self.status_label.setText("Установлено")
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
        layout = QHBoxLayout(self)
        icon = QLabel()
        icon.setPixmap(get_icon(version["type"]).pixmap(32, 32))
        layout.addWidget(icon)
        name = QLabel(f"<b>{version['name']}</b> [{TYPE_LABELS.get(version['type'], version['type'])}]")
        layout.addWidget(name)
        self.status = QLabel(version.get("status", "Установлено"))
        layout.addWidget(self.status)
        layout.addStretch()
        self.launch_btn = QPushButton("Запустить")
        self.launch_btn.clicked.connect(self.launch)
        layout.addWidget(self.launch_btn)
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self.delete)
        layout.addWidget(self.delete_btn)
    def launch(self):
        QMessageBox.information(self, "Запуск", f"Запуск версии {self.version['name']}")
    def delete(self):
        reply = QMessageBox.question(self, "Удалить версию", f"Удалить версию {self.version['name']}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.remove_requested.emit(self.version)

class LoaderUpdater(QObject):
    update = Signal(list)

class InstallationsTab(QWidget):
    def __init__(self, minecraft_manager, parent=None):
        super().__init__(parent)
        self.minecraft_manager = minecraft_manager
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.setStyleSheet("background: #f5f5f5; color: #111;")
        # Кастомные вкладки-кнопки
        tabs_layout = QHBoxLayout()
        self.tab_btns = []
        self.btn_my = QPushButton("Мои сборки")
        self.btn_create = QPushButton("Создать сборку")
        self.btn_ready = QPushButton("Готовые сборки")
        for btn in [self.btn_my, self.btn_create, self.btn_ready]:
            btn.setCheckable(True)
            btn.setStyleSheet("font-size: 17px; padding: 10px 32px; border: 2px solid #bbb; border-radius: 8px; background: #fff; color: #222; font-weight: bold;")
            tabs_layout.addWidget(btn)
            self.tab_btns.append(btn)
        tabs_layout.addStretch()
        main_layout.addLayout(tabs_layout)
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        for btn in self.tab_btns:
            self.btn_group.addButton(btn)
        # Контейнер для контента вкладок
        self.tabs_content = QStackedWidget()
        main_layout.addWidget(self.tabs_content)
        # Вкладка 'Мои сборки'
        self.my_builds_tab = QWidget()
        self.tabs_content.addWidget(self.my_builds_tab)
        # Вкладка 'Создать сборку'
        self.create_tab = QWidget()
        form_outer = QVBoxLayout(self.create_tab)
        form_outer.setContentsMargins(24, 24, 24, 24)
        form_outer.setSpacing(18)
        form_outer.setAlignment(Qt.AlignmentFlag.AlignBottom)
        # Darker background for the tab
        self.create_tab.setStyleSheet("background: #23272e;")
        top_layout = QHBoxLayout()
        # Icon: square, height = height of 4 fields
        icon = QLabel("Иконка")
        icon_size = 4 * 48 + 3 * 14  # 4 поля по 48px + 3 отступа по 14px (как fields_layout.setSpacing)
        icon.setFixedSize(icon_size, icon_size)
        icon.setStyleSheet(f"background: #2d313a; border: 2.5px solid #444; border-radius: 24px; font-size: 20px; color: #888; qproperty-alignment: AlignCenter;")
        top_layout.addWidget(icon)
        fields_layout = QVBoxLayout()
        fields_layout.setSpacing(14)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Название сборки")
        self.name_edit.setStyleSheet("font-size: 16px; padding: 10px; border-radius: 12px; border: 2px solid #444; background: #23272e; color: #eee;")
        fields_layout.addWidget(self.name_edit)
        self.version_combo = QComboBox()
        # Получаем все релизные версии через менеджер
        all_versions = self.minecraft_manager.get_available_versions()
        release_versions = [v["id"] for v in all_versions if v["type"] == "release"]
        self.version_combo.addItems(release_versions)
        # --- Кастомный стиль для QComboBox со своей SVG-стрелкой ---
        combo_style = """
        QComboBox {
            background: #23272e;
            border: 2px solid #444;
            border-radius: 12px;
            color: #eee;
            font-size: 16px;
            padding: 10px;
        }
        QComboBox::drop-down {
            border: none;
            background: transparent;
            width: 28px;
        }
        QComboBox::down-arrow {
            image: url(src/python/ui/icons/arrow_down.svg);
            width: 16px;
            height: 16px;
            margin-right: 16px;
            background: transparent;
        }
        QComboBox QAbstractItemView {
            background: #23272e;
            color: #eee;
            border: 2px solid #444;
            selection-background-color: #333a44;
            selection-color: #fff;
            outline: 0;
        }
        QComboBox QAbstractItemView QScrollBar:vertical {
            background: #23272e;
            width: 14px;
            margin: 2px 2px 2px 2px;
            border-radius: 7px;
        }
        QComboBox QAbstractItemView QScrollBar::handle:vertical {
            background: #444;
            min-height: 24px;
            border-radius: 4px;
            margin: 2px 3px 2px 3px;
        }
        QComboBox QAbstractItemView QScrollBar::add-line:vertical,
        QComboBox QAbstractItemView QScrollBar::sub-line:vertical {
            height: 0px;
            background: none;
            border: none;
        }
        QComboBox QAbstractItemView QScrollBar::add-page:vertical,
        QComboBox QAbstractItemView QScrollBar::sub-page:vertical {
            background: none;
        }
        """
        self.version_combo.setStyleSheet(combo_style)
        self.loader_combo = QComboBox()
        self.loader_combo.addItems(["Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"])
        self.loader_combo.setStyleSheet(combo_style)
        self.loader_ver_combo = QComboBox()
        self.loader_ver_combo.addItems(["0.14.21", "0.14.20", "0.14.19"])
        self.loader_ver_combo.setStyleSheet(combo_style)
        fields_layout.addWidget(self.version_combo)
        fields_layout.addWidget(self.loader_combo)
        fields_layout.addWidget(self.loader_ver_combo)
        top_layout.addLayout(fields_layout)
        form_outer.addLayout(top_layout)
        form_outer.addStretch()
        # Button and progress bar at the bottom
        create_btn = QPushButton("Создать сборку")
        create_btn.setStyleSheet("background: #2196F3; color: #fff; font-weight: bold; border-radius: 14px; padding: 16px 0; font-size: 18px;")
        create_btn.setMinimumHeight(48)
        form_outer.addWidget(create_btn)
        progress = QProgressBar()
        progress.setValue(0)
        progress.setStyleSheet("height: 26px; border-radius: 14px; border: 2.5px solid #222; background: #23272e; color: #23272e; font-size: 16px;")
        progress.setTextVisible(False)
        form_outer.addWidget(progress)
        self.tabs_content.addWidget(self.create_tab)
        # Вкладка 'Готовые сборки' (заглушка)
        self.ready_tab = QWidget()
        ready_layout = QVBoxLayout(self.ready_tab)
        ready_layout.addWidget(QLabel("Готовые сборки (скоро)", alignment=Qt.AlignmentFlag.AlignCenter))
        self.tabs_content.addWidget(self.ready_tab)
        # Логика переключения вкладок
        self.btn_my.clicked.connect(lambda: self.tabs_content.setCurrentWidget(self.my_builds_tab))
        self.btn_create.clicked.connect(lambda: self.tabs_content.setCurrentWidget(self.create_tab))
        self.btn_ready.clicked.connect(lambda: self.tabs_content.setCurrentWidget(self.ready_tab))
        self.btn_my.setChecked(True)
        self.tabs_content.setCurrentWidget(self.my_builds_tab)
        # Стилизация активной вкладки
        for btn in self.tab_btns:
            btn.toggled.connect(lambda checked, b=btn: b.setStyleSheet(
                "font-size: 17px; padding: 10px 32px; border: 2px solid #2196F3; border-radius: 8px; background: #e3f2fd; color: #222; font-weight: bold;" if checked else
                "font-size: 17px; padding: 10px 32px; border: 2px solid #bbb; border-radius: 8px; background: #fff; color: #222; font-weight: bold;"
            ))
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