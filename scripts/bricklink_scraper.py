# import re

# def process_article_file(filename="article.txt", output_filename="output.txt"):
#     """
#     Обрабатывает файл article.txt, извлекает информацию о фигурках, сохраняет уникальные значения в файл output.txt
#     в формате "артикул; minifig_name; длина", учитывая первое название до двоеточия, сортирует результат.

#     Args:
#         filename (str): Имя входного файла (по умолчанию "article.txt").
#         output_filename (Имя выходного файла (по умолчанию "output.txt").
#     """

#     results = set()  # Используем set для хранения уникальных данных

#     try:
#         with open(filename, "r", encoding="utf-8") as f:
#             for line in f:
#                 line = line.strip()
#                 if not line:  # Пропускаем пустые строки
#                     continue

#                 try:
#                     parts = line.split("|")
#                     if len(parts) != 2:  # Проверка на корректное количество частей
#                         print(f"Предупреждение: Некорректный формат строки: {line}")
#                         continue

#                     article_id = parts[0]
#                     description = parts[1]

#                     # Извлечение minifig_name
#                     catalog_split = description.split("Catalog:")
#                     if len(catalog_split) > 1:
#                         minifig_name_section = catalog_split[1]
#                         minifig_name_match = re.search(r"Minifigures:(.*)", minifig_name_section)
#                         if minifig_name_match:
#                             full_minifig_name = minifig_name_match.group(1).strip()
#                             # Разделяем имя по двоеточию и берем первую часть
#                             minifig_name = full_minifig_name.split(":")[0].strip()
#                         else:
#                             print(f"Предупреждение: Не удалось извлечь minifig_name из строки: {line}")
#                             continue
#                     else:
#                         print(f"Предупреждение: Отсутствует 'Catalog:' в строке: {line}")
#                         continue


#                     # Вычисление длины артикула (числовой части)
#                     # Разбиваем артикул на префикс и номер, предполагая, что номер состоит только из цифр
#                     match = re.match(r"([a-zA-Z]+)(\d+)", article_id)
#                     if match:
#                         prefix = match.group(1)
#                         number = match.group(2)
#                         length = len(number)
#                     else:
#                         print(f"Предупреждение: Не удалось разделить артикул на префикс и номер: {article_id}")
#                         continue


#                     # Формируем строку результата
#                     result_string = f"{prefix};{minifig_name};{length}"

#                     # Добавляем строку в set (автоматически обеспечивает уникальность)
#                     results.add(result_string)



#                 except Exception as e:
#                     print(f"Ошибка при обработке строки: {line}. Ошибка: {e}")

#     except FileNotFoundError:
#         print(f"Ошибка: Файл {filename} не найден.")
#         return
#     except Exception as e:
#         print(f"Общая ошибка при чтении/обработке файла: {e}")
#         return

#     # Сортируем результаты
#     sorted_results = sorted(list(results))

#     # Запись результатов в файл
#     try:
#         with open(output_filename, "w", encoding="utf-8") as outfile:
#             for result in sorted_results:
#                 outfile.write(result + "\n")
#         print(f"Данные успешно записаны в файл {output_filename}")
#     except Exception as e:
#         print(f"Ошибка при записи в файл: {e}")


# # Пример использования:
# process_article_file()  # Использует article.txt и output.txt по умолчанию
# # process_article_file("my_articles.txt", "my_output.txt")  # Можно указать другие имена файлов

# # import requests
# # from bs4 import BeautifulSoup
# # from urllib.parse import urljoin, parse_qs, urlparse
# # import time
# # import os

