# Конфигурация бота
BOT_TOKEN = '7612199346:AAEktN5uu3r24vngsosyxKY1xlSWuFBJTEs'

# Системные настройки
SYSTEM_CONFIG = {
    'jail_dirs': ['bin', 'lib', 'lib64', 'usr/bin', 'usr/lib', 'usr/lib64', 'etc', 'dev', 'tmp'],
    'essential_files': [
        '/bin/bash',
        '/bin/rbash',
        '/bin/ls',
        '/bin/cp',
        '/bin/mv',
        '/bin/mkdir',
        '/usr/bin/apt',
        '/usr/bin/apt-get',
        '/usr/bin/dpkg',
        '/bin/nano'
    ]
}

# Ограничения пользователей
USER_LIMITS = {
    'nproc': 100,
    'nofile': 1024,
    'fsize': 1048576,
    'cpu': 50,
    'as': 1048576,
    'maxlogins': 2
}

# Запрещенные команды
BLOCKED_COMMANDS = {
    'rm': '⛔ Команда rm запрещена для безопасности',
    'chmod': '⛔ Команда chmod запрещена для безопасности',
    'chown': '⛔ Команда chown запрещена для безопасности',
    'sudo': '⛔ Команда sudo запрещена для безопасности',
    'su': '⛔ Команда su запрещена для безопасности',
    'wget': '⛔ Команда wget запрещена для безопасности',
    'curl': '⛔ Команда curl запрещена для безопасности'
}

# SSH настройки
SSH_CONFIG = {
    'X11Forwarding': 'no',
    'AllowTcpForwarding': 'no',
    'PermitTunnel': 'no',
    'AllowAgentForwarding': 'no',
    'MaxSessions': 2,
    'ForceCommand': 'internal-sftp'
}

# Характеристики VDS
VDS_SPECS = {
    'cpu': '8 vCPU',
    'ram': '32 GB',
    'disk': '100 GB SSD',
    'traffic': 'Безлимитный',
    'speed': 'до 1 Гбит/с'
} 