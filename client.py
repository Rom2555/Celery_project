import requests
import sys
import time
import os

BASE_URL = "http://localhost:5000"
POLLING_INTERVAL = 2  # секунды между проверками статуса
MAX_WAIT_TIME = 300  # максимальное время ожидания в секундах


def upscale_image(image_path: str):
    if not os.path.exists(image_path):
        print(f"Ошибка: Файл '{image_path}' не найден.")
        sys.exit(1)

    print(f"[*] Отправка файла '{image_path}' на апскейл...")

    # Отправляем файл
    with open(image_path, 'rb') as f:
        files = {'file': (os.path.basename(image_path), f)}
        try:
            response = requests.post(f"{BASE_URL}/upscale", files=files)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[!] Ошибка при отправке: {e}")
            sys.exit(1)

    task_id = response.json().get('task_id')
    print(f"[+] Задача создана. ID: {task_id}")
    print(f"[*] Ожидание обработки (проверка каждые {POLLING_INTERVAL} сек)...")

    # Ожидание результата
    start_time = time.time()
    file_url = None

    while time.time() - start_time < MAX_WAIT_TIME:
        time.sleep(POLLING_INTERVAL)

        try:
            status_resp = requests.get(f"{BASE_URL}/tasks/{task_id}")
            status_data = status_resp.json()
        except requests.exceptions.RequestException:
            print("[!] Потеряно соединение с сервером. Повторная попытка...")
            continue

        status = status_data.get('status')

        if status == 'processing':
            # Выводим точку, чтобы видеть, что процесс не завис
            print(".", end="", flush=True)

        elif status == 'completed':
            print("\n[+] Обработка завершена!")
            file_url = status_data.get('file_url')
            break

        elif status == 'failed':
            print(f"\n[!] Задача завершилась с ошибкой: {status_data.get('error', 'Неизвестная ошибка')}")
            sys.exit(1)
    else:
        print(f"\n[!] Превышено время ожидания ({MAX_WAIT_TIME} секунд).")
        sys.exit(1)

    # 3. Скачивание результата
    if file_url:
        print(f"[*] Скачивание обработанного файла...")
        try:
            download_resp = requests.get(f"{BASE_URL}{file_url}")
            download_resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[!] Ошибка при скачивании файла: {e}")
            sys.exit(1)

        # Формируем имя выходного файла (например, lama_300px_upscaled.png)
        base_name, ext = os.path.splitext(os.path.basename(image_path))
        output_filename = f"{base_name}_upscaled{ext}"

        with open(output_filename, 'wb') as out_file:
            out_file.write(download_resp.content)

        print(f"[+] Готово! Файл сохранен как: {output_filename}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Использование: python client.py <путь_к_изображению>")
        print("Пример: python client.py lama_300px.png")
        sys.exit(1)

    upscale_image(sys.argv[1])