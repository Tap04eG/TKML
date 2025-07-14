"""
Вкладка "Профили" для лаунчера TMKL
Позволяет добавлять, удалять и выбирать оффлайн-профили с аватарками
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QLineEdit, QMessageBox, QInputDialog, QSizePolicy, QDialog, QDialogButtonBox
)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt, QSize
from services.download_service import DownloadService
from services.log_service import LogService

MAX_PROFILES = 8
AVATAR_SIZE = 48


def is_valid_nick(nick: str) -> bool:
    """Проверка валидности ника Minecraft (латиница, цифры, подчёркивание, 3-16 символов)"""
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9_]{3,16}", nick))


def get_avatar_pixmap(nick: str, size: int = AVATAR_SIZE) -> QPixmap:
    """Загружает аватарку с minotar.net, если не удалось — возвращает заглушку"""
    url = f"https://minotar.net/avatar/{nick}/{size}"
    try:
        # Используем DownloadService для загрузки аватара
        download_service = DownloadService()
        response_data = download_service.download_text(url, timeout=3)
        if response_data:
            pixmap = QPixmap()
            pixmap.loadFromData(response_data.encode('utf-8') if isinstance(response_data, str) else response_data)
            return pixmap
    except Exception as e:
        LogService.log('WARNING', f"Не удалось загрузить аватар для {nick}: {e}", source="ProfilesTab")
    # Заглушка: просто пустой серый квадрат
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor("lightgray"))
    return pixmap


class AddProfileDialog(QDialog):
    """Кастомный диалог для добавления профиля с подсветкой поля"""
    def __init__(self, existing_nicks, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить профиль")
        self.setModal(True)
        self.setFixedWidth(350)
        self.nick = None
        self.existing_nicks = set(existing_nicks)
        layout = QVBoxLayout(self)
        self.label = QLabel("Введите ник (3-16 символов, латиница, цифры, _):")
        layout.addWidget(self.label)
        self.line_edit = QLineEdit()
        layout.addWidget(self.line_edit)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.button_box)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.line_edit.textChanged.connect(self.validate_nick)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.validate_nick()
    def validate_nick(self):
        nick = self.line_edit.text().strip()
        if not is_valid_nick(nick):
            self.line_edit.setStyleSheet("background: #ffcccc;")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        elif nick in self.existing_nicks:
            self.line_edit.setStyleSheet("background: #ffcccc;")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            self.line_edit.setStyleSheet("background: #ccffcc;")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
    def accept(self):
        self.nick = self.line_edit.text().strip()
        super().accept()


class ProfilesTab(QWidget):
    """Виджет вкладки профилей"""
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(layout)
        
        # Заголовок
        title = QLabel("Профили игроков")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px 0;")
        layout.addWidget(title)
        
        # Список профилей
        self.profile_list = QListWidget()
        self.profile_list.setIconSize(QSize(AVATAR_SIZE, AVATAR_SIZE))
        self.profile_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.profile_list)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Добавить профиль")
        self.del_btn = QPushButton("Удалить профиль")
        self.set_active_btn = QPushButton("Сделать активным")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.set_active_btn)
        layout.addLayout(btn_layout)
        
        # Сигналы
        self.add_btn.clicked.connect(self.add_profile)
        self.del_btn.clicked.connect(self.delete_profile)
        self.set_active_btn.clicked.connect(self.set_active_profile)
        self.profile_list.itemSelectionChanged.connect(self.update_buttons)
        self.profile_list.itemDoubleClicked.connect(self.activate_profile_by_double_click)
        
        self.refresh_profiles()
        self.update_buttons()

    def refresh_profiles(self):
        """Обновляет список профилей на вкладке"""
        self.profile_list.clear()
        profiles = self.config_manager.profiles.get("profiles", {})
        active = self.config_manager.get_active_profile()
        for nick in profiles:
            item = QListWidgetItem(nick)
            pixmap = get_avatar_pixmap(nick)
            item.setIcon(pixmap)
            if nick == active:
                item.setBackground(QColor("cyan"))
                item.setText(f"{nick} (активен)")
            self.profile_list.addItem(item)
        # Отключаем кнопку добавления, если профилей 8
        self.add_btn.setEnabled(len(profiles) < MAX_PROFILES)

    def add_profile(self):
        """Добавляет новый профиль после проверки"""
        if len(self.config_manager.profiles.get("profiles", {})) >= MAX_PROFILES:
            QMessageBox.warning(self, "Лимит профилей", f"Максимум {MAX_PROFILES} профилей!")
            return
        existing_nicks = self.config_manager.profiles.get("profiles", {}).keys()
        dlg = AddProfileDialog(existing_nicks, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.nick:
            self.config_manager.add_profile(dlg.nick, {"name": dlg.nick})
            self.config_manager.set_active_profile(dlg.nick)
            self.refresh_profiles()

    def delete_profile(self):
        """Удаляет выбранный профиль с подтверждением"""
        item = self.profile_list.currentItem()
        if not item:
            return
        nick = item.text().replace(" (активен)", "")
        active = self.config_manager.get_active_profile()
        if nick == active and len(self.config_manager.profiles.get("profiles", {})) > 1:
            QMessageBox.warning(self, "Удаление профиля", "Нельзя удалить активный профиль. Сначала выберите другой.")
            return
        reply = QMessageBox.question(self, "Удалить профиль", f"Удалить профиль {nick}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.remove_profile(nick)
            # Если удалили активный профиль, сбрасываем активный
            if nick == active:
                self.config_manager.set_active_profile(None)
            self.refresh_profiles()

    def set_active_profile(self):
        """Делает выбранный профиль активным"""
        item = self.profile_list.currentItem()
        if not item:
            return
        nick = item.text().replace(" (активен)", "")
        self.config_manager.set_active_profile(nick)
        self.refresh_profiles()

    def activate_profile_by_double_click(self, item):
        nick = item.text().replace(" (активен)", "")
        self.config_manager.set_active_profile(nick)
        self.refresh_profiles()

    def update_buttons(self):
        """Обновляет состояние кнопок в зависимости от выбора"""
        item = self.profile_list.currentItem()
        profiles = self.config_manager.profiles.get("profiles", {})
        active = self.config_manager.get_active_profile()
        if not item:
            self.del_btn.setEnabled(len(profiles) > 0)
            self.set_active_btn.setEnabled(False)
            return
        nick = item.text().replace(" (активен)", "")
        self.del_btn.setEnabled(True)
        self.set_active_btn.setEnabled(nick != active)

    def get_selected_profile(self):
        """Возвращает данные выбранного профиля (dict) или None"""
        item = self.profile_list.currentItem()
        if not item:
            return None
        nick = item.text().replace(" (активен)", "")
        return self.config_manager.get_profile(nick) 