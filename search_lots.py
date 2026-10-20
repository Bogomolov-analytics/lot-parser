import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import re
import pickle
from datetime import datetime

# ============ НАСТРОЙКИ ============
API_KEY = "вставь свой ключ"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
YANDEXDRIVER_PATH = "yandexdriver.exe"
YANDEX_BROWSER_PATH = "browser.exe"
COOKIES_FILE = "cookies.pkl"
PROCESSED_FILE = "processed_ids.txt"
WATCH_LIST_FILE = "watch_list.txt"

# === TELEGRAM ===
TELEGRAM_TOKEN = "тоken"
TELEGRAM_CHAT_ID = "ID"

SKIP_AUTO = True

FILTER_URL = "https://tbankrot.ru/?pattern_id=446827&pattern_name=Долгожданная+покупка&sort=created&sort_order=desc&show_period=all"

BATCH_SIZE = 5
MAX_PRICE = 200_000

BAD_WORDS = [
    "доля", "доли", "долевая", "долевое", "1/2", "1/3", "1/4", "1/5",
    "1/6", "1/7", "1/8", "1/10", "1/100", "1/1000",
    "квартира", "жилой дом", "жилое помещение", "комната",
    "земельный участок", "земли", "участок", "садовый дом",
    "дача", "садовый участок", "снт", "иной объект",
    "оружие", "карабин", "ружьё", "ружье", "пистолет", "винтовка",
    "сайга", "ствол", "патрон", "огнестрел", "гладкоствольное",
    "нарезное", "ижмех", "мр-", "тоз-",
]

AUTO_WORDS = [
    "автомобиль", "машина", "легковой", "грузовой",
    "мотоцикл", "мотороллер", "транспортное средство",
    "фургон", "прицеп", "полуприцеп", "автобус", "тягач",
    "квадроцикл", "снегоход",
]


