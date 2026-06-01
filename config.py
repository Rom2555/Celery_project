import os


class Config:
    # Настройки Redis
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

    # Настройки Flask
    FLASK_PORT = int(os.environ.get('FLASK_PORT', 5000))

    # Настройки модели
    MODEL_PATH = os.environ.get('MODEL_PATH', 'EDSR_x2.pb')

    # Настройки хранения
    IMAGE_TTL = int(os.environ.get('IMAGE_TTL', 3600))

    # Допустимые форматы (для удобства)
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif'}
