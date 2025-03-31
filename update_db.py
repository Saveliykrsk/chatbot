from app import app, db, User
import os
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text

with app.app_context():
    # Создаем все таблицы, если они не существуют
    try:
        db.create_all()
        print("Таблицы созданы успешно")
    except Exception as e:
        print(f"Ошибка при создании таблиц: {str(e)}")

    # Добавляем новую колонку
    try:
        session = db.session
        session.execute(text("ALTER TABLE user ADD COLUMN plain_password VARCHAR(128)"))
        session.commit()
        print("Колонка plain_password добавлена")
    except Exception as e:
        print(f"Колонка уже существует или ошибка: {str(e)}")
    
    # Обновляем существующие записи
    try:
        users = User.query.all()
        for user in users:
            if user.username == 'admin':
                user.plain_password = 'Rerhbrb2022'
            else:
                user.plain_password = 'default_password'
        
        db.session.commit()
        print("База данных обновлена")
    except Exception as e:
        print(f"Ошибка при обновлении пользователей: {str(e)}")

    try:
        # Добавляем новую колонку image_path
        session.execute(text("ALTER TABLE chat_message ADD COLUMN image_path VARCHAR(255)"))
        session.commit()
        print("Колонка image_path добавлена в таблицу chat_message")
        
    except Exception as e:
        if 'duplicate column name' in str(e).lower():
            print("Колонка image_path уже существует")
        else:
            print(f"Ошибка при обновлении базы данных: {str(e)}")
            
    try:
        # Проверяем существование папки uploads
        if not os.path.exists('static/uploads'):
            os.makedirs('static/uploads')
            print("Создана папка для загрузок static/uploads")
        else:
            print("Папка static/uploads уже существует")
            
    except Exception as e:
        print(f"Ошибка при создании папки: {str(e)}") 