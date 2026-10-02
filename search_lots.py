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
API_KEY = "вставь сюда свой ключ"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
YANDEXDRIVER_PATH = r"C:\Users\user\Desktop\Torgi\yandexdriver.exe"
YANDEX_BROWSER_PATH = r"C:\Users\user\AppData\Local\Yandex\YandexBrowser\Application\browser.exe"
COOKIES_FILE = r"C:\Users\user\Desktop\Torgi\cookies.pkl"
PROCESSED_FILE = r"C:\Users\user\Desktop\Torgi\processed_ids.txt"
WATCH_LIST_FILE = r"C:\Users\user\Desktop\Torgi\watch_list.txt"

# === ФЛАГИ ===
SKIP_AUTO = True   # True = пропускать авто, False = брать авто

FILTER_URL = "https://tbankrot.ru/?start_p1=&start_p2=1500000&p1=&p2=200000.00&min_p1=&min_p2=200000.00&sort=created&sort_order=desc&swp=any_word&search=&region%5B%5D=19&region%5B%5D=27&region%5B%5D=32&type_1=on&num=&place%5B%5D=109&place%5B%5D=119&place%5B%5D=120&place%5B%5D=121&place%5B%5D=122&place%5B%5D=123&place%5B%5D=124&place%5B%5D=125&place%5B%5D=126&place%5B%5D=127&place%5B%5D=129&place%5B%5D=131&place%5B%5D=132&place%5B%5D=135&place%5B%5D=136&place%5B%5D=137&place%5B%5D=138&place%5B%5D=139&place%5B%5D=140&place%5B%5D=141&place%5B%5D=142&place%5B%5D=145&place%5B%5D=146&place%5B%5D=149&place%5B%5D=151&place%5B%5D=152&place%5B%5D=153&place%5B%5D=154&place%5B%5D=157&place%5B%5D=158&place%5B%5D=160&place%5B%5D=161&place%5B%5D=162&place%5B%5D=165&place%5B%5D=166&place%5B%5D=167&place%5B%5D=168&place%5B%5D=170&place%5B%5D=179&place%5B%5D=180&place%5B%5D=181&place%5B%5D=183&place%5B%5D=184&place%5B%5D=185&place%5B%5D=186&place%5B%5D=187&place%5B%5D=188&place%5B%5D=189&place%5B%5D=191&place%5B%5D=1003&place%5B%5D=1004&place%5B%5D=1005&place%5B%5D=1006&place%5B%5D=1007&place%5B%5D=1010&place%5B%5D=1011&place%5B%5D=1012&place%5B%5D=1013&place%5B%5D=1014&place%5B%5D=1015&place%5B%5D=1016&place%5B%5D=1017&place%5B%5D=1018&place%5B%5D=1019&place%5B%5D=1020&place%5B%5D=1021&place%5B%5D=1022&place%5B%5D=1023&place%5B%5D=1024&place%5B%5D=1025&place%5B%5D=1026&place%5B%5D=1037&place%5B%5D=1041&place%5B%5D=2027&place%5B%5D=2028&place%5B%5D=2029&place%5B%5D=2030&place%5B%5D=2033&place%5B%5D=2034&place%5B%5D=2035&place%5B%5D=2036&place%5B%5D=2038&place%5B%5D=2039&place%5B%5D=2040&place%5B%5D=2042&place%5B%5D=2043&place%5B%5D=2044&debtor=&au=&org=&stop=&pp_1=&pp_2=&st_1=&st_2=&sz_1=&sz_2=&ez_1=&ez_2=&et_1=&et_2=&parent_cat=2%2C4%2C10&sub_cat=4%2C26%2C27%2C28%2C29&spec_search=1&spec_type=&show_period=all&mark=&pattern_name=Долгожданная+покупка"

BATCH_SIZE = 5
MAX_PRICE = 200_000

