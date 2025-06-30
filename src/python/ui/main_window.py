"""
Главное окно лаунчера
Основной интерфейс приложения
"""

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QLabel, QMessageBox
from PySide6.QtCore import Qt
from loguru import logger
from ui.tabs.profiles_tab import ProfilesTab
from ui.tabs.installations_tab import InstallationsTab
from core.minecraft_manager import MinecraftManager


class MainWindow(QMainWindow):
    """Главное окно лаунчера"""
    
    def __init__(self, config_manager, theme_manager):
        """Инициализация главного окна"""
        super().__init__()
        
        self.config_manager = config_manager
        self.theme_manager = theme_manager
        
        # Настройка окна
        self.setWindowTitle("TMKL - The Minecraft Launcher")
        self.setMinimumSize(1000, 700)
        
        # Восстанавливаем размер окна
        width = self.config_manager.get("window_width", 1200)
        height = self.config_manager.get("window_height", 800)
        self.resize(width, height)
        
        # Создание интерфейса
        self.setup_ui()
        
        logger.info("Главное окно инициализировано")
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный layout
        main_layout = QVBoxLayout(central_widget)
        
        # Заголовок + кнопка темы
        header_layout = QHBoxLayout()
        title_label = QLabel("TMKL - The Minecraft Launcher")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; margin: 20px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        self.theme_btn = QPushButton("🌙/☀️")
        self.theme_btn.setFixedSize(36, 36)
        self.theme_btn.setToolTip("Переключить тему")
        header_layout.addWidget(self.theme_btn)
        main_layout.addLayout(header_layout)
        self.theme_btn.clicked.connect(self.toggle_theme)
        
        # Вкладки
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Создаем менеджер Minecraft
        self.minecraft_manager = MinecraftManager(self.config_manager)
        
        # Вкладка установок
        self.installations_tab = InstallationsTab()
        self.tab_widget.addTab(self.installations_tab, "Установки")
        
        # Вкладка профилей (реальная)
        self.profiles_tab = ProfilesTab(self.config_manager)
        self.tab_widget.addTab(self.profiles_tab, "Профили")
        
        # Вкладка настроек (заглушка)
        self.tab_widget.addTab(QLabel("Вкладка настроек"), "Настройки")
        
        # Кнопка запуска
        self.play_button = QPushButton("ИГРАТЬ")
        self.play_button.setMinimumHeight(50)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                margin: 20px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        main_layout.addWidget(self.play_button)
        
        # Сигналы
        self.play_button.clicked.connect(self.on_play_clicked)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Следим за изменениями профилей
        self.profiles_tab.profile_list.itemSelectionChanged.connect(self.update_play_button)
        
        self.update_play_button()

    def update_play_button(self):
        """Включает или выключает кнопку 'ИГРАТЬ' в зависимости от наличия профиля"""
        profiles = self.config_manager.profiles.get("profiles", {})
        active = self.config_manager.get_active_profile()
        enabled = bool(profiles) and active in profiles
        self.play_button.setEnabled(enabled)

    def on_play_clicked(self):
        profiles = self.config_manager.profiles.get("profiles", {})
        active = self.config_manager.get_active_profile()
        if not profiles or not active or active not in profiles:
            # Переключаемся на вкладку профилей
            self.tab_widget.setCurrentIndex(1)  # Индекс вкладки 'Профили' (обновлен)
            QMessageBox.information(self, "Нет профиля", "Создайте профиль для начала игры.")
            return
        
        # Получаем выбранную версию из активной вкладки
        current_tab = self.tab_widget.currentWidget()
        selected_version = None
        
        if hasattr(current_tab, 'get_selected_version'):
            selected_version = current_tab.get_selected_version()
        
        if not selected_version:
            QMessageBox.information(self, "Нет версии", "Выберите версию для запуска.")
            return
        
        # Здесь будет запуск игры
        QMessageBox.information(self, "Запуск", f"Запуск игры за {active} на версии {selected_version['id']}")

    def on_tab_changed(self, idx):
        self.update_play_button()

    def toggle_theme(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        self.theme_manager.toggle_theme(app) 