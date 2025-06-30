"""
Менеджер тем лаунчера
Управление светлой и темной темой
"""

from PySide6.QtWidgets import QApplication, QPushButton
from loguru import logger
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


class ThemeManager:
    """Менеджер тем лаунчера"""
    
    def __init__(self, config_manager):
        """Инициализация менеджера тем"""
        self.config_manager = config_manager
        self.current_theme = self.config_manager.get("theme", "system")
        self.dark = False
        
    def apply_theme(self, app, dark: bool = False):
        self.dark = dark
        palette = QPalette()
        if dark:
            palette.setColor(QPalette.ColorRole.Window, QColor(40, 40, 40))
            palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Button, QColor(60, 60, 60))
            palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Highlight, QColor(38, 79, 120))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        else:
            palette = app.style().standardPalette()
        app.setPalette(palette)
    
    def toggle_theme(self, app):
        self.apply_theme(app, not self.dark)
    
    def apply_theme_to_app(self):
        """Применение текущей темы"""
        theme = self.config_manager.get("theme", "system")
        
        if theme == "system":
            # Определяем системную тему
            app = QApplication.instance()
            if app and isinstance(app, QApplication):
                theme = "dark" if app.styleHints().colorScheme() == 1 else "light"
        
        if theme == "dark":
            self._apply_dark_theme()
        else:
            self._apply_light_theme()
            
        logger.info(f"Применена тема: {theme}")
    
    def _apply_dark_theme(self):
        """Применение темной темы"""
        app = QApplication.instance()
        if not app or not isinstance(app, QApplication):
            return
            
        # Темная тема
        self.apply_theme(app, True)
    
    def _apply_light_theme(self):
        """Применение светлой темы"""
        app = QApplication.instance()
        if not app or not isinstance(app, QApplication):
            return
            
        # Светлая тема
        self.apply_theme(app, False)
    
    def set_theme(self, theme: str):
        """Установка темы"""
        if theme in ["system", "light", "dark"]:
            self.config_manager.set("theme", theme)
            self.apply_theme_to_app()
            logger.info(f"Тема изменена на: {theme}")
        else:
            logger.warning(f"Неизвестная тема: {theme}")
    
    def get_current_theme(self) -> str:
        """Получение текущей темы"""
        return self.config_manager.get("theme", "system") 