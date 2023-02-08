FROM python:3.7-slim

WORKDIR /app

COPY requirements.txt .

RUN pip 3 install -r ./requirements.txt --no-cache-dir

COPY . .

CMD ["python3", "telegram_bot.py"]
