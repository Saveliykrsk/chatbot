from app import app, db, User

def change_admin_password(new_password):
    with app.app_context():
        # Находим пользователя admin
        admin = User.query.filter_by(username='admin').first()
        
        if admin:
            admin.set_password(new_password)
            db.session.commit()
            print("Пароль администратора успешно изменен")
        else:
            print("Пользователь admin не найден")

if __name__ == '__main__':
    change_admin_password('Rerhbrb2022') 