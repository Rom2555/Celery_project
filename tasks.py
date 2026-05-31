import os
import cv2
import numpy as np
import redis
from celery import Celery

# Инициализация Celery
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
celery = Celery(
    'tasks',
    broker=f'redis://{REDIS_HOST}:6379/0',
    backend=f'redis://{REDIS_HOST}:6379/0'
)

print("Загрузка модели EDSR_x2...")
MODEL_PATH = os.environ.get('MODEL_PATH', 'EDSR_x2.pb')
print(f"Загрузка модели {MODEL_PATH}...")
scaler = cv2.dnn_superres.DnnSuperResImpl_create()
scaler.readModel(MODEL_PATH)
scaler.setModel("edsr", 2)
print("EDSR_x2 модель успешно загружена.")

# Клиент Redis для сохранения результата
redis_client = redis.StrictRedis(host=REDIS_HOST, port=6379, db=0)


@celery.task(bind=True)
def upscale_task(self, img_bytes):
    """ Работа с байтами в оперативной памяти. """
    try:
        # Декодируем байты в numpy массив (аналог cv2.imread, но из памяти)
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Неверные данные изображения")

        # Ваша логика апскейла
        result = scaler.upsample(image)

        # Кодируем обратно в байты (аналог cv2.imwrite, но в память)
        success, encoded_img = cv2.imencode('.png', result)
        if not success:
            raise Exception("Не удалось закодировать изображение")

        img_out_bytes = encoded_img.tobytes()

        # Сохраняем обработанное изображение в Redis с TTL 1 час (3600 сек)
        ttl_seconds = int(os.environ.get('IMAGE_TTL', 3600))
        redis_client.setex(f"processed_{self.request.id}", ttl_seconds, img_out_bytes)

        return True
    except Exception as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise e