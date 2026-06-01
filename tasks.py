import os
import sys
import logging
import cv2
import numpy as np
import redis
from celery import Celery
from config import Config

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация Celery
celery = Celery(
    'tasks',
    broker=f'redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}/0',
    backend=f'redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}/0'
)

redis_client = redis.StrictRedis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=0)

# Проверка есть ли модель
MODEL_PATH = Config.MODEL_PATH
if not os.path.exists(MODEL_PATH):
    logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Файл модели '{MODEL_PATH}' не найден!")
    logger.critical("Воркер не может быть запущен без модели. Завершение работы.")
    sys.exit(1)

logger.info(f"Загрузка модели {MODEL_PATH}...")
scaler = cv2.dnn_superres.DnnSuperResImpl_create()
scaler.readModel(MODEL_PATH)
scaler.setModel("edsr", 2)
logger.info("Модель EDSR_x2 успешно загружена.")

@celery.task(bind=True, name='tasks.upscale_task')
def upscale_task(self, img_bytes):
    """ Работа с байтами в оперативной памяти. """
    try:
        # Декодируем байты в numpy массив (аналог cv2.imread, но из памяти)
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Неверные данные изображения")

        result = scaler.upsample(image)

        # Кодируем обратно в байты (аналог cv2.imwrite, но в память)
        success, encoded_img = cv2.imencode('.png', result)
        if not success:
            raise Exception("Не удалось закодировать изображение")

        img_out_bytes = encoded_img.tobytes()

        # Используем TTL из конфига
        redis_client.setex(f"processed_{self.request.id}", Config.IMAGE_TTL, img_out_bytes)

        return True
    except Exception as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise e