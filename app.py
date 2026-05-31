import os
import io
import redis
from flask import Flask, request, jsonify, send_file
from tasks import upscale_task

app = Flask(__name__)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
redis_client = redis.StrictRedis(host=REDIS_HOST, port=6379, db=0)


@app.route('/upscale', methods=['POST'])
def upscale():
    if 'file' not in request.files:
        return jsonify({"error": "Файл не предоставлен"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Файл не выбран"}), 400

    img_bytes = file.read()
    task = upscale_task.delay(img_bytes)

    return jsonify({"task_id": task.id}), 202


@app.route('/health', methods=['GET'])
def health():
    """Возвращает 200 OK, если Flask готов принимать запросы"""
    return jsonify({"status": "ok"}), 200


@app.route('/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task = upscale_task.AsyncResult(task_id)

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
    app.run(host='0.0.0.0', port=5000)
