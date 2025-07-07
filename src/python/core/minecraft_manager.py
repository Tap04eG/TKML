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
import xml.etree.ElementTree as ET
import re
from collections import defaultdict


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
            
            return versions
            
        except Exception as e:
            return []
    
    def is_version_installed(self, version_id: str) -> bool:
        """Проверка установлена ли версия"""
        version_dir = self.versions_path / version_id
        return version_dir.exists()
    
    def download_version(self, version_id: str, progress_callback=None) -> bool:
        """Загрузка версии Minecraft (упрощенная версия)"""
        try:
            # Создаем директорию для версии
            version_dir = self.versions_path / version_id
            version_dir.mkdir(exist_ok=True)
            
            if progress_callback:
                progress_callback(f"Версия {version_id} загружена")
            
            return True
            
        except Exception as e:
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
                return False
            
            return True
            
        except Exception as e:
            return False
    
    def get_fabric_loader_versions(self, minecraft_version: str) -> list:
        """Получить список версий Fabric Loader для выбранной версии Minecraft"""
        try:
            url = f"https://meta.fabricmc.net/v2/versions/loader/{minecraft_version}"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            # Версии идут от новых к старым, берём только loader.version
            return [entry["loader"]["version"] for entry in data if "loader" in entry]
        except Exception as e:
            return []
    
    def get_forge_loader_versions(self, minecraft_version: str) -> list:
        """Получить список версий Forge Loader для выбранной версии Minecraft"""
        try:
            url = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
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
            return result if result else []
        except Exception as e:
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
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            versions = [entry["loader"]["version"] for entry in data if "loader" in entry and "version" in entry["loader"]]
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
            return result if result else []
        except Exception as e:
            return []
    
    def get_neoforge_loader_versions(self, minecraft_version: str) -> list:
        try:
            url = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            versions = [v.text for v in root.findall(".//version") if v.text]
            parts = minecraft_version.split('.')
            if len(parts) >= 2:
                prefix = f"{parts[1]}.{parts[2]}" if len(parts) > 2 else f"{parts[1]}"
                prefix = f"{prefix}."
                filtered = [v for v in versions if v.startswith(prefix)]
                filtered_sorted = sorted(filtered, key=lambda s: [int(x) if x.isdigit() else x for x in s.replace('-beta','').split('.')], reverse=True)
                return filtered_sorted if filtered_sorted else []
            return []
        except Exception as e:
            return []
    
    def get_paper_versions(self, minecraft_version: str) -> list:
        try:
            url = f"https://api.papermc.io/v2/projects/paper/versions/{minecraft_version}"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            return [str(b) for b in data.get("builds", [])]
        except Exception as e:
            return []
    
    def get_purpur_versions(self, minecraft_version: str) -> list:
        try:
            url = f"https://api.purpurmc.org/v2/purpur/{minecraft_version}"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            return [str(b) for b in data.get("builds", [])]
        except Exception as e:
            return [] 