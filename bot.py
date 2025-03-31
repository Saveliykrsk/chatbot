import telebot
import subprocess
import os
import time
import string
import random
import json
from threading import Thread
import re
import traceback

# Токен вашего бота (замените на свой)
TOKEN = "7763700239:AAFyT-ZkcQ9LLnlAK5NM5aXA4-CYBvkLlwg"

bot = telebot.TeleBot(TOKEN)

# Словарь для хранения состояния пользовательских сессий
user_sessions = {}

# Пути для хранения данных
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
VPS_DATA_FILE = os.path.join(CONFIG_DIR, "vps_data.json")

# Создаем конфигурационную директорию, если она не существует
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

# Загружаем данные о созданных VPS
def load_vps_data():
    try:
        if os.path.exists(VPS_DATA_FILE):
            with open(VPS_DATA_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Ошибка при загрузке данных VPS: {e}")
        return {}

# Сохраняем данные о созданных VPS
def save_vps_data(data):
    try:
        with open(VPS_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Ошибка при сохранении данных VPS: {e}")

# Глобальные данные о VPS
vps_data = load_vps_data()

def execute_command(cmd, input_data=None, shell=True):
    """Выполняет команду и возвращает вывод"""
    try:
        print(f"Выполняю команду: {cmd}")
        if input_data:
            process = subprocess.Popen(
                cmd,
                shell=shell,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=input_data)
        else:
            process = subprocess.Popen(
                cmd,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
        
        output = stdout + stderr
        print(f"Результат команды (код {process.returncode}): {output[:200]}...")
        return output, process.returncode
    except Exception as e:
        error_text = f"Ошибка при выполнении команды: {str(e)}\n{traceback.format_exc()}"
        print(error_text)
        return error_text, -1

def generate_random_name(length=8):
    """Генерирует случайное имя для контейнера"""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

def create_docker_container(chat_id, os_type="ubuntu"):
    """Создает Docker контейнер с указанной операционной системой"""
    try:
        # Проверяем наличие Docker
        output, code = execute_command("docker --version")
        if code != 0:
            return None, "❌ Ошибка: Docker не установлен или недоступен. Пожалуйста, установите Docker."
        
        # Генерируем уникальное имя для контейнера
        container_name = f"vps-{generate_random_name()}"
        
        # Определяем образ в зависимости от типа ОС
        if os_type.lower() == "ubuntu":
            image = "ubuntu:22.04"
        elif os_type.lower() == "debian":
            image = "debian:12"
        else:
            return None, f"❌ Неподдерживаемый тип ОС: {os_type}"
        
        # Запускаем контейнер
        bot.send_message(chat_id, f"🔄 Запускаю контейнер с {os_type}...")
        
        # Создаем и запускаем контейнер
        cmd = f"docker run -d --name {container_name} --restart=always -it {image} /bin/bash -c 'apt-get update && apt-get install -y openssh-server sudo curl && mkdir -p /run/sshd && echo root:root | chpasswd && echo PermitRootLogin yes >> /etc/ssh/sshd_config && service ssh start && curl -s https://sshx.io/get | sh && sleep infinity'"
        output, code = execute_command(cmd)
        
        if code != 0:
            return None, f"❌ Ошибка при создании контейнера:\n{output}"
        
        # Ждем немного, чтобы контейнер успел запуститься и выполнить команды
        time.sleep(5)
        
        # Теперь получаем SSH данные через sshx
        bot.send_message(chat_id, "🔄 Настраиваю SSH доступ через sshx...")
        cmd = f"docker exec {container_name} sshx"
        output, code = execute_command(cmd)
        
        if code != 0:
            return None, f"❌ Ошибка при настройке sshx:\n{output}"
        
        # Получаем IP-адрес контейнера
        cmd = f"docker inspect -f '{{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {container_name}"
        ip_output, ip_code = execute_command(cmd)
        
        if ip_code != 0:
            ip_address = "неизвестно"
        else:
            ip_address = ip_output.strip()
        
        # Создаем объект с данными о VPS
        vps_info = {
            "container_name": container_name,
            "os_type": os_type,
            "ip_address": ip_address,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active",
            "sshx_output": output.strip()
        }
        
        # Обновляем данные о VPS
        if str(chat_id) not in vps_data:
            vps_data[str(chat_id)] = []
        
        vps_data[str(chat_id)].append(vps_info)
        save_vps_data(vps_data)
        
        return vps_info, None
        
    except Exception as e:
        error_text = f"❌ Неожиданная ошибка: {str(e)}\n{traceback.format_exc()}"
        return None, error_text

def process_vps_creation(chat_id, os_type):
    """Обрабатывает создание VPS в отдельном потоке"""
    try:
        bot.send_message(chat_id, f"🔄 Начинаю создание виртуального сервера ({os_type})...")
        
        # Создаем VPS
        vps_info, error = create_docker_container(chat_id, os_type)
        
        if error:
            bot.send_message(chat_id, error)
        else:
            # Формируем сообщение с результатами
            message = f"""✅ Виртуальный сервер успешно создан!

🖥️ **Информация о VPS**:
• 🔖 Имя: `{vps_info['container_name']}`
• 🐧 ОС: {vps_info['os_type']}
• 🌐 IP: {vps_info['ip_address']}
• 🕒 Создан: {vps_info['created_at']}

📋 **Подключение через SSH**:
```
{vps_info['sshx_output']}
```

Для управления используйте команды:
• /list - Список ваших серверов
• /stop [имя] - Остановить сервер
• /start_server [имя] - Запустить сервер
• /delete [имя] - Удалить сервер
• /ssh [имя] - Получить SSH данные
"""
            bot.send_message(chat_id, message, parse_mode="Markdown")
        
    except Exception as e:
        error_text = f"❌ Ошибка при создании VPS: {str(e)}\n{traceback.format_exc()}"
        bot.send_message(chat_id, error_text)
    finally:
        # Удаляем сессию пользователя
        if chat_id in user_sessions:
            del user_sessions[chat_id]

def stop_container(container_name):
    """Останавливает Docker контейнер"""
    cmd = f"docker stop {container_name}"
    output, code = execute_command(cmd)
    return code == 0, output

def start_container(container_name):
    """Запускает Docker контейнер"""
    cmd = f"docker start {container_name}"
    output, code = execute_command(cmd)
    return code == 0, output

def delete_container(container_name):
    """Удаляет Docker контейнер"""
    cmd = f"docker rm -f {container_name}"
    output, code = execute_command(cmd)
    return code == 0, output

def get_container_ssh(container_name):
    """Получает SSH данные для контейнера"""
    cmd = f"docker exec {container_name} sshx"
    output, code = execute_command(cmd)
    if code == 0:
        return True, output
    return False, output

def setup_freeroot(chat_id):
    """Настраивает freeroot и выполняет необходимые команды"""
    # Эту функцию оставляем для обратной совместимости,
    # но перенаправляем на использование Docker
    bot.send_message(chat_id, "⚠️ Метод freeroot устарел. Использую Docker для создания VPS...")
    return process_vps_creation(chat_id, "ubuntu")

def process_freeroot_setup(chat_id):
    """Обрабатывает настройку freeroot в отдельном потоке"""
    # Эту функцию оставляем для обратной совместимости,
    # но перенаправляем на использование Docker
    process_vps_creation(chat_id, "ubuntu")

@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.send_message(message.chat.id, """👋 Привет! Я бот для создания и управления виртуальными серверами.

Доступные команды:
• /create_ubuntu - Создать VPS на базе Ubuntu
• /create_debian - Создать VPS на базе Debian
• /list - Список ваших серверов
• /stop [имя] - Остановить сервер
• /start_server [имя] - Запустить сервер
• /delete [имя] - Удалить сервер
• /ssh [имя] - Получить SSH данные
• /help - Показать справку
""")

@bot.message_handler(commands=['create', 'create_ubuntu'])
def create_ubuntu_handler(message):
    chat_id = message.chat.id
    
    # Проверяем, не запущен ли уже процесс для этого пользователя
    if chat_id in user_sessions:
        bot.send_message(chat_id, "⚠️ У вас уже есть активная сессия. Пожалуйста, дождитесь завершения.")
        return
    
    # Создаем новую сессию
    user_sessions[chat_id] = {
        'start_time': time.time()
    }
    
    # Запускаем обработку в отдельном потоке
    thread = Thread(target=process_vps_creation, args=(chat_id, "ubuntu"))
    thread.daemon = True
    thread.start()
    
    bot.send_message(chat_id, "🚀 Запускаю процесс создания VPS на базе Ubuntu...\n"
                           "Это может занять некоторое время. Пожалуйста, подождите.")

@bot.message_handler(commands=['create_debian'])
def create_debian_handler(message):
    chat_id = message.chat.id
    
    # Проверяем, не запущен ли уже процесс для этого пользователя
    if chat_id in user_sessions:
        bot.send_message(chat_id, "⚠️ У вас уже есть активная сессия. Пожалуйста, дождитесь завершения.")
        return
    
    # Создаем новую сессию
    user_sessions[chat_id] = {
        'start_time': time.time()
    }
    
    # Запускаем обработку в отдельном потоке
    thread = Thread(target=process_vps_creation, args=(chat_id, "debian"))
    thread.daemon = True
    thread.start()
    
    bot.send_message(chat_id, "🚀 Запускаю процесс создания VPS на базе Debian...\n"
                           "Это может занять некоторое время. Пожалуйста, подождите.")

@bot.message_handler(commands=['list'])
def list_handler(message):
    chat_id = message.chat.id
    
    # Получаем список VPS пользователя
    user_vps = vps_data.get(str(chat_id), [])
    
    if not user_vps:
        bot.send_message(chat_id, "У вас пока нет созданных серверов. Используйте /create_ubuntu или /create_debian, чтобы создать новый сервер.")
        return
    
    # Формируем сообщение со списком
    message_text = "📋 **Список ваших серверов**:\n\n"
    
    for i, vps in enumerate(user_vps, 1):
        message_text += f"{i}. **{vps['container_name']}**\n"
        message_text += f"   • 🐧 ОС: {vps['os_type']}\n"
        message_text += f"   • 🌐 IP: {vps['ip_address']}\n"
        message_text += f"   • 🕒 Создан: {vps['created_at']}\n"
        message_text += f"   • 📊 Статус: {vps['status']}\n\n"
    
    bot.send_message(chat_id, message_text, parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def stop_handler(message):
    chat_id = message.chat.id
    args = message.text.split()
    
    if len(args) < 2:
        bot.send_message(chat_id, "⚠️ Пожалуйста, укажите имя сервера. Например: `/stop vps-abcdefgh`", parse_mode="Markdown")
        return
    
    container_name = args[1]
    
    # Проверяем, есть ли такой сервер у пользователя
    user_vps = vps_data.get(str(chat_id), [])
    found = False
    
    for vps in user_vps:
        if vps['container_name'] == container_name:
            found = True
            break
    
    if not found:
        bot.send_message(chat_id, f"⚠️ Сервер с именем {container_name} не найден. Используйте /list для просмотра списка ваших серверов.")
        return
    
    # Останавливаем контейнер
    bot.send_message(chat_id, f"🔄 Останавливаю сервер {container_name}...")
    success, output = stop_container(container_name)
    
    if success:
        # Обновляем статус в данных
        for vps in user_vps:
            if vps['container_name'] == container_name:
                vps['status'] = "stopped"
                break
        
        save_vps_data(vps_data)
        
        bot.send_message(chat_id, f"✅ Сервер {container_name} успешно остановлен")
    else:
        bot.send_message(chat_id, f"❌ Ошибка при остановке сервера {container_name}:\n{output}")

@bot.message_handler(commands=['start_server'])
def start_server_handler(message):
    chat_id = message.chat.id
    args = message.text.split()
    
    if len(args) < 2:
        bot.send_message(chat_id, "⚠️ Пожалуйста, укажите имя сервера. Например: `/start_server vps-abcdefgh`", parse_mode="Markdown")
        return
    
    container_name = args[1]
    
    # Проверяем, есть ли такой сервер у пользователя
    user_vps = vps_data.get(str(chat_id), [])
    found = False
    
    for vps in user_vps:
        if vps['container_name'] == container_name:
            found = True
            break
    
    if not found:
        bot.send_message(chat_id, f"⚠️ Сервер с именем {container_name} не найден. Используйте /list для просмотра списка ваших серверов.")
        return
    
    # Запускаем контейнер
    bot.send_message(chat_id, f"🔄 Запускаю сервер {container_name}...")
    success, output = start_container(container_name)
    
    if success:
        # Обновляем статус в данных
        for vps in user_vps:
            if vps['container_name'] == container_name:
                vps['status'] = "active"
                break
        
        save_vps_data(vps_data)
        
        bot.send_message(chat_id, f"✅ Сервер {container_name} успешно запущен")
    else:
        bot.send_message(chat_id, f"❌ Ошибка при запуске сервера {container_name}:\n{output}")

@bot.message_handler(commands=['delete'])
def delete_handler(message):
    chat_id = message.chat.id
    args = message.text.split()
    
    if len(args) < 2:
        bot.send_message(chat_id, "⚠️ Пожалуйста, укажите имя сервера. Например: `/delete vps-abcdefgh`", parse_mode="Markdown")
        return
    
    container_name = args[1]
    
    # Проверяем, есть ли такой сервер у пользователя
    user_vps = vps_data.get(str(chat_id), [])
    found = False
    vps_index = -1
    
    for i, vps in enumerate(user_vps):
        if vps['container_name'] == container_name:
            found = True
            vps_index = i
            break
    
    if not found:
        bot.send_message(chat_id, f"⚠️ Сервер с именем {container_name} не найден. Используйте /list для просмотра списка ваших серверов.")
        return
    
    # Удаляем контейнер
    bot.send_message(chat_id, f"🔄 Удаляю сервер {container_name}...")
    success, output = delete_container(container_name)
    
    if success:
        # Удаляем запись из данных
        if vps_index >= 0:
            user_vps.pop(vps_index)
            vps_data[str(chat_id)] = user_vps
            save_vps_data(vps_data)
        
        bot.send_message(chat_id, f"✅ Сервер {container_name} успешно удален")
    else:
        bot.send_message(chat_id, f"❌ Ошибка при удалении сервера {container_name}:\n{output}")

@bot.message_handler(commands=['ssh'])
def ssh_handler(message):
    chat_id = message.chat.id
    args = message.text.split()
    
    if len(args) < 2:
        bot.send_message(chat_id, "⚠️ Пожалуйста, укажите имя сервера. Например: `/ssh vps-abcdefgh`", parse_mode="Markdown")
        return
    
    container_name = args[1]
    
    # Проверяем, есть ли такой сервер у пользователя
    user_vps = vps_data.get(str(chat_id), [])
    found = False
    
    for vps in user_vps:
        if vps['container_name'] == container_name:
            found = True
            break
    
    if not found:
        bot.send_message(chat_id, f"⚠️ Сервер с именем {container_name} не найден. Используйте /list для просмотра списка ваших серверов.")
        return
    
    # Получаем SSH данные
    bot.send_message(chat_id, f"🔄 Получаю SSH данные для сервера {container_name}...")
    success, output = get_container_ssh(container_name)
    
    if success:
        message_text = f"""📋 **SSH данные для {container_name}**:

```
{output}
```

🔑 Данные для входа:
• Логин: `root`
• Пароль: `root`
"""
        bot.send_message(chat_id, message_text, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, f"❌ Ошибка при получении SSH данных для сервера {container_name}:\n{output}")

@bot.message_handler(commands=['status'])
def status_handler(message):
    chat_id = message.chat.id
    
    if chat_id in user_sessions:
        elapsed_time = time.time() - user_sessions[chat_id]['start_time']
        bot.send_message(chat_id, f"⏱️ У вас есть активная сессия, которая выполняется {elapsed_time:.1f} секунд.")
    else:
        bot.send_message(chat_id, "ℹ️ У вас нет активных сессий.")

@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = """
🤖 **Docker VPS Bot**

Команды:
• /start - Начало работы с ботом
• /create_ubuntu - Создать VPS на базе Ubuntu
• /create_debian - Создать VPS на базе Debian
• /list - Список ваших серверов
• /stop [имя] - Остановить сервер
• /start_server [имя] - Запустить сервер
• /delete [имя] - Удалить сервер
• /ssh [имя] - Получить SSH данные
• /status - Проверить статус текущей сессии
• /help - Показать это сообщение

Бот создает виртуальные серверы на базе Docker и настраивает SSH доступ через sshx.io.
"""
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def default_handler(message):
    bot.send_message(message.chat.id, "Используйте /help для просмотра списка доступных команд.")

if __name__ == "__main__":
    print("Бот запущен")
    try:
        # Проверка наличия Docker при запуске
        try:
            output, code = execute_command("docker --version")
            if code == 0:
                print(f"Docker установлен: {output.strip()}")
            else:
                print(f"Предупреждение: Docker не установлен или недоступен: {output}")
        except Exception as e:
            print(f"Ошибка при проверке версии Docker: {e}")
            
        # Проверка прав для запуска Docker
        try:
            output, code = execute_command("docker ps")
            if code == 0:
                print("Docker работает и доступен текущему пользователю")
            else:
                print(f"Предупреждение: Docker недоступен или требует прав администратора: {output}")
        except Exception as e:
            print(f"Ошибка при проверке доступности Docker: {e}")
        
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Критическая ошибка при запуске бота: {e}\n{traceback.format_exc()}")
