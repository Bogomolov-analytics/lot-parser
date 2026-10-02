import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import sys

API_KEY = "вставь сюда свой ключ"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

def get_lot_data(url):
    headers = {
        "User-Agent": UserAgent().random,
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Не найдено"
        
        price = "Не найдена"
        for tag in soup.find_all(["span", "div", "p"]):
            text = tag.get_text(strip=True)
            if "руб" in text.lower() or "₽" in text:
                price = text
                break

        full_text = soup.get_text(separator="\n", strip=True)[:2000]
        print("=== СПАРСЕННЫЙ ТЕКСТ ===")
        print(full_text)
        print("=== КОНЕЦ ТЕКСТА ===")

        return {
            "url": url,
            "title": title,
            "price": price,
            "full_text": full_text
        }
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return None

def analyze_with_deepseek(lot_data):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = f"""
    Ты — аналитик по банкротным торгам. Проанализируй лот по ссылке:
    {lot_data['url']}
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
        print("Использование: python analyze_lot.py <ссылка_на_лот>")
        sys.exit(1)
    
    url = sys.argv[1]
    print(f"Анализируем лот: {url}\n")
    
    lot_data = get_lot_data(url)
    if lot_data:
        print(f"Название: {lot_data['title']}")
        print(f"Цена: {lot_data['price']}\n")
        print("Отправляем в DeepSeek...\n")
        analysis = analyze_with_deepseek(lot_data)
        print("### Анализ от DeepSeek:")
        print(analysis)
    else:
        print("Не удалось получить данные по ссылке. Возможно, сайт блокирует парсинг.")
