![example event parameter](https://github.com/Migunov-Yaroslav/SWA_bot_2/actions/workflows/main.yml/badge.svg?event=push)

# Стек технологий
<p>
  <a 
  target="_blank" href="https://www.python.org/downloads/" title="Python version"><img src="https://img.shields.io/badge/python-_3.7-green.svg">
  </a>
</p>

# SWA_Bot_2

Телеграм-бот для доступа к базе данных запчастей в Google таблице.
Доступ к боту предоставляется после однократного ввода пароля.
Бот работает с Google таблицей через API, для доступа к которому необходимо 
зарегистрироваться и скачать файл .JSON с приватными ключами. Более подробно 
процесс авторизации в Google API можно посмотреть здесь:
```zsh
https://pygsheets.readthedocs.io/en/stable/authorization.html
```
Шаблон Google таблицы находится по адресу SWA_bot/DB.xlsx


## Шаблон наполнения файла .env
Файл .env находится по адресу SWA_bot/infra/. Пример наполнения:
```
TELEGRAM_TOKEN - токен телеграм-бота
BOT_PASSWORD - пароль для доступа к боту
SPREADSHEET_NAME - название Google spreadsheet с базой запчастей
```

## Установка проекта и запуск в контейнере:

Клонируйте проект себе на локальную машину:
```zsh
sudo git clone https://github.com/Migunov-Yaroslav/SWA_Bot_2.git
```

Перейдите в папку /yamdb_final/infra:
```zsh
cd infra_sp2/infra/
```

Соберите контейнеры:
```zsh
sudo docker-compose up -d --build
```


Разработчик:
```zsh
Ярослав Мигунов
```