# # # --- Настройки ---
# # BASE_URL = "https://www.bricklink.com"
# # START_URL = urljoin(BASE_URL, "/catalogTree.asp?itemType=M")
# # HEADERS = {
# #     "User-Agent": (
# #         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
# #         "AppleWebKit/537.36 (KHTML, like Gecko) "
# #         "Chrome/115.0.0.0 Safari/537.36"
# #     ),
# #     "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
# # }
# # COOKIES = {
# #     "ASPSESSIONIDQSARSBAC": "JDHCEIEAHIFDPCLOCKNDFBGB",
# #     "ASPSESSIONIDSSDSSDCB": "EDLOBIEAHGIDADJFFPDKFMHB",
# #     "AWSALB": "JUtCl/QGV6EOkjSKwmGOwnIslcjincEn7C6+wkRMQSatN00npMiLMNaMeJsbo6+DzJZ+1RQ7TT85dBHTsYNZ8vouBIoCbausRPzFonJaVkL79TYTmGJhKpxtkJ6+",
# #     "AWSALBCORS": "JUtCl/QGV6EOkjSKwmGOwnIslcjincEn7C6+wkRMQSatN00npMiLMNaMeJsbo6+DzJZ+1RQ7TT85dBHTsYNZ8vouBIoCbausRPzFonJaVkL79TYTmGJhKpxtkJ6+",
# #     "BLHASTOKEN": "1",
# #     "BLNEWSESSIONID": "V10BE394A6851615A0B4CB63B0435B24D90C51E098E654EBFA2D31D0DD464968CBE8C8BA8D7048AF5AFB733F7571B1FA1A6",
# #     "blCartBuyerID": "-887092228",
# #     "aws-waf-token": "5315ebe8-0716-4557-8a51-74ba0b8f1ab3:EQoAigdJVlNWAAAA:LwMtTvC2YOkddNOQLau8pkHQR/7QqJBpMyJW5xWZsTtOu3qtDPC+cZdkVoQu48A/iKpfCOgrYc0lWZYsO0j93AoG3FGe5/U9Hh7Wn7lqajc4U5CDsYCk95fWj5cz9emL9rIHXLw+CLDHA+uR/59UNxp/ZfzjLfUrqHD/wsjTy7KtNYzddcnG7cRfrO++2+OvugAdrfoBaqx+FWTxLRyzJ3zL0tZeC3Jm2d/0RW0jV3gIUkKwIuV7yekauHR2ztJa9op1FoOkxyY="
# # }
# # OUTPUT_FILE = "output.txt"
# # DELAY = 1.0  # пауза между запросами, в секундах

# # # --- Функции для сохранения и загрузки уже записанных элементов ---
# # def load_seen():
# #     seen = set()
# #     if os.path.exists(OUTPUT_FILE):
# #         with open(OUTPUT_FILE, encoding="utf-8") as f:
# #             for line in f:
# #                 seen.add(line.strip())
# #     return seen

# # def save_items(items):
# #     with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
# #         for it in items:
# #             f.write(it + "\n")

# # # --- HTTP + парсинг страницы ---
# # def get_soup(url, params=None):
# #     resp = requests.get(url, headers=HEADERS, cookies=COOKIES, params=params, timeout=10)
# #     resp.raise_for_status()
# #     return BeautifulSoup(resp.text, "lxml")

# # # --- Основной процесс ---
# # def main():
# #     seen = load_seen()

# #     print("Загружаем главную страницу…")
# #     soup = get_soup(START_URL)
# #     subcats = set()
# #     for a in soup.select("a[href^='/catalogList.asp']"):
# #         subcats.add(urljoin(BASE_URL, a["href"]))
# #     print(f"Найдено {len(subcats)} подкатегорий.")

# #     for base_cat in subcats:
# #         print(f"\n=== Обработка {base_cat} ===")
# #         page = 1

# #         while True:
# #             parsed = urlparse(base_cat)
# #             qs = parse_qs(parsed.query)
# #             qs["pg"] = [str(page)]
# #             new_query = "&".join(f"{k}={v[0]}" for k, v in qs.items())
# #             url = parsed._replace(query=new_query).geturl()

# #             print(f" Страница {page}: {url}")
# #             try:
# #                 soup = get_soup(url)
# #             except Exception as e:
# #                 print("  Ошибка загрузки:", e)
# #                 break

# #             form = soup.select_one("form#ItemEditForm")
# #             if not form:
# #                 print("  Не найдена форма ItemEditForm — прерываем.")
# #                 break

# #             rows = form.select("table.catalog-list__body-main tr")
# #             if len(rows) <= 1:
# #                 print("  Нет записей на странице.")
# #                 break

# #             new_items = []
# #             for tr in rows[1:]:
# #                 link = tr.select_one("td:nth-of-type(2) a[href*='/v2/catalog/catalogitem.page']")
# #                 if link:
# #                     code = link.get_text(strip=True)
# #                     if code and code not in seen:
# #                         new_items.append(code)
# #                         seen.add(code)

# #             if new_items:
# #                 save_items(new_items)
# #                 print(f"  Добавлено {len(new_items)} новых Item No.")
# #             else:
# #                 print("  Новых Item No. не найдено.")

# #             next_btn = soup.find("a", string="Next")
# #             if not next_btn or "disabled" in next_btn.get("class", []):
# #                 print("  Дальше страниц нет — переходим к следующей категории.")
# #                 break

# #             page += 1
# #             time.sleep(DELAY)

# #     print("\nВсе категории обработаны. Результат в", OUTPUT_FILE)

