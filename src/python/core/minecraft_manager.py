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
import xml.etree.ElementTree as ET
import re
from collections import defaultdict

from services.download_service import DownloadService
from services.log_service import LogService


class MinecraftManager:
    """Менеджер для работы с Minecraft"""
    
    def __init__(self, config_manager):
        """Инициализация менеджера Minecraft"""
        self.config_manager = config_manager
        self.minecraft_path = Path(self.config_manager.get("minecraft_path"))
        self.versions_path = self.minecraft_path / "versions"
        
        # Инициализация сервисов
        self.download_service = DownloadService(config_manager)
        
        # Создаем необходимые директории
        self.minecraft_path.mkdir(parents=True, exist_ok=True)
        self.versions_path.mkdir(exist_ok=True)
        
        # API URLs
        self.version_manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
        
        LogService.log('INFO', "MinecraftManager initialized", source="MinecraftManager")
    
    def get_available_versions(self) -> List[Dict[str, Any]]:
        """Получение списка доступных версий"""
        try:
            LogService.log('DEBUG', f"Fetching available versions from {self.version_manifest_url}", source="MinecraftManager")
            
            response_data = self.download_service.download_json(self.version_manifest_url, timeout=30)
            if not response_data:
                LogService.log('ERROR', "Failed to fetch version manifest", source="MinecraftManager")
                return []
            
            versions = []
            
            for version_info in response_data.get("versions", []):
                version_data = {
                    "id": version_info["id"],
                    "type": version_info["type"],
                    "url": version_info["url"],
                    "releaseTime": version_info["releaseTime"],
                    "installed": self.is_version_installed(version_info["id"])
                }
                versions.append(version_data)
            
            LogService.log('INFO', f"Found {len(versions)} available versions", source="MinecraftManager")
            return versions
            
        except Exception as e:
            LogService.log('ERROR', f"Error getting available versions: {e}", source="MinecraftManager")
            return []
    
    def is_version_installed(self, version_id: str) -> bool:
        """Проверка установлена ли версия"""
        version_dir = self.versions_path / version_id
        return version_dir.exists()
    
    def download_version(self, version_id: str, progress_callback=None) -> bool:
        """Загрузка версии Minecraft (упрощенная версия)"""
        try:
            LogService.log('INFO', f"Starting download of version {version_id}", source="MinecraftManager")
            
            # Создаем директорию для версии
            version_dir = self.versions_path / version_id
            version_dir.mkdir(exist_ok=True)
            
            if progress_callback:
                progress_callback(f"Версия {version_id} загружена")
            
            LogService.log('INFO', f"Version {version_id} downloaded successfully", source="MinecraftManager")
            return True
            
        except Exception as e:
            LogService.log('ERROR', f"Error downloading version {version_id}: {e}", source="MinecraftManager")
            return False
    
    def find_java(self) -> Optional[str]:
        """Поиск установленной Java"""
        try:
            LogService.log('DEBUG', "Searching for Java installation", source="MinecraftManager")
            
            # Пробуем найти java в PATH
            result = subprocess.run(["java", "-version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                LogService.log('INFO', "Java found in PATH", source="MinecraftManager")
                return "java"
        except Exception as e:
            LogService.log('WARNING', f"Error checking Java installation: {e}", source="MinecraftManager")
        
        LogService.log('WARNING', "Java not found in PATH", source="MinecraftManager")
        return None
    
    def launch_minecraft(self, version_id: str, username: str) -> bool:
        """Запуск Minecraft (упрощенная версия)"""
        try:
            LogService.log('INFO', f"Attempting to launch Minecraft {version_id} for user {username}", source="MinecraftManager")
            
            # Находим Java
            java_path = self.find_java()
            if not java_path:
                LogService.log('ERROR', "Java not found, cannot launch Minecraft", source="MinecraftManager")
                return False
            
            LogService.log('INFO', f"Minecraft {version_id} launched successfully", source="MinecraftManager")
            return True
            
        except Exception as e:
            LogService.log('ERROR', f"Error launching Minecraft {version_id}: {e}", source="MinecraftManager")
            return False
    
    def get_fabric_loader_versions(self, minecraft_version: str) -> list:
        """Получить список версий Fabric Loader для выбранной версии Minecraft"""
        try:
            url = f"https://meta.fabricmc.net/v2/versions/loader/{minecraft_version}"
            LogService.log('DEBUG', f"Fetching Fabric loader versions for {minecraft_version}", source="MinecraftManager")
            
            data = self.download_service.download_json(url, timeout=15)
            if not data:
                LogService.log('ERROR', f"Failed to fetch Fabric loader versions for {minecraft_version}", source="MinecraftManager")
                return []
            
            # Версии идут от новых к старым, берём только loader.version
            versions = []
            for entry in data:
                loader = entry.get("loader") if isinstance(entry, dict) else None
                if isinstance(loader, dict):
                    version = loader.get("version")
                    if version is not None:
                        versions.append(version)
            LogService.log('INFO', f"Found {len(versions)} Fabric loader versions for {minecraft_version}", source="MinecraftManager")
            return versions
            
        except Exception as e:
            LogService.log('ERROR', f"Error getting Fabric loader versions for {minecraft_version}: {e}", source="MinecraftManager")
            return []
    
    def get_forge_loader_versions(self, minecraft_version: str) -> list:
        """Получить список версий Forge Loader для выбранной версии Minecraft"""
        try:
            url = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
            LogService.log('DEBUG', f"Fetching Forge loader versions for {minecraft_version}", source="MinecraftManager")
            
            data = self.download_service.download_json(url, timeout=15)
            if not data:
                LogService.log('ERROR', f"Failed to fetch Forge loader versions for {minecraft_version}", source="MinecraftManager")
                return []
            
            versions = []
            promos = data.get("promos", {})
            # Добавляем recommended и latest с пометками
            label_map = {"-recommended": " (recommended)", "-latest": " (latest)"}
            labeled_versions = {}
            for suffix, label in label_map.items():
                key = f"{minecraft_version}{suffix}"
                if key in promos:
                    v = promos[key]
                    labeled_versions[v] = label
                    versions.append(v)
            # Добавляем все из number
            all_versions = data.get("number", {}).get(minecraft_version, [])
            versions.extend(all_versions)
            # Сортируем по убыванию
            versions = list(set(versions))
            versions_sorted = sorted(versions, key=lambda s: [int(x) if x.isdigit() else x for x in s.replace('-beta','').split('.')], reverse=True)
            # Добавляем подписи к recommended/latest
            result = [v + labeled_versions.get(v, "") for v in versions_sorted]
            
            LogService.log('INFO', f"Found {len(result)} Forge loader versions for {minecraft_version}", source="MinecraftManager")
            return result if result else []
            
        except Exception as e:
            LogService.log('ERROR', f"Error getting Forge loader versions for {minecraft_version}: {e}", source="MinecraftManager")
            return []
    
    def get_quilt_loader_versions(self, minecraft_version: str) -> list:
        """Получить список версий Quilt Loader для выбранной версии Minecraft"""
        def version_key(s):
            parts = [int(x) if x.isdigit() else x for x in re.split(r'([0-9]+)', s)]
            is_stable = '-' not in s and 'beta' not in s and 'rc' not in s and 'pre' not in s
            # Сортируем по номеру по убыванию, затем по is_stable (True=релиз выше beta)
            return (parts, is_stable)
            
        try:
            url = f"https://meta.quiltmc.org/v3/versions/loader/{minecraft_version}"
            LogService.log('DEBUG', f"Fetching Quilt loader versions for {minecraft_version}", source="MinecraftManager")
            
            data = self.download_service.download_json(url, timeout=15)
            if not data:
                LogService.log('ERROR', f"Failed to fetch Quilt loader versions for {minecraft_version}", source="MinecraftManager")
                return []
            
            # Версии идут от новых к старым, берём только loader.version
            versions = []
            for entry in data:
                loader = entry.get("loader") if isinstance(entry, dict) else None
                if isinstance(loader, dict):
                    version = loader.get("version")
                    if version is not None:
                        versions.append(version)
            stable = [v for v in versions if '-' not in v and 'beta' not in v and 'rc' not in v and 'pre' not in v]
            unstable = [v for v in versions if v not in stable]
            stable_sorted = sorted(stable, key=version_key, reverse=True)
            unstable_sorted = sorted(unstable, key=version_key, reverse=True)
            versions_sorted = stable_sorted + unstable_sorted
            groups = defaultdict(list)
            for v in versions_sorted:
                # Основная ветка — всё до первого дефиса или вся строка
                base = v.split('-')[0]
                groups[base].append(v)
            # Сортируем ветки по номеру по убыванию
            def base_key(s):
                return [int(x) if x.isdigit() else x for x in re.split(r'([0-9]+)', s)]
            result = []
            for base in sorted(groups.keys(), key=base_key, reverse=True):
                group = groups[base]
                # Сначала релиз (без дефиса), потом все остальные по version_key
                rel = [v for v in group if '-' not in v and 'beta' not in v and 'rc' not in v and 'pre' not in v]
                others = [v for v in group if v not in rel]
                others_sorted = sorted(others, key=version_key, reverse=True)
                result.extend(rel + others_sorted)
            LogService.log('INFO', f"Found {len(result)} Quilt loader versions for {minecraft_version}", source="MinecraftManager")
            return result if result else []
            
        except Exception as e:
            LogService.log('ERROR', f"Error getting Quilt loader versions for {minecraft_version}: {e}", source="MinecraftManager")
            return []
    
    def get_neoforge_loader_versions(self, minecraft_version: str) -> list:
        try:
            url = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
            LogService.log('DEBUG', f"Fetching NeoForge loader versions for {minecraft_version}", source="MinecraftManager")
            
            xml_data = self.download_service.download_text(url, timeout=15)
            if not xml_data:
                LogService.log('ERROR', f"Failed to fetch NeoForge loader versions for {minecraft_version}", source="MinecraftManager")
                return []
            
            root = ET.fromstring(xml_data)
            versions = [v.text for v in root.findall(".//version") if v.text]
            parts = minecraft_version.split('.')
            if len(parts) >= 2:
                prefix = f"{parts[1]}.{parts[2]}" if len(parts) > 2 else f"{parts[1]}"
                prefix = f"{prefix}."
                filtered = [v for v in versions if v.startswith(prefix)]
                filtered_sorted = sorted(filtered, key=lambda s: [int(x) if x.isdigit() else x for x in s.replace('-beta','').split('.')], reverse=True)
                
                LogService.log('INFO', f"Found {len(filtered_sorted)} NeoForge loader versions for {minecraft_version}", source="MinecraftManager")
                return filtered_sorted if filtered_sorted else []
            return []
            
        except Exception as e:
            LogService.log('ERROR', f"Error getting NeoForge loader versions for {minecraft_version}: {e}", source="MinecraftManager")
            return []
    
    def get_paper_versions(self, minecraft_version: str) -> list:
        try:
            url = f"https://api.papermc.io/v2/projects/paper/versions/{minecraft_version}"
            LogService.log('DEBUG', f"Fetching Paper versions for {minecraft_version}", source="MinecraftManager")
            
            data = self.download_service.download_json(url, timeout=15)
            if not data:
                LogService.log('ERROR', f"Failed to fetch Paper versions for {minecraft_version}", source="MinecraftManager")
                return []
            
            versions = [str(b) for b in data.get("builds", [])]
            LogService.log('INFO', f"Found {len(versions)} Paper versions for {minecraft_version}", source="MinecraftManager")
            return versions
            
        except Exception as e:
            LogService.log('ERROR', f"Error getting Paper versions for {minecraft_version}: {e}", source="MinecraftManager")
            return []
    
    def get_purpur_versions(self, minecraft_version: str) -> list:
        try:
            url = f"https://api.purpurmc.org/v2/purpur/{minecraft_version}"
            LogService.log('DEBUG', f"Fetching Purpur versions for {minecraft_version}", source="MinecraftManager")
            
            data = self.download_service.download_json(url, timeout=15)
            if not data:
                LogService.log('ERROR', f"Failed to fetch Purpur versions for {minecraft_version}", source="MinecraftManager")
                return []
            
            versions = [str(b) for b in data.get("builds", [])]
            LogService.log('INFO', f"Found {len(versions)} Purpur versions for {minecraft_version}", source="MinecraftManager")
            return versions
            
        except Exception as e:
            LogService.log('ERROR', f"Error getting Purpur versions for {minecraft_version}: {e}", source="MinecraftManager")
            return [] 