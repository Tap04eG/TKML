"""
Менеджер конфигурации лаунчера
Управляет настройками и профилями пользователя
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


class ConfigManager:
    """Менеджер конфигурации лаунчера"""
    
    def __init__(self):
        """Инициализация менеджера конфигурации"""
        # Определяем пути к файлам конфигурации
        self.config_dir = Path.home() / ".tmkl"
        self.config_file = self.config_dir / "config.json"
        self.profiles_file = self.config_dir / "profiles.json"
        
        # Создаем директории если не существуют
        self.config_dir.mkdir(exist_ok=True)
        
        # Загружаем конфигурацию
        self.config = self._load_config()
        self.profiles = self._load_profiles()
        
        logger.info("ConfigManager инициализирован")
        
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка основной конфигурации"""
        default_config = {
            "theme": "system",  # system, light, dark
            "language": "ru",
            "minecraft_path": str(Path.home() / ".minecraft"),
            "java_path": "auto",  # auto или путь к Java
            "max_memory": 2048,  # MB
            "min_memory": 512,   # MB
            "window_width": 1200,
            "window_height": 800,
            "auto_update": True,
            "check_servers": True,
            "download_threads": 4,
            "instances_path": "instances",  # Папка для сборок
            "versions_path": "versions",    # Папка для версий
            "libraries_path": "libraries",  # Папка для библиотек
            "assets_path": "assets",        # Папка для ресурсов
            "logs_path": "logs",            # Папка для логов
            "config_path": "config",        # Папка для конфигурации
            "temp_path": "temp"             # Папка для временных файлов
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Обновляем дефолтную конфигурацию загруженными данными
                    default_config.update(loaded_config)
                    logger.info("Конфигурация загружена")
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации: {e}")
        
        return default_config
    
    def _load_profiles(self) -> Dict[str, Any]:
        """Загрузка профилей пользователей"""
        default_profiles = {
            "profiles": {},
            "active_profile": None
        }
        
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    loaded_profiles = json.load(f)
                    default_profiles.update(loaded_profiles)
                    logger.info("Профили загружены")
            except Exception as e:
                logger.error(f"Ошибка загрузки профилей: {e}")
        
        return default_profiles
    
    def save_config(self):
        """Сохранение конфигурации"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info("Конфигурация сохранена")
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
    
    def save_profiles(self):
        """Сохранение профилей"""
        try:
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, indent=2, ensure_ascii=False)
            logger.info("Профили сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения профилей: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получение значения из конфигурации"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Установка значения в конфигурацию"""
        self.config[key] = value
        self.save_config()
    
    def get_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Получение профиля по имени"""
        return self.profiles.get("profiles", {}).get(profile_name)
    
    def add_profile(self, profile_name: str, profile_data: Dict[str, Any]):
        """Добавление нового профиля"""
        if "profiles" not in self.profiles:
            self.profiles["profiles"] = {}
        
        self.profiles["profiles"][profile_name] = profile_data
        self.save_profiles()
        logger.info(f"Профиль {profile_name} добавлен")
    
    def remove_profile(self, profile_name: str):
        """Удаление профиля"""
        if profile_name in self.profiles.get("profiles", {}):
            del self.profiles["profiles"][profile_name]
            self.save_profiles()
            logger.info(f"Профиль {profile_name} удален")
    
    def get_active_profile(self) -> Optional[str]:
        """Получение активного профиля"""
        return self.profiles.get("active_profile")
    
    def set_active_profile(self, profile_name: str):
        """Установка активного профиля"""
        self.profiles["active_profile"] = profile_name
        self.save_profiles()
        logger.info(f"Активный профиль установлен: {profile_name}")
    
    def get_minecraft_path(self) -> Path:
        """Получение пути к папке Minecraft"""
        return Path(self.get("minecraft_path"))
    
    def get_instances_path(self) -> Path:
        """Получение пути к папке сборок"""
        return self.get_minecraft_path() / self.get("instances_path", "instances")
    
    def get_versions_path(self) -> Path:
        """Получение пути к папке версий"""
        return self.get_minecraft_path() / self.get("versions_path", "versions")
    
    def get_libraries_path(self) -> Path:
        """Получение пути к папке библиотек"""
        return self.get_minecraft_path() / self.get("libraries_path", "libraries")
    
    def get_assets_path(self) -> Path:
        """Получение пути к папке ресурсов"""
        return self.get_minecraft_path() / self.get("assets_path", "assets")
    
    def get_logs_path(self) -> Path:
        """Получение пути к папке логов"""
        return self.get_minecraft_path() / self.get("logs_path", "logs")
    
    def get_config_path(self) -> Path:
        """Получение пути к папке конфигурации"""
        return self.get_minecraft_path() / self.get("config_path", "config")
    
    def get_temp_path(self) -> Path:
        """Получение пути к папке временных файлов"""
        return self.get_minecraft_path() / self.get("temp_path", "temp") 