# # if __name__ == "__main__":
# #     main()


# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# Скрипт для парсинга файла с кодами:
# - Сортирует все строки файла
# - Извлекает уникальные артикли (буквенная часть перед цифрами)
# - Записывает список уникальных артиклей в article.txt
# - Записывает строки, не соответствующие шаблону, в failed.txt
# """
# import re

# # --- Настройки ---
# INPUT_FILE = "output.txt"     # исходный файл с кодами
# ARTICLE_FILE = "article.txt"  # файл для уникальных артиклей
# FAILED_FILE = "failed.txt"    # файл для несоответствующих строк

# # --- Чтение и сортировка ---
# with open(INPUT_FILE, encoding="utf-8") as f:
#     lines = [line.strip() for line in f if line.strip()]

# lines.sort()

# # --- Регулярное выражение для артикля: буквы+цифры ---
# pattern = re.compile(r"^([A-Za-z]+)(\d+)$")

# articles = set()
# failed = []

# # --- Обработка строк ---
# for line in lines:
#     m = pattern.match(line)
#     if m:
#         prefix = m.group(1)
#         articles.add(prefix)
#     else:
#         failed.append(line)

# # --- Запись уникальных артиклей ---
# with open(ARTICLE_FILE, "w", encoding="utf-8") as f:
#     for art in sorted(articles):
#         f.write(f"{art}\n")

# # --- Запись несоответствующих строк ---
# with open(FAILED_FILE, "w", encoding="utf-8") as f:
#     for item in failed:
#         f.write(f"{item}\n")

# print(f"Уникальных артиклей: {len(articles)}, сохранено в '{ARTICLE_FILE}'")
# print(f"Несоответствующих строк: {len(failed)}, сохранено в '{FAILED_FILE}'")

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse
import time
import os
import re

# --- Настройки ---
BASE_URL      = "https://www.bricklink.com"
START_URL     = urljoin(BASE_URL, "/catalogTree.asp?itemType=M")
HEADERS       = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}
COOKIES = {
    "_pk_id.12.23af":      "e9e71214ea6558f6.1741544960.",
    "_pk_ref.12.23af":     "%5B%22%22%2C%22%22%2C1752783486%2C%22https%3A%2F%2Fwww.google.com%2F%22%5D",
    "_pk_ses.12.23af":     "1",
    "_sp_id.8289":         ".1741544959.14.1752784119.1752768259.8b772279-b46e-4135-840c-e3b9134454d2..2c349467-6c20-43d5-b95a-20ccdc14a895.1752783493172.5",
    "_sp_ses.8289":        "*",
    "adcloud":             "{\"_les_v\":\"c%2Cy%2Clego.com%2C1741547255\"}",
    "AGE_GATE":            "grown_up",
    "AMCV_FCD5E69B53FDC29C0A4C98A7%40AdobeOrg": (
        "179643557%7CMCIDTS%7C20157%7CMCMID%7C04521520882813082912174168391284569704"
        "%7CMCAAMLH-1742150254%7C6%7CMCAAMB-1742150254%7CRKhpRz8krg2tLO6pguXWp5olkAcUni"
        "QYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1741552654s%7CNONE%7CvVersion%7C5.5.0"
    ),
    "ASPSESSIONIDQSARSBAC": "EJOOFIEAEGHDCGGDDONCOLDL",
    "ASPSESSIONIDSSDSSDCB": "KBPCCIEABPBKMMIHEJEMOOCG",
    "AWSALB":               "xm/eU3+aiChhgxdZVF7/ZaiiXPe9Jssvjxkvia0BBWs+b/Uoi/dRNBn+BY879IirM6GRJ02pLC93h5Am3dnR/j9hoyq02acH8ZJ3cJTzSxg0Cxwp434n5CE93Fcz",
    "AWSALBCORS":           "xm/eU3+aiChhgxdZVF7/ZaiiXPe9Jssvjxkvia0BBWs+b/Uoi/dRNBn+BY879IirM6GRJ02pLC93h5Am3dnR/j9hoyq02acH8ZJ3cJTzSxg0Cxwp434n5CE93Fcz",
    "BLHASTOKEN":           "1",
    "BLNEWSESSIONID":       "V10BE394A6851615A0B4CB63B0435B24D90C51E098E654EBFA2D31D0DD464968CBE8C8BA8D7048AF5AFB733F7571B1FA1A6",
    "blCartBuyerID":        "-887092228",
    "aws-waf-token":        "5315ebe8-0716-4557-8a51-74ba0b8f1ab3:EQoAigdJVlNWAAAA:LwMtTvC2YOkddNOQLau8pkHQR/7QqJBpMyJW5xWZsTtOu3qtDPC+cZdkVoQu48A/iKpfCOgrYc0lWZYsO0j93AoG3FGe5/U9Hh7Wn7lqajc4U5CDsYCk95fWj5cz9emL9rIHXLw+CLDHA+uR/59UNxp/ZfzjLfUrqHD/wsjTy7KtNYzddcnG7cRfrO++2+OvugAdrfoBaqx+FWTxLRyzJ3zL0tZeC3Jm2d/0RW0jV3gIUkKwIuV7yekauHR2ztJa9op1FoOkxyY="
}

