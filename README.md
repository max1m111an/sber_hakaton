# sber_hakaton
SberTechRun 2026

***Кейс №1 - Максидом "Микросервис умных калькуляторов ремонта и стоимости работ"***

## Запуск
1. Положите выгрузку каталога `products_final.json` в корень проекта (в git она не хранится — 274 МБ).
2. Запустите сервисы:
```
docker compose up --build
```
При первом старте API создаёт таблицы и, если база пустая, загружает каталог в фоне
(~1–2 минуты). Ход импорта: http://localhost/api/v1/health. Документация API: http://localhost/docs

Остановка сервисов (данные БД сохраняются в томе `pgdata`):
```
docker compose down
```
Полная очистка вместе с базой — `docker compose down -v` (каталог загрузится заново при следующем старте).

## Импорт каталога вручную
```
docker compose exec fastapi python -m database.import_products /app/data/products_final.json --reset
```
`--reset` очищает товары и категории перед загрузкой; без него импорт обновляет записи по `id`.
`--reseed-rules` перезаписывает нормативы расхода значениями из `database/seed_rules.py`.

Что делает импорт (`database/catalog_parser.py`, `database/classifier.py`):
- читает файл потоково, не загружая его целиком в память;
- категории берёт из поля `categories` и `url_key` товара (в выгрузке нет иерархии — все категории первого уровня);
- из характеристик и названия извлекает фасовку: м² в упаковке, кг, л, длину, штук в упаковке, норму расхода;
- определяет влагостойкость и тип работ (baseline-матчинг на правилах, уверенность 0.95 по категории / 0.75 по названию).

## API
| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/catalog/categories/tree` | Дерево категорий (`category_id`, `depth_level`) |
| GET | `/api/catalog/categories` | Сведения о категориях (`parent_id`, `depth_level`, `q`, `work_type`) |
| GET | `/api/catalog/products` | Товары: `category_id`, `include_subsections`, `include_categories_tree`, `per_page`, `page`, `q`, `brand_id`, `price_min`, `price_max`, `work_type`, `moisture_resistant`, `sort` |
| GET | `/api/catalog/products/{id}` | Полная карточка товара |
| GET | `/api/regions` | Регионы (в выгрузке их нет — пустой список) |
| POST | `/api/v1/calc/general` | Общий калькулятор: тип объекта + вариант ремонта (+ помещения) → смета и список покупок |
| POST | `/api/v1/calc/room` | Калькулятор комнаты: тип, площадь, влажность, уровень ремонта |
| POST | `/api/v1/product/{id}/calc` | Сколько купить товара под размеры (`area` / `length`+`width` / `width`+`height`) |
| POST | `/api/v1/match` | Тип работ, влагостойкость и помещения для нового товара |
| GET | `/api/v1/match/products` | Разметка каталога с уверенностью (для админки) |
| GET | `/api/v1/work-types` | Типы работ и число товаров |
| GET | `/api/v1/rules` | Нормативы расхода |
| GET | `/api/v1/health` | Состояние БД и импорта |

Нормативы расхода и ориентировочные расценки работ лежат в таблице `normative_rule`
(начальные значения — `database/seed_rules.py`).

## Установка зависимостей
Работа с poetry:
```
pip install poetry
poetry install
poetry export -f requirements.txt --output requirements.txt --without-hashes
pip install -r requirements.txt
```
