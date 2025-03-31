#!/usr/bin/env python3
# wsgi.py - файл для запуска приложения через WSGI-совместимый сервер

import os
import sys

# Добавляем текущую директорию в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Пытаемся импортировать приложение
    from app import app as application
    print("Приложение успешно импортировано")
except ImportError as e:
    # В случае ошибки импорта выводим подробности
    print(f"Ошибка импорта: {e}")
    print(f"Текущая директория: {os.getcwd()}")
    print("Файлы в директории:")
    for file in os.listdir("."):
        print(f" - {file}")
    sys.exit(1)
except Exception as e:
    # Отлавливаем другие ошибки в приложении
    print(f"Ошибка при запуске приложения: {e}")
    sys.exit(1)

# Если файл запускается напрямую
if __name__ == "__main__":
    print("Запуск приложения...")
    application.run(host="0.0.0.0", port=5000) 