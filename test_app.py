import sys
import io
import pytest
from unittest.mock import MagicMock, patch

# === Защита от ошибки DLL на Windows ===
sys.modules['numpy'] = MagicMock()
sys.modules['cv2'] = MagicMock()
sys.modules['cv2.dnn_superres'] = MagicMock()
# ========================================

from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@patch('app.upscale_task.delay')
def test_upscale_route(mock_delay, client):
    # Подготовка: мокаем возвращаемый ID задачи
    mock_delay.return_value = MagicMock(id='test-task-123')

    # Создаем "файл" из обычного текста.
    fake_file = io.BytesIO("это тестовая картинка".encode('utf-8'))

    # Отправляем запрос
    response = client.post(
        '/upscale',
        data={'file': (fake_file, 'test.png')},
        content_type='multipart/form-data'
    )

    # Проверяем результат
    assert response.status_code == 202
    assert response.get_json()['task_id'] == 'test-task-123'


@patch('app.upscale_task.AsyncResult')
def test_get_task_status_processing(mock_async_result, client):
    mock_async_result.return_value.state = 'PENDING'

    response = client.get('/tasks/test-task-123')

    assert response.status_code == 200
    assert response.get_json()['status'] == 'processing'


@patch('app.upscale_task.AsyncResult')
def test_get_task_status_completed(mock_async_result, client):
    mock_async_result.return_value.state = 'SUCCESS'

    response = client.get('/tasks/test-task-123')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'completed'
    assert data['file_url'] == '/processed/test-task-123.png'


@patch('app.redis_client')
def test_get_processed_file(mock_redis, client):
    # Мокаем Redis: запрос картинки, возвращаем просто строку байтов
    mock_redis.get.return_value = "фейковые байты из редиса".encode('utf-8')

    response = client.get('/processed/test-task-123.png')

    assert response.status_code == 200
    # Проверяем, что клиент пытался найти именно этот ключ в базе
    mock_redis.get.assert_called_once_with('processed_test-task-123')