OUTPUT_FILE   = "output.txt"
ARTICLE_FILE  = "article.txt"
FAILED_FILE   = "failed.txt"
DELAY         = 1.0

# --- Инициализируем сессию с вашим лимитом редиректов ---
session = requests.Session()
session.headers.update(HEADERS)
session.cookies.update(COOKIES)
# Увеличим лимит перенаправлений
session.max_redirects = 60

def load_seen():
    seen = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            for line in f:
                seen.add(line.strip().split('|')[0])
    return seen

def save_items(items):
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for code, title in items:
            f.write(f"{code}|{title}\n")

def get_soup(url, params=None):
    # Теперь используем session.get — он уважает session.max_redirects
    resp = session.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")

def scrape():
    seen = load_seen()
    print("Загружаем главную страницу…")
    try:
        soup = get_soup(START_URL)
    except requests.exceptions.TooManyRedirects:
        print("Слишком много редиректов на стартовой странице. Увеличьте session.max_redirects или проверьте START_URL.")
        return

    subcats = {
        urljoin(BASE_URL, a["href"])
        for a in soup.select("a[href^='/catalogList.asp']")
    }
    print(f"Найдено {len(subcats)} подкатегорий.")

    for base_cat in subcats:
        print(f"\n=== Обработка {base_cat} ===")
        page = 1

        while True:
            parsed = urlparse(base_cat)
            qs = parse_qs(parsed.query)
            qs["pg"] = [str(page)]
            new_query = "&".join(f"{k}={v[0]}" for k, v in qs.items())
            url = parsed._replace(query=new_query).geturl()

            print(f" Страница {page}: {url}")
            try:
                soup = get_soup(url)
            except requests.exceptions.TooManyRedirects:
                print("  Слишком много редиректов — пропускаем эту категорию.")
                break
            except Exception as e:
                print("  Ошибка загрузки:", e)
                break

            form = soup.select_one("form#ItemEditForm")
            if not form:
                print("  Не найдена форма ItemEditForm — прерываем.")
                break

            rows = form.select("table.catalog-list__body-main tr")
            if len(rows) <= 1:
                print("  Нет записей на странице.")
                break

            new_items = []
            for tr in rows[1:]:
                link = tr.select_one("td:nth-of-type(2) a[href*='/v2/catalog/catalogitem.page']")
                title_tag = tr.select_one("td:nth-of-type(3)")
                if link and title_tag:
                    code = link.get_text(strip=True)
                    title = title_tag.get_text(strip=True)
                    if code and code not in seen:
                        new_items.append((code, title))
                        seen.add(code)

            if new_items:
                save_items(new_items)
                print(f"  Добавлено {len(new_items)} новых позиций.")
            else:
                print("  Новых позиций не найдено.")

            next_btn = soup.find("a", string="Next")
            if not next_btn or "disabled" in next_btn.get("class", []):
                print("  Дальше страниц нет — переходим к следующей категории.")
                break

            page += 1
            time.sleep(DELAY)

    print("\nСбор данных завершён. Результат в", OUTPUT_FILE)

def postprocess():
    if not os.path.exists(OUTPUT_FILE):
        print("Файл", OUTPUT_FILE, "не найден.")
        return

    with open(OUTPUT_FILE, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    lines.sort(key=lambda x: x.split('|')[0])

    pattern = re.compile(r"^[A-Za-z]+\d+\|.+$")
    valid, failed = [], []

    for line in lines:
        if pattern.match(line):
            valid.append(line)
        else:
            failed.append(line)

    with open(ARTICLE_FILE, "w", encoding="utf-8") as f:
        for item in valid:
            f.write(item + "\n")

    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        for item in failed:
            f.write(item + "\n")

    print(f"Итоговых позиций: {len(valid)} → {ARTICLE_FILE}")
    print(f"Несоответствий: {len(failed)} → {FAILED_FILE}")

if __name__ == "__main__":
    scrape()
    postprocess()
