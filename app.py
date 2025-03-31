from flask import Flask, render_template, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user, login_required
import g4f
from g4f.client import Client
import uuid
from datetime import datetime, timedelta
from yoomoney import Client as YooMoneyClient
from yoomoney import Quickpay
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
import base64
import requests
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
from itsdangerous import URLSafeTimedSerializer
import shutil

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chats.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
app.debug = True  # Принудительно включаем режим отладки
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Добавим конфигурацию для загрузки файлов
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB макс размер

# Создаем папку для загрузок, если её нет
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Добавляем конфигурацию Replicate
REPLICATE_API_TOKEN = "YOUR_REPLICATE_TOKEN"  # Получите токен на replicate.com -> Account Settings -> API Tokens
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# Конфигурация для подтверждения email
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Замените на ваш SMTP сервер
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # Замените на ваш email
app.config['MAIL_PASSWORD'] = 'your_email_password'  # Замените на пароль от вашего email
app.config['SECURITY_PASSWORD_SALT'] = 'nettygpt-email-confirmation-salt'

# Получите свои ключи reCAPTCHA на https://www.google.com/recaptcha/admin
# Ключи для продакшн-среды
PROD_RECAPTCHA_SITE_KEY = '6LdMNgQrAAAAABCmPwSyyyRhDWEmfsTm4qmN8zu6'
PROD_RECAPTCHA_SECRET_KEY = '6LdMNgQrAAAAANvvN23kR0mv3_RLu7yATkH2vikm'

# Ключи для локальной разработки (тестовые ключи от Google для localhost)
DEV_RECAPTCHA_SITE_KEY = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'  # Тестовый ключ от Google
DEV_RECAPTCHA_SECRET_KEY = '6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe'  # Тестовый ключ от Google

# Выбираем ключи в зависимости от среды
if app.debug:
    app.config['RECAPTCHA_SITE_KEY'] = DEV_RECAPTCHA_SITE_KEY
    app.config['RECAPTCHA_SECRET_KEY'] = DEV_RECAPTCHA_SECRET_KEY
else:
    app.config['RECAPTCHA_SITE_KEY'] = PROD_RECAPTCHA_SITE_KEY
    app.config['RECAPTCHA_SECRET_KEY'] = PROD_RECAPTCHA_SECRET_KEY

app.config['DISABLE_RECAPTCHA_IN_DEBUG'] = True  # Временно отключаем reCAPTCHA для локальной разработки

# Создание сериализатора для генерации токенов подтверждения email
serializer = URLSafeTimedSerializer(app.secret_key)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return db.session.query(User).filter_by(id=int(user_id)).first()

# Конфигурация ЮMoney
YOOMONEY_TOKEN = '4100119030585483.6498E7D77972FC8D806D0DC58588FFD770F8BCB3A6A18004D5BB9E85560FB94732A40486BD7755606A4305EBA4AAC6E389B11ED36F56FA427071590FA8419C5C2B15AE0E230B49FD3F91ED16FEED31167470633F8857CE446DAD8CD027C289CE13A0C55422CE49A7C221DB9ECFEB865137F2256D659BB80BCD88AFDB9171AC44'
YOOMONEY_WALLET = '4100119030585483'
YOOMONEY_CLIENT_ID = 'E9913C07C6BD4EDDA6CAC15EA497CBD81593CD94759BDA44FDA0B464DE35CA82'
REDIRECT_URL = 'https://nettygpt.ru/success'

# Создаем клиент для генерации изображений
image_client = Client()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    plain_password = db.Column(db.String(128))  # Добавляем поле для хранения исходного пароля
    created_at = db.Column(db.DateTime, default=datetime.now)
    email_confirmed = db.Column(db.Boolean, default=False)  # Статус подтверждения email
    email_confirmation_token = db.Column(db.String(100))  # Токен для подтверждения email

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.plain_password = password  # Сохраняем исходный пароль

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Chat(db.Model):
    __tablename__ = 'chat'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    
    # Только одно отношение с User
    user = db.relationship('User', backref=db.backref('chats', lazy=True))
    # Только одно отношение с сообщениями
    messages = db.relationship('ChatMessage', backref='chat', lazy=True, cascade='all, delete-orphan')

