# sber_hakaton
SberTechRun 2026

***Кейс №1 - Максидом "Микросервис умных калькуляторов ремонта и стоимости работ"***

## Запуск
Запуск сервисов:
```
docker compose up --build
```

Остановка сервисов:
```
docker compose down -v
```

## Установка зависимостей
Работа с poetry:
```
pip install poetry
poetry install
poetry export -f requirements.txt --output requirements.txt --without-hashes
pip install -r requirements.txt
```
