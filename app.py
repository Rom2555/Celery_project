# app.py
import os
import io
import redis
from flask import Flask, request, jsonify, send_file
from config import Config
from celery import Celery

app = Flask(__name__)
celery = Celery(
    'tasks',
    broker=f'redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}/0',
    backend=f'redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}/0'
)

redis_client = redis.StrictRedis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=0)

# Функция проверки MAGIC BYTES
def is_valid_image(file_stream) -> bool:
    """Проверяет сигнатуры (magic bytes) файла."""
    # Сохраняем текущую позицию курсора
    current_pos = file_stream.tell()
    # Читаем первые 12 байт
    header = file_stream.read(12)
    # Возвращаем курсор обратно чтобы Flask мог потом прочитать файл целиком
    file_stream.seek(current_pos)

    # Словарь сигнатур {формат: байты}
    signatures = {
        'jpeg': [b'\xff\xd8\xff'],
        'png': [b'\x89PNG\r\n\x1a\n'],
        'bmp': [b'BM'],
        'tiff': [b'II\x2a\x00', b'MM\x00\x2a'] # Little-endian и Big-endian
    }

    for format_name, sigs in signatures.items():
        for sig in sigs:
            if header.startswith(sig):
                return True
    return False

@app.route('/upscale', methods=['POST'])
def upscale():
    if 'file' not in request.files:
        return jsonify({"error": "Файл не предоставлен"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Файл не выбран"}), 400

    # Проверка расширения
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in Config.ALLOWED_EXTENSIONS:
        return jsonify({"error": "Неподдерживаемое расширение файла. Допустимы: JPG, PNG, BMP, TIFF"}), 400

    # Проверка Magic Bytes
    if not is_valid_image(file.stream):
        return jsonify({"error": "Файл не является изображением (неверная сигнатура) или поврежден"}), 400

    img_bytes = file.read()

    # Отправляем задачу по имени, чтобы не грузить модель в память API
    task = celery.send_task('tasks.upscale_task', args=[img_bytes])

    return jsonify({"task_id": task.id}), 202


@app.route('/health', methods=['GET'])
def health():
    """Возвращает 200 OK, если Flask готов принимать запросы"""
    return jsonify({"status": "ok"}), 200


@app.route('/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task = celery.AsyncResult(task_id)

    if task.state == 'PENDING':
        response = {'status': 'processing'}
    elif task.state == 'SUCCESS':
        response = {
            'status': 'completed',
            'file_url': f'/processed/{task_id}.png'
        }
    else:
        response = {
            'status': 'failed',
            'error': str(task.info.get('error', 'Неизвестная ошибка')) if isinstance(task.info, dict) else str(
                task.info)
        }
    return jsonify(response)


@app.route('/processed/<file>', methods=['GET'])
def get_processed_file(file):
    task_id = file.rsplit('.', 1)[0]
    img_bytes = redis_client.get(f"processed_{task_id}")

    if not img_bytes:
        return jsonify({"error": "Файл не найден или срок его хранения истёк"}), 404

    return send_file(
        io.BytesIO(img_bytes),
        mimetype='image/png',
        as_attachment=False
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.FLASK_PORT)