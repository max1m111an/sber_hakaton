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

Что делает импорт (`database/catalog_parser.py`):
- читает файл потоково, не загружая его целиком в память;
- категории берёт из поля `categories` и `url_key` товара (в выгрузке нет иерархии — все категории первого уровня);
- из характеристик и названия извлекает фасовку: м² в упаковке, кг, л, длину, штук в упаковке, норму расхода;
- определяет влагостойкость; тип работ товару присваивает ML-модель (см. ниже) сразу после импорта.

## ML-матчинг товаров к типам работ (п. 3.1 ТЗ)
`ml/matching.py` — текст товара (`name` + `marketing_description` + `characteristics`) → эмбеддинг
`sentence-transformers` (`cointegrated/rubert-tiny2`) → `LogisticRegression` → тип работ и уверенность.
`MLMatcher.predict(product) -> (work_type_id, confidence)`; id — из `database/work_types.py` (0 — не относится к работам).

- **Обучающая выборка:** решения менеджера из «Разметки каталога» + слабая разметка правилами по ключевым словам
  (`ml/weak_labels.py`, только для обучения) + случайные неразмеченные товары как класс «не относится к работам».
- **Подбор в калькуляторе** берёт только товары с уверенностью модели ≥ `ML_CONFIDENCE_THRESHOLD` (0.8) или подтверждённые менеджером.
- **Когда обучается:** автоматически после импорта и при старте, если модели нет; вручную — кнопка «Переобучить модель»
  в админке, `POST /api/v1/ml/train` или `docker compose exec fastapi python -m ml.matching train`.
- **Качество** (F1 по типам работ на отложенных 20%, точность и полнота при пороге) — `GET /api/v1/stats`, страница «Метрики».
- **Docker:** torch ставится CPU-сборкой, модель скачивается при сборке образа и в рантайме сеть не нужна (`HF_HUB_OFFLINE=1`).
  Обученный классификатор и кеш эмбеддингов лежат в томе `ml_artifacts`. Для GPU:
  `docker compose build --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121` и `ML_DEVICE=cuda`.

## API
| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/catalog/categories/tree` | Дерево категорий (`category_id`, `depth_level`) |
| GET | `/api/catalog/categories` | Сведения о категориях (`parent_id`, `depth_level`, `q`, `work_type`) |
| GET | `/api/catalog/products` | Товары: `category_id`, `include_subsections`, `include_categories_tree`, `per_page`, `page`, `q`, `brand_id`, `price_min`, `price_max`, `work_type`, `moisture_resistant`, `sort` |
| GET | `/api/catalog/products/{id}` | Полная карточка товара |
| GET | `/api/regions` | Регионы (в выгрузке их нет — пустой список) |
| POST | `/api/v1/calc/general` | Общий калькулятор: тип объекта + вариант ремонта (+ помещения) → смета и список покупок |
| POST | `/api/v1/calc/room` | Калькулятор комнаты: тип, площадь, влажность, уровень ремонта; `picks` — ручной выбор товара по коду работы, `disabled` — исключённые работы |
| POST | `/api/v1/product/{id}/calc` | Сколько купить товара под размеры (`area` / `length`+`width` / `width`+`height`) |
| POST | `/api/v1/match` | Предсказание модели для нового товара: `work_type_id`, уверенность, 3 альтернативы |
| GET | `/api/v1/match/products` | Предсказания модели по каталогу: уверенность, метка обучения, расхождения (`disagree`) |
| PATCH | `/api/v1/match/products/{id}` | Менеджер подтверждает или меняет тип работ |
| POST | `/api/v1/match/confirm` | Массовое подтверждение (по `ids` или фильтру `min_confidence`, `work_type`, `q`) |
| GET | `/api/v1/stats` | Сводка по каталогу и метрики ML-модели (F1, точность при пороге, распределение уверенности) |
| POST | `/api/v1/ml/train` | Переобучить ML-матчинг в фоне |
| GET | `/api/v1/ml/status` | Состояние модели и обучения |
| GET | `/api/v1/work-types` | Типы работ и число товаров |
| GET | `/api/v1/rules` | Нормативы расхода |
| GET | `/api/v1/health` | Состояние БД и импорта |

Нормативы расхода и ориентировочные расценки работ лежат в таблице `normative_rule`
(начальные значения — `database/seed_rules.py`).

## Фронтенд
React-приложение (`frontend/`) работает на данных API: смета — `POST /api/v1/calc/general`,
каталог — `/api/catalog/products`, карточка — `/api/catalog/products/{id}` и `/api/v1/product/{id}/calc`,
разметка — `/api/v1/match/*`, метрики — `/api/v1/stats`. Для `npm run dev` API проксируется на `localhost:8080`.

## Установка зависимостей
Работа с poetry:
```
pip install poetry
poetry install
poetry export -f requirements.txt --output requirements.txt --without-hashes
pip install -r requirements.txt
```
