# Image Upscaler

Асинхронное API для увеличения разрешения изображений с использованием нейросетевой модели EDSR (Enhanced Deep Super-Resolution).

## Описание

Приложение принимает изображение через REST API, обрабатывает его с помощью модели EDSR x2 и возвращает увеличенную версию. Обработка происходит асинхронно через Celery, результаты сохраняются в Redis на 1 час.

## Архитектура

Приложение состоит из трёх основных компонентов:

- **Flask (app.py)** - REST API, принимает изображения и возвращает статус задач
- **Celery (tasks.py)** - асинхронный воркер, обрабатывает изображения нейросетью EDSR
- **Redis** - брокер очередей между Flask и Celery, а также хранилище для результатов

При отправке изображения клиент получает ID задачи и периодически опрашивает статус через API. После завершения обработки результат доступен для скачивания.

## Требования

- Python 3.10+
- Docker и Docker Compose (для контейнерного запуска)

## Быстрый старт

### Запуск через Docker Compose

1. Скопируйте пример конфигурации:
```bash
cp .env_example .env
```

2. Запустите сервисы:
```bash
docker-compose up -d
```

3. Выполните апскейл изображения:
```bash
python client.py lama_300px.png
```

### Локальный запуск

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

3. В отдельном терминале запустите воркер Celery:
```bash
celery -A tasks worker --loglevel=info
```

4. В отдельном терминале запустите Flask:
```bash
python app.py
```

## API

### POST /upscale

Отправка изображения на обработку.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` - изображение в формате PNG/JPG

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### GET /tasks/{task_id}

Проверка статуса задачи.

**Response:**
```json
{
  "status": "processing" | "completed" | "failed",
  "file_url": "/processed/{task_id}.png"  // только при status=completed
}
```

### GET /processed/{file}

Скачивание обработанного изображения.

## Конфигурация (.env)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `REDIS_HOST` | Хост Redis | `localhost` (Docker: `redis`) |
| `REDIS_PORT` | Порт Redis | `6379` |
| `FLASK_PORT` | Порт Flask API | `5000` |
| `MODEL_PATH` | Путь к модели EDSR | `EDSR_x2.pb` |
| `IMAGE_TTL` | Время жизни файла в Redis (сек) | `3600` (1 час) |

## Технологии

- **Flask** - веб-фреймворк
- **Celery** - очередь асинхронных задач
- **Redis** - брокер сообщений и хранилище результатов
- **OpenCV** - нейросеть EDSR для апскейлинга

## Тестирование

```bash
pytest test_app.py
```

## Примечания

Этот учебный проект создан в рамках курса Python-разработчик от netology.ru
