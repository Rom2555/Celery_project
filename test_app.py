import io
import pytest
from unittest.mock import MagicMock, patch

from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@patch('app.celery.send_task')
@patch('app.is_valid_image', return_value=True)
def test_upscale_route_success(mock_is_valid, mock_send_task, client):
    """Тест успешной отправки файла (проверка только маршрута и вызова таски)"""
    mock_send_task.return_value = MagicMock(id='test-task-123')

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
    mock_send_task.assert_called_once()


def test_upscale_route_invalid_extension(client):
    """Тест ошибки при неверном расширении файла"""
    fake_file = io.BytesIO("какой то текст".encode('utf-8'))
    response = client.post(
        '/upscale',
        data={'file': (fake_file, 'test.txt')},
        content_type='multipart/form-data'
    )

    assert response.status_code == 400
    assert "Неподдерживаемое расширение" in response.get_json()['error']


def test_upscale_route_invalid_magic_bytes(client):
    """Тест ошибки при подмене сигнатуры файла (расширение png, но внутри текст)"""
    fake_file = io.BytesIO("это не картинка".encode('utf-8'))
    response = client.post(
        '/upscale',
        data={'file': (fake_file, 'fake.png')},
        content_type='multipart/form-data'
    )

    assert response.status_code == 400
    assert "неверная сигнатура" in response.get_json()['error']


@patch('app.celery.AsyncResult')
def test_get_task_status_processing(mock_async_result, client):
    """Тест статуса 'в процессе'"""
    mock_async_result.return_value.state = 'PENDING'

    response = client.get('/tasks/test-task-123')

    assert response.status_code == 200
    assert response.get_json()['status'] == 'processing'


@patch('app.celery.AsyncResult')
def test_get_task_status_completed(mock_async_result, client):
    """Тест статуса 'завершено'"""
    mock_async_result.return_value.state = 'SUCCESS'

    response = client.get('/tasks/test-task-123')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'completed'
    assert data['file_url'] == '/processed/test-task-123.png'


@patch('app.redis_client')
def test_get_processed_file(mock_redis, client):
    """Тест скачивания готового файла"""
    mock_redis.get.return_value = "фейковые байты из редиса".encode('utf-8')

    response = client.get('/processed/test-task-123.png')

    assert response.status_code == 200
    # Проверяем, что клиент пытался найти именно этот ключ в базе
    mock_redis.get.assert_called_once_with('processed_test-task-123')


@patch('app.redis_client')
def test_get_processed_file_not_found(mock_redis, client):
    """Тест ошибки, если файл удалился из Redis (истек TTL)"""
    mock_redis.get.return_value = None

    response = client.get('/processed/test-task-123.png')

    assert response.status_code == 404
    assert "истёк" in response.get_json()['error']