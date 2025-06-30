from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QListWidget, QListWidgetItem, QSizePolicy, QDialog, QDialogButtonBox, QMessageBox, QMenu, QTabWidget, QCheckBox, QScrollArea, QFrame, QGridLayout, QGraphicsDropShadowEffect, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QIcon
import os
import json
import urllib.request

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

class InstallationsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.installed_versions = []
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        # Вкладка "Установлено"
        self.installed_tab = QWidget()
        self.setup_installed_tab()
        self.tabs.addTab(self.installed_tab, "Установлено")
        # Вкладка "Новая установка"
        self.new_tab = QWidget()
        self.setup_new_tab()
        self.tabs.addTab(self.new_tab, "Новая установка")

    def setup_installed_tab(self):
        layout = QVBoxLayout(self.installed_tab)
        self.installed_list = QListWidget()
        for v in self.installed_versions:
            item = QListWidgetItem()
            widget = InstalledVersionWidget(v, parent=self.installed_list)
            widget.remove_requested.connect(self.remove_version)
            item.setSizeHint(widget.sizeHint())
            self.installed_list.addItem(item)
            self.installed_list.setItemWidget(item, widget)
        layout.addWidget(self.installed_list)
        self.installed_list.setStyleSheet("QListWidget::item { border-bottom: 1px solid #eee; }")

    def setup_new_tab(self):
        layout = QVBoxLayout(self.new_tab)
        # Фильтры
        filter_layout = QHBoxLayout()
        self.filter_checkboxes = {}
        for t in VERSION_TYPES:
            cb = QCheckBox(TYPE_LABELS[t])
            cb.setChecked(t == "release")
            cb.stateChanged.connect(self.update_cards)
            self.filter_checkboxes[t] = cb
            filter_layout.addWidget(cb)
        layout.addLayout(filter_layout)
        # Поиск
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по названию...")
        self.search_edit.textChanged.connect(self.update_cards)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        # Прокручиваемая область с карточками
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area)
        self.update_cards()

    def load_official_versions(self):
        try:
            with urllib.request.urlopen(MOJANG_MANIFEST_URL, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            versions = []
            for v in data["versions"]:
                versions.append({
                    "name": v["id"],
                    "type": v["type"],
                    "date": v.get("releaseTime", "")[:10]
                })
            return versions
        except Exception as e:
            print(f"[WARN] Не удалось загрузить список версий Mojang: {e}")
            return []

    def update_cards(self):
        # Определяем активные фильтры
        active_types = [t for t, cb in self.filter_checkboxes.items() if cb.isChecked()]
        if not active_types:
            # Всегда хотя бы один фильтр активен
            self.filter_checkboxes["release"].setChecked(True)
            active_types = ["release"]
        search = self.search_edit.text().lower()
        # Очищаем старые карточки
        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.itemAt(i)
            if item is not None:
                w = item.widget()
                if w:
                    w.setParent(None)
        # Добавляем карточки
        row, col = 0, 0
        for v in self.load_official_versions():
            if v["type"] not in active_types:
                continue
            if search and search not in v["name"].lower():
                continue
            installed = any(inst["name"] == v["name"] for inst in self.installed_versions)
            card = VersionCard(v, installed=installed)
            card.installed_signal.connect(self.on_version_installed)
            self.cards_layout.addWidget(card, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

    def on_version_installed(self, version):
        if not any(v["name"] == version["name"] for v in self.installed_versions):
            self.installed_versions.append({"name": version["name"], "type": version["type"], "status": "Установлено"})
        self.setup_installed_tab()
        self.update_cards()

    def remove_version(self, version):
        self.installed_versions = [v for v in self.installed_versions if v["name"] != version["name"]]
        self.setup_installed_tab()
        self.update_cards() 