def send_to_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text[:4000],
            "disable_web_page_preview": True,
        }
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 200:
            print("  📨 Отправлено в Telegram")
        else:
            print(f"  ⚠️ Telegram ошибка: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"  ⚠️ Telegram не отправлен: {e}")


def extract_field(analysis, field_name):
    """Достаёт строку ПОЛЕ: значение из ответа DeepSeek."""
    m = re.search(rf"{field_name}[:\s]+(.+)", analysis, re.IGNORECASE)
    if m:
        return m.group(1).strip().split("\n")[0]
    return ""


def extract_verdict(analysis):
    return extract_field(analysis, "ВЕРДИКТ")


def extract_liquidity(analysis):
    return extract_field(analysis, "ЛИКВИДНОСТЬ")


def get_processed_ids():
    if not os.path.exists(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)


def save_processed_id(lot_id):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(lot_id + "\n")


def save_to_watchlist(lot_id, title, price, reason):
    date_str = datetime.now().strftime("%d.%m.%Y")
    line = f"{lot_id} | {title} | {price} | {reason} | {date_str}\n"
    with open(WATCH_LIST_FILE, "a", encoding="utf-8") as f:
        f.write(line)


def find_in_watchlist(title):
    if not os.path.exists(WATCH_LIST_FILE):
        return None, None
    short = title[:60].lower()
    with open(WATCH_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if short in line.lower():
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5:
                    return parts[2], parts[4]
    return None, None


def save_cookies(driver):
    try:
        with open(COOKIES_FILE, "wb") as f:
            pickle.dump(driver.get_cookies(), f)
        print("✅ Куки сохранены")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения куки: {e}")


def load_cookies(driver):
    if not os.path.exists(COOKIES_FILE):
        return False
    try:
        with open(COOKIES_FILE, "rb") as f:
            cookies = pickle.load(f)
        for cookie in cookies:
            cookie.pop("sameSite", None)
            cookie.pop("expiry", None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        return True
    except Exception as e:
        print(f"⚠️ Ошибка загрузки куки: {e}")
        return False


def parse_price(price_str):
    if not price_str:
        return None
    cleaned = re.sub(r"[^\d,.]", "", str(price_str))
    cleaned = cleaned.replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", cleaned.replace(" ", ""))
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def get_end_date(full_text):
    patterns = [
        r"Приём заявок:.*?до\s+(\d{2}[/.\-]\d{2}[/.\-]\d{4})",
        r"Проведение торгов:.*?до\s+(\d{2}[/.\-]\d{2}[/.\-]\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, full_text, re.IGNORECASE)
        if m:
            date_str = m.group(1).replace(".", "/").replace("-", "/")
            try:
                return datetime.strptime(date_str, "%d/%m/%Y")
            except ValueError:
                continue
    return None


def get_start_date(full_text):
    patterns = [
        r"Приём заявок:\s*с\s+(\d{2}[/.\-]\d{2}[/.\-]\d{4})",
        r"Проведение торгов:\s*с\s+(\d{2}[/.\-]\d{2}[/.\-]\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, full_text, re.IGNORECASE)
        if m:
            date_str = m.group(1).replace(".", "/").replace("-", "/")
            try:
                return datetime.strptime(date_str, "%d/%m/%Y")
            except ValueError:
                continue
    return None


def get_min_price(full_text):
    m = re.search(r"минимальная цена[:\s]+([\d\s]+[,.]?\d*)", full_text, re.IGNORECASE)
    if m:
        return parse_price(m.group(1))
    return None


def get_lot_status(full_text):
    text = full_text.lower()
    if "торги состоялись" in text:
        return "sold"
    if "торги не состоялись" in text:
        return "failed"
    end_date = get_end_date(full_text)
    if end_date and end_date < datetime.now():
        return "expired"
    return "active"


def get_priority_tag(full_text, current_price):
    start = get_start_date(full_text)
    if start and (datetime.now() - start).days <= 3:
        return "🔥 СВЕЖИЙ (торги только начались)"
    min_price = get_min_price(full_text)
    if min_price and current_price:
        if current_price <= min_price * 1.15:
            return "💰 НА ДНЕ (цена у минимума)"
    return "➖ СЕРЕДИНА (цена ещё не упала)"


def is_bad_lot(title, full_text, price_str):
    text = (title + " " + full_text).lower()
    for word in BAD_WORDS:
        if word in text:
            return True, f"мусор: {word}"
    if SKIP_AUTO:
        for word in AUTO_WORDS:
            if word in text:
                return True, f"авто (SKIP_AUTO=True): {word}"
    price = parse_price(price_str)
    if price is not None and price > MAX_PRICE:
        return True, f"цена {price} > {MAX_PRICE}"
    return False, "ок"


def get_lot_links(driver):
    seen = set()
    links = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(15):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='/item?id=']")
    for el in elements:
        href = el.get_attribute("href")
        if not href:
            continue
        match = re.search(r"/item\?id=(\d+)", href)
        if match and href not in seen:
            seen.add(href)
            links.append(href)
    return links


def get_lot_data_with_selenium(driver, url):
    driver.get(url)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(3)
    full_text = driver.find_element(By.TAG_NAME, "body").text
    title = driver.title
    price = "Не найдена"
    for line in full_text.split("\n"):
        low = line.lower()
        if ("руб" in low or "₽" in low) and re.search(r"\d", line):
            if any(w in low for w in ["задаток", "комиссия", "шаг", "аванс", "минимальная"]):
                continue
            price = line.strip()
            break
    return {"url": url, "title": title, "price": price, "full_text": full_text[:4000]}


def analyze_with_deepseek(lot_data, extra_context="", max_retries=2):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    prompt = f"""
Ты — аналитик банкротных торгов. Цель клиента: купить дёшево → продать за 4–6 недель.

Лот:
Ссылка: {lot_data['url']}
Название: {lot_data['title']}
Цена: {lot_data['price']}
{extra_context}
Текст: {lot_data['full_text'][:2000]}

НЕ берём: авто, доли, квартиры, дома, участки, оружие.
Берём: ТМЦ, оборудование, инструмент, стройматериалы, гараж/кладовка.

Ответь СТРОГО в таком формате (без воды, без разжёвывания):

ВЕРДИКТ: БРАТЬ или ОТКАЗ (до 10 слов)
ЛИКВИДНОСТЬ: ВЫСОКАЯ / СРЕДНЯЯ / НИЗКАЯ (до 10 слов — почему)
ЦЕНА ОТСЕЧЕНИЯ: <цифра> руб (если есть в тексте, иначе "не указана")
ТОЧКА ВХОДА: <диапазон> руб
МАРЖА: <диапазон> руб за 4–6 недель
РИСКИ: <1–2 главных риска, до 15 слов>
ДЕЙСТВИЕ: <что сделать сейчас, до 15 слов>
"""
    data = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "stream": False}
    for attempt in range(max_retries):
        try:
            response = requests.post(DEEPSEEK_URL, headers=headers, json=data, timeout=90)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except (requests.Timeout, requests.ConnectionError) as e:
            print(f"  ⚠️ DeepSeek не ответил (попытка {attempt + 1}): {e}")
            time.sleep(5)
        except Exception as e:
            return f"Ошибка DeepSeek: {e}"
    return "DeepSeek: не удалось получить ответ после 2 попыток"


def safe_get(driver, url, max_attempts=3, pause=10):
    for attempt in range(max_attempts):
        try:
            driver.get(url)
            return True
        except Exception as e:
            print(f"  ⚠️ Попытка {attempt + 1}/{max_attempts} не удалась: {e}")
            if attempt < max_attempts - 1:
                time.sleep(pause)
    return False


def create_driver():
    options = Options()
    options.binary_location = YANDEX_BROWSER_PATH

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")

    service = Service(executable_path=YANDEXDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """
    })

    return driver


def main():
    processed = get_processed_ids()
    driver = create_driver()

    try:
        print("Открываем Т-Банкрот...")
        safe_get(driver, "https://tbankrot.ru/")
        time.sleep(3)

        driver.maximize_window()

        print()
        print("=" * 60)
        print("ЛОГИН ВРУЧНУЮ:")
        print("1. Переключись в окно Яндекс.Браузера")
        print("2. Залогинься: логин, пароль, СМС")
        print("3. Убедись, что видишь свой НИК в правом верхнем углу")
        print("4. Вернись в это окно и нажми ENTER")
        print("=" * 60)
        print()

        input(">>> Залогинился? Нажми ENTER для продолжения... ")

        save_cookies(driver)

        print("\nПауза 10 секунд перед переходом на фильтр...")
        time.sleep(10)

        print("Открываем фильтр...")
        if not safe_get(driver, FILTER_URL, max_attempts=3, pause=10):
            print("❌ Не удалось открыть фильтр. Прерываем.")
            return

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(10)

        print("Прокручиваем страницу вниз для подгрузки всех лотов...")
        links = get_lot_links(driver)
        print(f"Найдено ссылок: {len(links)}")
        print(f"Режим: SKIP_AUTO = {SKIP_AUTO}")

        total_batches = (len(links) - 1) // BATCH_SIZE + 1 if links else 0
        new_count = 0
        skip_count = 0
        watch_count = 0
        repeat_count = 0

        for i in range(0, len(links), BATCH_SIZE):
            batch = links[i:i + BATCH_SIZE]
            print(f"\n===== Батч {i // BATCH_SIZE + 1} из {total_batches} =====")
            for link in batch:
                match = re.search(r"id=(\d+)", link)
                if not match:
                    continue
                lot_id = match.group(1)
                if lot_id in processed:
                    continue
                print(f"\n--- Лот ID {lot_id} ---")
                try:
                    lot_data = get_lot_data_with_selenium(driver, link)
                    current_price = parse_price(lot_data['price'])

                    bad, reason = is_bad_lot(lot_data['title'], lot_data['full_text'], lot_data['price'])
                    if bad:
                        print(f"⏭ Пропуск: {reason}")
                        save_processed_id(lot_id)
                        skip_count += 1
                        continue

                    status = get_lot_status(lot_data['full_text'])
                    if status == "sold":
                        print(f"⏭ Sold: куплен")
                        save_processed_id(lot_id)
                        skip_count += 1
                        continue
                    if status in ("failed", "expired"):
                        reason = "не состоялись" if status == "failed" else "срок истёк"
                        print(f"📌 Watch-list: {reason}")
                        save_to_watchlist(lot_id, lot_data['title'], lot_data['price'], reason)
                        save_processed_id(lot_id)
                        watch_count += 1
                        continue

                    priority = get_priority_tag(lot_data['full_text'], current_price)

                    extra_context = ""
                    repeat_note = ""
                    old_price_str, old_date = find_in_watchlist(lot_data['title'])
                    if old_price_str:
                        repeat_count += 1
                        old_price = parse_price(old_price_str)
                        diff_str = ""
                        if old_price and current_price:
                            diff_pct = (current_price - old_price) / old_price * 100
                            diff_str = f" (было {old_price:.0f} ₽ → стало {current_price:.0f} ₽, изменение {diff_pct:+.1f}%)"
                        print(f"⚠️ ПОВТОРНЫЙ лот (был в watch-list {old_date}){diff_str}")
                        repeat_note = f"⚠️ ПОВТОРНЫЙ ЛОТ (был в watch-list {old_date}){diff_str}"
                        extra_context = f"⚠️ ЭТО ПОВТОРНЫЙ ЛОТ. Ранее был в watch-list от {old_date} с ценой {old_price_str}.{diff_str} Учти это в анализе."

                    print(f"Приоритет: {priority}")
                    print(f"Цена: {lot_data['price']}")
                    print("Отправляем в DeepSeek...")
                    analysis = analyze_with_deepseek(lot_data, extra_context)
                    print(f"### Анализ:")
                    print(analysis)

                    verdict = extract_verdict(analysis)
                    liquidity = extract_liquidity(analysis)

                    tg_text = ""
                    if verdict:
                        tg_text += f"🎯 {verdict}\n"
                    if liquidity:
                        tg_text += f"📊 Ликвидность: {liquidity}\n"
                    tg_text += "\n"
                    tg_text += f"{priority}\n"
                    if repeat_note:
                        tg_text += f"{repeat_note}\n"
                    tg_text += f"📦 {lot_data['title']}\n"
                    tg_text += f"💰 {lot_data['price']}\n"
                    tg_text += f"🔗 {lot_data['url']}\n\n"
                    tg_text += analysis
                    send_to_telegram(tg_text)

                    save_processed_id(lot_id)
                    new_count += 1
                    time.sleep(2)
                except Exception as e:
                    print(f"⚠️ Ошибка на лоте {lot_id}: {e}")
                    continue
            time.sleep(5)

        print(f"\n✅ Обработано: {new_count}, пропущено: {skip_count}, в watch-list: {watch_count}, повторных: {repeat_count}")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
