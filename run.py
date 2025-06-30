#!/usr/bin/env python3
"""
Скрипт запуска TMKL - The Minecraft Launcher
"""

import sys
import os
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src" / "python"))

try:
    from src.python.main import main
    main()
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что установлены все зависимости:")
    print("pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"Ошибка запуска: {e}")
    sys.exit(1) 