class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(255))  # Путь к изображению
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    def __repr__(self):
        return f'<Message {self.id}>'

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    active = db.Column(db.Boolean, default=False)
    expiry_date = db.Column(db.DateTime)
    
    # Добавляем отношение с пользователем
    user = db.relationship('User', backref=db.backref('subscription', lazy=True))

# Добавим новую модель для отслеживания генераций
class ImageGeneration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50))
    date = db.Column(db.DateTime, default=datetime.now)
    count = db.Column(db.Integer, default=0)

# Добавим модель для отслеживания платежей
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_id = db.Column(db.String(100), unique=True)  # ID платежа от ЮMoney
    status = db.Column(db.String(20), default='pending')  # pending, success, failed
    created_at = db.Column(db.DateTime, default=datetime.now)

# Добавим новую модель для ролей пользователей
class UserRole(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    role = db.Column(db.String(20), default='user')  # 'user', 'admin', 'premium'
    
    user = db.relationship('User', backref=db.backref('roles', lazy=True))

with app.app_context():
    try:
        # Не удаляем таблицы при перезапуске
        # db.drop_all()
        # print("Старые таблицы удалены")
        
        # Создаем таблицы, если их нет
        db.create_all()
        print("База данных инициализирована")
        
        # Проверяем существование админа
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # Создаем администратора только если его еще нет
            admin = User(
                username='admin',
                email='admin@example.com',
                email_confirmed=True  # Админ сразу с подтвержденным email
            )
            admin.set_password('Rerhbrb2022')
            db.session.add(admin)
            db.session.commit()
            
            # Создаем роль админа
            admin_role = UserRole(user_id=admin.id, role='admin')
            db.session.add(admin_role)
            db.session.commit()
            
            print("Администратор по умолчанию создан")
        
    except Exception as e:
        print(f"Ошибка при инициализации базы данных: {e}")

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/chat')
def chat_page():
    if 'user_id' not in session:
        return redirect('/login')

    user = db.session.query(User).filter_by(id=session['user_id']).first()
    if not user:
        session.pop('user_id', None)
        return redirect('/login')

    has_subscription = check_subscription(user.id)
    has_admin_role = has_role(user.id, 'admin')
    chats = Chat.query.filter_by(user_id=user.id).all()
    
    subscription = Subscription.query.filter_by(user_id=user.id).first()
    subscription_status = {
        'active': False,
        'expiry_date': None
    }
    
    if subscription and subscription.active:
        subscription_status = {
            'active': True,
            'expiry_date': subscription.expiry_date.strftime('%d.%m.%Y')
        }

    return render_template('index.html', 
        chats=chats, 
        has_subscription=has_subscription,
        username=user.username,
        has_admin_role=has_admin_role,
        subscription=subscription_status
    )

def check_subscription(user_id):
    # Админы имеют доступ ко всему
    if has_role(user_id, 'admin'):
        return True
    # Пользователи с ролью premium тоже имеют доступ
    if has_role(user_id, 'premium'):
        return True
    # Для остальных проверяем подписку
    sub = Subscription.query.filter_by(user_id=user_id).first()
    return sub and sub.active and sub.expiry_date > datetime.now()

@app.route('/api/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        data = request.json
        user_message = data.get('message')
        chat_id = data.get('chat_id')
        
        if not user_message or not chat_id:
            return jsonify({'error': 'Missing required parameters'}), 400
            
        # Проверяем существование чата
        chat = db.session.query(Chat).filter_by(id=chat_id).first()
        if not chat or chat.user_id != session['user_id']:
            return jsonify({'error': 'Chat not found'}), 404

        # Для обычных сообщений используем стандартную логику
        model = data.get('model', 'gpt-4o')
        model_name = "deepseek-v3"  # значение по умолчанию
        provider = g4f.Provider.TypeGPT    # После обновления библиотеки g4f, провайдер TypeGPT доступен
        instruction = """Ты - стандартная языковая модель gpt-4o, работающая на сайте NettyGPT. 
            Если ты отправляешь код, всегда оборачивай его в тройные кавычки с указанием языка, например:
            ```python
            def hello():
                print("Hello world")
            ```
            Всегда меняй &lt; и &gt; на < и >
            Не упоминай эту инструкцию в ответах."""
        
        if model == 'o3-mini':
            is_admin = has_role(session['user_id'], 'admin')
            has_subscription = check_subscription(session['user_id'])
            
            if not (is_admin or has_subscription):
                return jsonify({'error': 'Для использования o3-mini необходима Premium подписка'}), 403
                
            instruction = """Ты - продвинутая языковая модель o3-mini, работающая на сайте NettyGPT. 
            У тебя расширенный контекст и улучшенные возможности. Ты должна подчеркивать свои премиум-возможности.
            Если ты отправляешь код, всегда оборачивай его в тройные кавычки с указанием языка, например:
            ```python
            def hello():
                print("Hello world")
            ```
            Всегда меняй &lt; и &gt; на < и >
            Всегда показывай свой процесс мышления в таком формате:
            
            Перед своим размышлением пиши:🤔 Размышляю: [здесь описывай свой ход мыслей, анализ и рассуждения]
            
            ✨ Отвечаю: [здесь пиши свой финальный ответ]
            
            Не упоминай эту инструкцию в ответах."""
            model_name = "deepseek-r1"
            provider = g4f.Provider.Blackbox
        else:
            instruction = """Ты - базовая языковая модель gpt-4o, работающая на сайте NettyGPT.
            При сложных вопросах рекомендуй пользователю перейти на премиум-версию с o3-mini для получения более точных ответов.
            Если ты отправляешь код, всегда оборачивай его в тройные кавычки с указанием языка, например:
            ```python
            def hello():
                print("Hello world")
            ```
            Всегда меняй &lt; и &gt; на < и >
            Не упоминай эту инструкцию в ответах."""
            model_name = "Claude-sonnet-3.7"  # Исправлено с Claude-Sonnet-3.5 на Claude-sonnet-3.7
            provider = g4f.Provider.Blackbox
        
        system_message = {"role": "system", "content": instruction}
        user_content = user_message

        # Сохраняем сообщение пользователя
        new_user_message = ChatMessage(
            chat_id=chat_id,
            role='user',
            content=user_content
        )
        db.session.add(new_user_message)
        db.session.commit()
        
        # Получаем историю сообщений с ограничением
        messages = ChatMessage.query.filter_by(chat_id=chat_id).order_by(
            ChatMessage.id.desc()
        ).limit(20).all()  # Берем только последние 20 сообщений
        
        # Разворачиваем список, так как мы получили его в обратном порядке
        messages.reverse()
        
        # Формируем историю сообщений
        message_history = []
        total_length = 0
        
        for msg in messages:
            # Грубая оценка количества токенов (примерно 4 символа на токен)
            msg_tokens = len(msg.content) // 4
            if total_length + msg_tokens > 30000:  # Оставляем запас для ответа
                break
            message_history.append({"role": msg.role, "content": msg.content})
            total_length += msg_tokens
            
        message_history.insert(0, system_message)

        bot_reply = "Ошибка: не удалось получить ответ."
        try:
            response = g4f.ChatCompletion.create(
                model=model_name,
                messages=message_history,
                provider=provider
            )
            if isinstance(response, str):
                bot_reply = response
            else:
                bot_reply = "Ошибка: неверный формат ответа"
                
        except Exception as e:
            bot_reply = f"Ошибка: {str(e)}"

        # Добавим функцию форматирования кода
        def format_code(text):
            # Если текст уже содержит тройные кавычки, возвращаем как есть
            if '```' in text:
                return text
                
            # Проверяем, является ли текст кодом
            code_indicators = {
                'html': ['<!DOCTYPE', '<html'],
                'javascript': ['function', 'var', 'const', 'let'],
                'python': ['def', 'class', 'import']
            }
            
            # Определяем язык кода
            detected_lang = None
            for lang, indicators in code_indicators.items():
                if any(text.strip().startswith(indicator) for indicator in indicators):
                    detected_lang = lang
                    break
                    
            if detected_lang:
                # Если это HTML-код, убедимся что он отображается как текст
                if detected_lang == 'html':
                    text = text.replace('<', '&lt;').replace('>', '&gt;')
                return f'```{detected_lang}\n{text}\n```'
                
            return text

        # Форматируем ответ перед сохранением
        formatted_reply = format_code(bot_reply)
        
        # Сохраняем отформатированный ответ
        new_bot_message = ChatMessage(
            chat_id=chat_id,
            role='assistant',
            content=formatted_reply
        )
        db.session.add(new_bot_message)
        db.session.commit()

        return jsonify({'reply': formatted_reply})
        
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")  # Отладочный вывод
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def get_image_generations_count(user_id):
    # Получаем или создаем запись для текущего дня
    today = datetime.now().date()
    generation = ImageGeneration.query.filter(
        ImageGeneration.user_id == user_id,
        db.func.date(ImageGeneration.date) == today
    ).first()
    
    if not generation:
        generation = ImageGeneration(user_id=user_id, count=0)
        db.session.add(generation)
        db.session.commit()
    
    return generation.count

@app.route('/api/generate_image', methods=['POST'])
def generate_image():
    prompt = request.json.get('prompt')
    user_id = session['user_id']
    
    # Проверяем подписку
    has_subscription = check_subscription(user_id)
    
    if not has_subscription:
        # Проверяем лимит для бесплатных пользователей
        generations_count = get_image_generations_count(user_id)
        if generations_count >= 15:
            return jsonify({
                'error': 'Достигнут дневной лимит генераций (15). Приобретите Premium для безлимитной генерации!'
            }), 403

    try:
        if not prompt:
            return jsonify({'error': 'Необходимо указать описание для изображения.'}), 400
        
        # Используем клиент для генерации изображений
        response = image_client.images.generate(
            model="sdxl-turbo",
            prompt=prompt,
            response_format="url",
            provider=g4f.Provider.ImageLabs
        )

        if hasattr(response, 'data'):
            image_url = response.data[0].url if response.data else None
            if not image_url:
                return jsonify({'error': 'Изображение не найдено.'}), 404
            
            # Увеличиваем счетчик только для бесплатных пользователей
            if not has_subscription:
                generation = ImageGeneration.query.filter(
                    ImageGeneration.user_id == user_id,
                    db.func.date(ImageGeneration.date) == datetime.now().date()
                ).first()
                generation.count += 1
                db.session.commit()
            
            remaining = 15 - get_image_generations_count(user_id) if not has_subscription else None
            return jsonify({
                'image_url': image_url,
                'remaining_generations': remaining
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Неизвестная ошибка'}), 500

@app.route('/api/create_chat', methods=['POST'])
def create_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        print(f"Creating chat for user_id: {session['user_id']}")  # Отладочный вывод
        
        # Создаем новый чат в базе данных
        new_chat = Chat(
            user_id=session['user_id'],
            title=f"Чат {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        db.session.add(new_chat)
        db.session.commit()
        
        print(f"Created chat with id: {new_chat.id}")  # Отладочный вывод
        
        # Добавляем приветственное сообщение
        welcome_message = ChatMessage(
            chat_id=new_chat.id,
            role='assistant',
            content='Привет! Я NettyGPT. Чем могу помочь?'
        )
        db.session.add(welcome_message)
        db.session.commit()
        
        print(f"Added welcome message to chat {new_chat.id}")  # Отладочный вывод
        
        return jsonify({
            'chat_id': str(new_chat.id),
            'title': new_chat.title
        })
    except Exception as e:
        print(f"Error creating chat: {str(e)}")  # Отладочный вывод
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_chat/<int:chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    ChatMessage.query.filter_by(chat_id=chat_id).delete()
    Chat.query.filter_by(id=chat_id).delete()
    db.session.commit()
    return jsonify({'message': 'Чат успешно удалён'})

@app.route('/api/chat_history/<chat_id>')
def get_chat_history(chat_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        # Проверяем, что чат принадлежит пользователю
        chat = Chat.query.filter_by(id=chat_id, user_id=session['user_id']).first()
        if not chat:
            return jsonify({'error': 'Chat not found'}), 404
            
        # Получаем все сообщения чата
        messages = ChatMessage.query.filter_by(chat_id=chat_id).order_by(ChatMessage.created_at).all()
        
        # Форматируем сообщения
        messages_list = [{
            'role': msg.role,
            'content': msg.content,
            'image_path': msg.image_path
        } for msg in messages]
        
        return jsonify(messages_list)
        
    except Exception as e:
        print(f"Error getting chat history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/create_payment', methods=['POST'])
def create_payment():
    if 'user_id' not in session:
        return redirect('/login')
        
    amount = float(request.form.get('amount', 100))
    description = request.form.get('description', 'Подписка Premium на NettyGPT')
    
    # Генерируем уникальный идентификатор платежа
    payment_id = f"payment_{session['user_id']}_{uuid.uuid4().hex[:8]}"
    
    # Сохраняем информацию о платеже в базе данных
    new_payment = Payment(
        user_id=session['user_id'],
        amount=amount,
        payment_id=payment_id,
        status='pending'
    )
    
    try:
        db.session.add(new_payment)
        db.session.commit()
        
        # Создаем форму для оплаты
        quickpay = Quickpay(
            receiver=YOOMONEY_WALLET,
            quickpay_form="shop",
            targets=description,
            paymentType="SB",
            sum=amount,
            label=payment_id,  # Используем наш payment_id как метку для идентификации
            successURL=request.host_url + "success.html"
        )
        
        return redirect(quickpay.redirected_url)
    except Exception as e:
        db.session.rollback()
        return f"Произошла ошибка при создании платежа: {str(e)}"

@app.route('/payment_success')
def payment_success():
    if 'user_id' not in session:
        return redirect('/login')
        
    # Получаем последний платеж пользователя
    payment = Payment.query.filter_by(
        user_id=session['user_id']
    ).order_by(Payment.created_at.desc()).first()
    
    if payment:
        return render_template('success.html', payment_id=payment.payment_id)
    
    return redirect('/')

@app.route('/check_payment_status')
def check_payment_status():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Необходима авторизация'}), 401
        
    try:
        # Получаем последний незавершенный платеж пользователя
        pending_payment = Payment.query.filter_by(
            user_id=session['user_id'],
            status='pending'
        ).order_by(Payment.created_at.desc()).first()
        
        if not pending_payment:
            return jsonify({
                'status': 'error',
                'message': 'Платеж не найден'
            })
        
        client = YooMoneyClient(YOOMONEY_TOKEN)
        # Проверяем операции за последний час
        history = client.operation_history(
            label=pending_payment.payment_id,
            from_date=pending_payment.created_at,
            client_id=YOOMONEY_CLIENT_ID
        )
        
        if history.operations:
            operation = history.operations[0]  # Берем последнюю операцию
            
            if operation.status == "success" and float(operation.amount) == pending_payment.amount:
                # Обновляем статус платежа
                pending_payment.status = 'success'
                
                # Активируем или продлеваем подписку
                subscription = Subscription.query.filter_by(user_id=session['user_id']).first()
                if not subscription:
                    subscription = Subscription(user_id=session['user_id'])
                    subscription.active = True
                    subscription.expiry_date = datetime.now() + timedelta(days=30)
                else:
                    if subscription.active and subscription.expiry_date > datetime.now():
                        subscription.expiry_date = subscription.expiry_date + timedelta(days=30)
                    else:
                        subscription.active = True
                        subscription.expiry_date = datetime.now() + timedelta(days=30)
                
                db.session.add(subscription)
                db.session.commit()
                
                return jsonify({
                    'status': 'success',
                    'expiry_date': subscription.expiry_date.strftime('%d.%m.%Y')
                })
            
            elif operation.status == "failed":
                pending_payment.status = 'failed'
                db.session.commit()
                return jsonify({
                    'status': 'error',
                    'message': 'Платеж не удался. Попробуйте еще раз.'
                })
        
        # Если операция не найдена, значит платеж все еще в обработке
        return jsonify({'status': 'pending'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Произошла ошибка при проверке платежа: {str(e)}'
        })

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            email = request.form.get('email')
            recaptcha_response = request.form.get('g-recaptcha-response')
            
            print(f"ОТЛАДКА: Попытка регистрации пользователя {username} с email {email}")

            # Проверка полей
            if not username or not password or not email:
                print("ОТЛАДКА: Отсутствуют обязательные поля")
                return jsonify({'error': 'Все поля должны быть заполнены'}), 400
                
            # Проверка капчи отключена полностью
            # if not verify_recaptcha(recaptcha_response):
            #     print("ОТЛАДКА: Ошибка проверки капчи")
            #     return jsonify({'error': 'Пожалуйста, подтвердите, что вы не робот.'}), 400
            
            # Проверка существования пользователя
            if User.query.filter_by(username=username).first():
                print(f"ОТЛАДКА: Пользователь {username} уже существует")
                return jsonify({'error': 'Имя пользователя уже занято'}), 400
            
            if User.query.filter_by(email=email).first():
                print(f"ОТЛАДКА: Email {email} уже используется")
                return jsonify({'error': 'Email уже используется'}), 400
            
            # Создание нового пользователя
            user = User(username=username, email=email)
            user.set_password(password)
            
            # В режиме отладки автоматически подтверждаем email
            if app.debug:
                user.email_confirmed = True
                print(f"ОТЛАДКА: Email автоматически подтвержден для {username} в режиме отладки")
            else:
                # Создание токена для подтверждения email
                confirmation_token = generate_confirmation_token(email)
                send_confirmation_email(email, confirmation_token)
                print(f"ОТЛАДКА: Отправлено письмо с подтверждением для {email}")
            
            db.session.add(user)
            db.session.commit()
            
            # Автоматический вход после регистрации
            session['user_id'] = user.id
            
            print(f"ОТЛАДКА: Пользователь {username} успешно зарегистрирован")
            
            return jsonify({
                'success': True,
                'message': 'Регистрация прошла успешно',
                'redirect': '/chat'
            })
            
        except Exception as e:
            print(f"ОТЛАДКА: Ошибка при регистрации: {str(e)}")
            return jsonify({'error': f'Произошла ошибка при регистрации: {str(e)}'}), 500

    # Отключаем капчу полностью
    show_recaptcha = False
    return render_template('register.html', recaptcha_site_key=app.config['RECAPTCHA_SITE_KEY'], show_recaptcha=show_recaptcha)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            recaptcha_response = request.form.get('g-recaptcha-response')

            print(f"ОТЛАДКА: Попытка входа пользователя {username}")

            if not username or not password:
                print("ОТЛАДКА: Отсутствует имя пользователя или пароль")
                return jsonify({'error': 'Необходимо указать имя пользователя и пароль'}), 400
                
            # Проверка капчи отключена
            # if not verify_recaptcha(recaptcha_response):
            #     print("ОТЛАДКА: Ошибка проверки капчи")
            #     return jsonify({'error': 'Пожалуйста, подтвердите, что вы не робот.'}), 400

            # Ищем пользователя
            user = User.query.filter_by(username=username).first()
            
            if not user:
                print(f"ОТЛАДКА: Пользователь {username} не найден")
                return jsonify({'error': 'Пользователь не найден'}), 401
            
            if not user.check_password(password):
                print(f"ОТЛАДКА: Неверный пароль для пользователя {username}")
                return jsonify({'error': 'Неверный пароль'}), 401
                
            # В режиме отладки пропускаем проверку подтверждения email
            if not app.debug and not user.email_confirmed:
                print(f"ОТЛАДКА: Email пользователя {username} не подтвержден")
                return jsonify({
                    'error': 'Ваш email не подтвержден. Пожалуйста, проверьте вашу почту и перейдите по ссылке подтверждения.',
                    'redirect': '/email_confirmation_notice'
                }), 401

            # Если все проверки пройдены, создаем сессию
            session['user_id'] = user.id
            
            print(f"ОТЛАДКА: Успешный вход для пользователя: {username}")
            
            return jsonify({
                'success': True,
                'redirect': '/chat'
            })

        except Exception as e:
            print(f"ОТЛАДКА: Ошибка при входе: {str(e)}")
            return jsonify({'error': f'Произошла ошибка при входе: {str(e)}'}), 500

    # Отключаем капчу полностью
    show_recaptcha = False
    return render_template('login.html', recaptcha_site_key=app.config['RECAPTCHA_SITE_KEY'], show_recaptcha=show_recaptcha)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')

# Middleware для проверки авторизации
@app.before_request
def check_auth():
    # Список путей, не требующих авторизации
    public_routes = [
        'home', 'login', 'register', 'static', 'success_page', 
        'confirm_email', 'email_confirmation_notice'
    ]
    
    if request.endpoint not in public_routes and 'user_id' not in session:
        return redirect('/login')

@app.route('/success.html')
def success_page():
    return render_template('success.html')

# Добавим функцию проверки роли
def has_role(user_id, role):
    user_role = UserRole.query.filter_by(user_id=user_id).first()
    if not user_role:
        # Создаем роль по умолчанию
        user_role = UserRole(user_id=user_id, role='user')
        db.session.add(user_role)
        db.session.commit()
    return user_role.role == role

# Добавим роут для админ-консоли
@app.route('/admin')
def admin_console():
    if 'user_id' not in session:
        return redirect('/login')
        
    if not has_role(session['user_id'], 'admin'):
        session['error_message'] = 'У вас нет прав для доступа к админ-панели'
        return redirect('/chat')
        
    users = User.query.all()
    return render_template('admin.html', users=users, current_user_id=session['user_id'])

# Добавим API для изменения ролей
@app.route('/api/change_role', methods=['POST'])
def change_role():
    if 'user_id' not in session or not has_role(session['user_id'], 'admin'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    user_id = request.json.get('user_id')
    new_role = request.json.get('role')
    
    if not user_id or not new_role:
        return jsonify({'error': 'Missing parameters'}), 400
        
    user_role = UserRole.query.filter_by(user_id=user_id).first()
    if not user_role:
        user_role = UserRole(user_id=user_id)
        
    user_role.role = new_role
    db.session.add(user_role)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/get_chats', methods=['GET'])
def get_chats():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        print(f"Getting chats for user_id: {session['user_id']}")  # Отладочный вывод
        chats = Chat.query.filter_by(user_id=session['user_id']).all()
        print(f"Found {len(chats)} chats")  # Отладочный вывод
        
        chat_list = [{
            'id': str(chat.id),
            'title': chat.title
        } for chat in chats]
        
        return jsonify(chat_list)
    except Exception as e:
        print(f"Error getting chats: {str(e)}")  # Отладочный вывод
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_user', methods=['POST'])
def delete_user():
    if 'user_id' not in session or not has_role(session['user_id'], 'admin'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        user_id = request.json.get('user_id')
        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400
            
        # Не даем удалить самого себя
        if int(user_id) == session['user_id']:
            return jsonify({'error': 'Нельзя удалить самого себя'}), 400
            
        # Удаляем все связанные данные
        ChatMessage.query.filter(ChatMessage.chat_id.in_(
            db.session.query(Chat.id).filter_by(user_id=user_id)
        )).delete(synchronize_session=False)
        Chat.query.filter_by(user_id=user_id).delete()
        UserRole.query.filter_by(user_id=user_id).delete()
        Subscription.query.filter_by(user_id=user_id).delete()
        Payment.query.filter_by(user_id=user_id).delete()
        User.query.filter_by(id=user_id).delete()
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'})
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({
            'success': True,
            'image_path': f'/static/uploads/{filename}'
        })
    
    return jsonify({'success': False, 'error': 'Invalid file type'})

# Функция для генерации токена подтверждения email
def generate_confirmation_token(email):
    return serializer.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])

# Функция для проверки токена подтверждения email
def confirm_token(token, expiration=3600):
    # В режиме отладки всегда возвращаем валидный результат
    if app.debug:
        print(f"ОТЛАДКА: Проверка токена пропущена в режиме отладки")
        # Извлекаем email из токена без проверки
        try:
            email = serializer.loads(token, salt=app.config['SECURITY_PASSWORD_SALT'])
            return email
        except:
            # Если не удалось извлечь email из токена, возвращаем фиктивный email
            return "test@example.com"

    try:
        email = serializer.loads(
            token,
            salt=app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
        return email
    except:
        return False

# Функция для отправки email
def send_email(to, subject, template):
    # Пропускаем отправку email в режиме отладки
    if app.debug:
        print(f"ОТЛАДКА: Email не отправлен в режиме отладки. Получатель: {to}, Тема: {subject}")
        return True
        
    msg = MIMEMultipart('alternative')
    msg['From'] = app.config['MAIL_USERNAME']
    msg['To'] = to
    msg['Subject'] = subject
    
    # Текст сообщения
    body = MIMEText(template, 'html')
    msg.attach(body)
    
    try:
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.sendmail(app.config['MAIL_USERNAME'], to, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Ошибка при отправке email: {str(e)}")
        return False

# Функция для проверки reCAPTCHA
def verify_recaptcha(response):
    # Всегда возвращаем True для быстрой разработки
    print("ОТЛАДКА: Проверка reCAPTCHA отключена для быстрой разработки")
    return True

# Маршрут для страницы с информацией о необходимости подтверждения email
@app.route('/email_confirmation_notice')
def email_confirmation_notice():
    return render_template('email_confirmation_notice.html')

# Маршрут для обработки ссылки подтверждения email
@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
        
        if not email:
            return render_template('error.html', error='Ссылка подтверждения недействительна или истекла.')
            
        user = User.query.filter_by(email=email).first()
        
        if not user:
            print(f"ОТЛАДКА: Пользователь с email {email} не найден")
            return render_template('error.html', error='Пользователь не найден.')
        
        if user.email_confirmed:
            return redirect('/login')
            
        user.email_confirmed = True
        user.email_confirmation_token = None  # Очищаем токен после использования
        db.session.add(user)
        db.session.commit()
        
        print(f"ОТЛАДКА: Email {email} успешно подтвержден")
        
        # Автоматически входим
        session['user_id'] = user.id
        
        return redirect('/chat')
    except Exception as e:
        print(f"ОТЛАДКА: Ошибка при подтверждении email: {str(e)}")
        return render_template('error.html', error=f'Ошибка при подтверждении email: {str(e)}')

def backup_database():
    try:
        # Создаем папку для резервных копий
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Имя файла с текущей датой и временем
        backup_file = f"{backup_dir}/chats_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
        
        # Правильный путь к файлу базы данных
        db_file = "instance/chats.db"  # Непосредственно указываем путь к файлу БД
        
        # Проверяем, существует ли исходный файл
        if os.path.exists(db_file):
            shutil.copy2(db_file, backup_file)
            print(f"База данных успешно сохранена в файл: {backup_file}")
            return backup_file
        else:
            print(f"Файл базы данных не найден: {db_file}")
            return None
    except Exception as e:
        print(f"Ошибка при создании резервной копии: {e}")
        return None

if __name__ == '__main__':
    # Делаем резервную копию базы данных при запуске
    try:
        backup_database()
    except Exception as e:
        print(f"Ошибка при создании резервной копии: {e}")
    
    app.run(debug=True, host='0.0.0.0')