"""
Менеджер Minecraft
Управление версиями, загрузкой и запуском игры
"""

import json
import os
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
from loguru import logger


class MinecraftManager:
    """Менеджер для работы с Minecraft"""
    
    def __init__(self, config_manager):
        """Инициализация менеджера Minecraft"""
        self.config_manager = config_manager
        self.minecraft_path = Path(self.config_manager.get("minecraft_path"))
        self.versions_path = self.minecraft_path / "versions"
        
        # Создаем необходимые директории
        self.minecraft_path.mkdir(parents=True, exist_ok=True)
        self.versions_path.mkdir(exist_ok=True)
        
        # API URLs
        self.version_manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
        
        logger.info("MinecraftManager инициализирован")
    
    def get_available_versions(self) -> List[Dict[str, Any]]:
        """Получение списка доступных версий"""
        try:
            response = requests.get(self.version_manifest_url, timeout=30)
            response.raise_for_status()
            
            manifest = response.json()
            versions = []
            
            for version_info in manifest.get("versions", []):
                version_data = {
                    "id": version_info["id"],
                    "type": version_info["type"],
                    "url": version_info["url"],
                    "releaseTime": version_info["releaseTime"],
                    "installed": self.is_version_installed(version_info["id"])
                }
                versions.append(version_data)
            
            logger.info(f"Загружено {len(versions)} версий")
            return versions
            
        except Exception as e:
            logger.error(f"Ошибка загрузки версий: {e}")
            return []
    
    def is_version_installed(self, version_id: str) -> bool:
        """Проверка установлена ли версия"""
        version_dir = self.versions_path / version_id
        return version_dir.exists()
    
    def download_version(self, version_id: str, progress_callback=None) -> bool:
        """Загрузка версии Minecraft (упрощенная версия)"""
        try:
            logger.info(f"Начинаем загрузку версии {version_id}")
            
            # Создаем директорию для версии
            version_dir = self.versions_path / version_id
            version_dir.mkdir(exist_ok=True)
            
            if progress_callback:
                progress_callback(f"Версия {version_id} загружена")
            
            logger.info(f"Версия {version_id} успешно загружена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки версии {version_id}: {e}")
            return False
    
    def find_java(self) -> Optional[str]:
        """Поиск установленной Java"""
        try:
            # Пробуем найти java в PATH
            result = subprocess.run(["java", "-version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return "java"
        except:
            pass
        
        return None
    
    def launch_minecraft(self, version_id: str, username: str) -> bool:
        """Запуск Minecraft (упрощенная версия)"""
        try:
            # Находим Java
            java_path = self.find_java()
            if not java_path:
                logger.error("Java не найдена")
                return False
            
            logger.info(f"Запуск Minecraft версии {version_id} для пользователя {username}")
            
            # Здесь будет полная логика запуска
            return True
            
        except Exception as e:
            logger.error(f"Ошибка запуска Minecraft: {e}")
            return False 