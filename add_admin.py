from app import app, db, User, UserRole

def create_admin(username, password, email):
    with app.app_context():
        # Проверяем существование пользователя
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"Пользователь {username} уже существует")
            return

        # Создаем нового пользователя
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Создаем роль админа
        admin_role = UserRole(user_id=user.id, role='admin')
        db.session.add(admin_role)
        db.session.commit()

        print(f"Администратор {username} успешно создан")

if __name__ == '__main__':
    username = input("Введите имя администратора: ")
    password = input("Введите пароль: ")
    email = input("Введите email: ")
    create_admin(username, password, email) 