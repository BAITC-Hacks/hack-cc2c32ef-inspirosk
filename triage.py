#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Разбор обращений: категория (справка / жалоба / другое) + черновик ответа.

Запуск:
    python3 triage.py                 # читает messages.txt
    python3 triage.py my.txt          # другой файл
    python3 triage.py --json          # машиночитаемый вывод
"""

import json
import re
import sys

DEFAULT_FILE = "messages.txt"

# --- Правила категорий -------------------------------------------------------
# Каждое правило: (регулярка по основе слова, вес). Побеждает категория с
# наибольшей суммой весов; при нуле или ничьей — "другое".
RULES = {
    "жалоба": [
        (r"пропал|не работает|не раб|сломал|отключил", 3),
        (r"очеред|холодн|грязн|шум|духот|протека", 3),
        (r"жалоб|возмущ|безобраз|ужасн|отвратит", 3),
        (r"долго жду|уже неделю|никто не отвеч|хамств", 3),
        (r"не могу|не получается|не пуска", 2),
    ],
    "справка": [
        (r"справк|выписк|подтвержд|документ", 3),
        (r"как получить|как оформить|куда обратит|где взять", 3),
        (r"^где |^когда |^сколько |^какой |^какие ", 2),
        (r"режим работы|график работы|расписан", 2),
    ],
    "другое": [
        (r"записаться|запись на|хочу записать|назначьте|назначить", 3),
        (r"консультац|приём|прием|встреч", 1),
        (r"предлага|идея|спасибо|благодар", 2),
    ],
}

# --- Тематика: ответственная служба и конкретная строка для черновика --------
TOPICS = [
    (r"справк|место учёб|место учеб|обучен", {
        "service": "учебный отдел",
        "line": ("Справку о месте учёбы можно заказать в личном кабинете "
                 "(раздел «Справки») или в учебном отделе, каб. 105. "
                 "Срок подготовки — 3 рабочих дня."),
    }),
    (r"столов|еда|обед|буфет|питани", {
        "service": "службу питания",
        "line": ("Передали замечание по работе столовой: проверим график "
                 "раздачи в пиковые часы и температуру блюд на линии."),
    }),
    (r"wi-?fi|вайфай|интернет|сет[ьи]|пароль|доступ", {
        "service": "ИТ-службу",
        "line": ("ИТ-служба проверит точки доступа в указанном корпусе. "
                 "Как временное решение — сеть guest или проводное "
                 "подключение в читальном зале."),
    }),
    (r"записаться|запись|консультац|приём|прием", {
        "service": "приёмную",
        "line": ("Чтобы записать вас на консультацию, уточните, пожалуйста, "
                 "тему и удобное время — свободные слоты на завтра есть "
                 "с 10:00 до 16:00."),
    }),
    (r"парковк|машин|автомобил|пропуск", {
        "service": "службу эксплуатации",
        "line": ("Гостевая парковка — со стороны корпуса А, въезд по разовому "
                 "пропуску. Пропуск оформляет принимающая сторона на "
                 "ресепшене, достаточно номера автомобиля."),
    }),
]

TOPIC_DEFAULT = {
    "service": "профильную службу",
    "line": "Уточним детали по вашему вопросу и вернёмся с ответом.",
}


def classify(text):
    """Возвращает (категория, [сработавшие правила])."""
    low = text.lower()
    scores = {}
    hits = {}
    for category, rules in RULES.items():
        score = 0
        matched = []
        for pattern, weight in rules:
            found = re.search(pattern, low)
            if found:
                score += weight
                matched.append(found.group(0).strip())
        scores[category] = score
        hits[category] = matched

    best = max(scores, key=lambda c: scores[c])
    if scores[best] == 0 or list(scores.values()).count(scores[best]) > 1:
        return "другое", hits.get("другое", [])
    return best, hits[best]


def detect_topic(text):
    low = text.lower()
    for pattern, topic in TOPICS:
        if re.search(pattern, low):
            return topic
    return TOPIC_DEFAULT


def draft(text, category):
    topic = detect_topic(text)
    if category == "жалоба":
        return ("Здравствуйте! Спасибо, что сообщили о проблеме, — приносим "
                "извинения за неудобства. {line} Обращение передано в {service}; "
                "о результатах сообщим в течение 2 рабочих дней."
                ).format(**topic)
    if category == "справка":
        return ("Здравствуйте! Спасибо за обращение. {line} Если что-то "
                "осталось непонятным — ответьте на это сообщение, поможем."
                ).format(**topic)
    return ("Здравствуйте! Спасибо за обращение. {line} Запрос передан в "
            "{service} — подтверждение пришлём ответным сообщением."
            ).format(**topic)


def read_messages(path):
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    path = args[0] if args else DEFAULT_FILE

    try:
        messages = read_messages(path)
    except IOError as exc:
        print("Не удалось прочитать %s: %s" % (path, exc), file=sys.stderr)
        return 1

    results = []
    for text in messages:
        category, matched = classify(text)
        results.append({
            "message": text,
            "category": category,
            "matched_rules": matched,
            "reply": draft(text, category),
        })

    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    for i, item in enumerate(results, 1):
        why = ", ".join(item["matched_rules"]) or "нет явных признаков"
        print("[%d] %s" % (i, item["message"]))
        print("    Категория: %s (сработало: %s)" % (item["category"], why))
        print("    Черновик ответа: %s" % item["reply"])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