BAD_WORDS = [
    "доля", "доли", "долевая", "долевое", "1/2", "1/3", "1/4", "1/5",
    "1/6", "1/7", "1/8", "1/10", "1/100", "1/1000",
    "квартира", "жилой дом", "жилое помещение", "комната",
    "земельный участок", "земли", "участок", "садовый дом",
    "дача", "садовый участок", "снт",
    "иной объект",
]

AUTO_WORDS = [
    "автомобиль", "машина", "легковой", "грузовой",
    "мотоцикл", "мотороллер", "транспортное средство",
    "фургон", "прицеп", "полуприцеп", "автобус", "тягач",
    "квадроцикл", "снегоход",
]


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
        return "🔥 СВЕЖИЙ"

    min_price = get_min_price(full_text)
    if min_price and current_price:
        if current_price <= min_price * 1.15:
            return "💰 НА ДНЕ"

    return "➖ СЕРЕДИНА"


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
    Ты — аналитик по банкротным торгам. Проанализируй лот:
    Ссылка: {lot_data['url']}
    Название: {lot_data['title']}
    Цена: {lot_data['price']}
    {extra_context}
    Текст страницы (фрагмент): {lot_data['full_text']}

    Цель клиента: купить дёшево → продать быстро (4–6 недель).
    Берём ТМЦ, оборудование, инструмент, стройматериалы, небольшую недвижку (гараж, кладовка).
    НЕ берём: авто, доли, квартиры, дома, участки.

    Проверь по чек-листу рисков (залог, запреты, долги).
    Предложи точку входа и предварительную маржу.
    Ответ дай кратко, по пунктам.
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


def main():
    processed = get_processed_ids()
    options = Options()
    options.binary_location = YANDEX_BROWSER_PATH
    service = Service(executable_path=YANDEXDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    try:
        print("Открываем Т-Банкрот...")
        driver.get("https://tbankrot.ru/")
        time.sleep(3)

        cookies_loaded = load_cookies(driver)
        if cookies_loaded:
            print("✅ Куки загружены. Проверь — залогинен ли ты?")
        else:
            print("Куки не найдены.")

        driver.maximize_window()
        print(">>> Окно развёрнуто. У тебя 30 секунд осмотреться <<<")
        print("    Если НЕ залогинен — залогинься сейчас (логин, пароль, СМС).")
        time.sleep(30)

        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()

        if "войти" in page_text[:3000] or "зарегистрироваться" in page_text[:3000]:
            print("⚠️ Не залогинен. У тебя 180 секунд на вход...")
            time.sleep(180)
            save_cookies(driver)
        else:
            print("✅ Уже залогинен. Идём дальше.")
            if not cookies_loaded:
                save_cookies(driver)

        driver.get(FILTER_URL)
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

                    bad, reason = is_bad_lot(
                        lot_data['title'],
                        lot_data['full_text'],
                        lot_data['price']
                    )
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
                    old_price_str, old_date = find_in_watchlist(lot_data['title'])
                    if old_price_str:
                        repeat_count += 1
                        old_price = parse_price(old_price_str)
                        diff_str = ""
                        if old_price and current_price:
                            diff_pct = (current_price - old_price) / old_price * 100
                            diff_str = f" (было {old_price:.0f} ₽ → стало {current_price:.0f} ₽, изменение {diff_pct:+.1f}%)"

                        print(f"⚠️ ПОВТОРНЫЙ лот (был в watch-list {old_date}){diff_str}")
                        extra_context = f"⚠️ ЭТО ПОВТОРНЫЙ ЛОТ. Ранее был в watch-list от {old_date} с ценой {old_price_str}.{diff_str} Учти это в анализе — стоит ли брать сейчас или причина несостоявшихся торгов сохранилась."

                    print(f"Приоритет: {priority}")
                    print(f"Цена: {lot_data['price']}")
                    print("Отправляем в DeepSeek...")

                    analysis = analyze_with_deepseek(lot_data, extra_context)
                    print(f"### Анализ ({priority}):")
                    print(analysis)
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
