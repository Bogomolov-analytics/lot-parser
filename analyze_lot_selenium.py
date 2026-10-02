import time
import sys
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- НАСТРОЙКИ ---
API_KEY = "sk-b06be7898c3b4611822548d67d06e177"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
YANDEXDRIVER_PATH = r"C:\Users\user\Desktop\Torgi\yandexdriver.exe"
PROFILE_DIR = r"C:\Users\user\Desktop\Torgi\profile"  # Папка для сохранения куки

def get_lot_data_with_selenium(url):
    options = Options()
    # Указываем папку профиля, чтобы куки сохранялись
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    
    service = Service(executable_path=YANDEXDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        driver.get(url)
        # Ждём загрузки body
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Если ты уже залогинен, пауза не нужна. Если нет — даём время на вход.
        # Можно уменьшить до 5 секунд, если профиль уже сохранён.
        time.sleep(60)  # 60 секунд на случай, если нужно залогиниться
        
        full_text = driver.find_element(By.TAG_NAME, "body").text
        title = driver.title
        price = "Не найдена"
        for line in full_text.split("\n"):
            if "руб" in line.lower() or "₽" in line:
                price = line
                break
        
        return {
            "url": url,
            "title": title,
            "price": price,
            "full_text": full_text[:4000]
        }
    except Exception as e:
        print(f"Ошибка Selenium: {e}")
        return None
    finally:
        driver.quit()  # Закрываем браузер после сбора данных

def analyze_with_deepseek(lot_data):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = f"""
    Ты — аналитик по банкротным торгам. Проанализируй лот:
    Ссылка: {lot_data['url']}
    Название: {lot_data['title']}
    Цена: {lot_data['price']}
    Текст страницы (фрагмент): {lot_data['full_text']}

    Проверь его по нашему чек-листу рисков (залог, запреты, ДТП, долги и т.д.).
    Предложи точку входа и рассчитай предварительную маржу.
    Ответ дай кратко, по пунктам.
    """
    data = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    try:
        response = requests.post(DEEPSEEK_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Ошибка при запросе к DeepSeek: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python analyze_lot_selenium.py <ссылка_на_лот>")
        sys.exit(1)
    
    url = sys.argv[1]
    print(f"Анализируем лот через Selenium: {url}\n")
    
    lot_data = get_lot_data_with_selenium(url)
    if lot_data:
        print(f"Название: {lot_data['title']}")
        print(f"Цена: {lot_data['price']}\n")
        print("Отправляем в DeepSeek...\n")
        analysis = analyze_with_deepseek(lot_data)
        print("### Анализ от DeepSeek:")
        print(analysis)
    else:
        print("Не удалось получить данные через Selenium.")