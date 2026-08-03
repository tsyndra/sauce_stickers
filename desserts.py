"""Dessert catalog for round defrost labels."""

from __future__ import annotations

from datetime import timedelta

BRAND = "HATIMAKI"
DEFAULT_STORAGE = "Хранить при t +2…+6 °C"

# Branch legal entities shown at the bottom of dessert labels.
LEGAL_ENTITIES = [
    "ИП Агафонов В.В.",
    "ИП Агафонов И.В.",
    "ИП Дьякова О.В.",
    "ИП Ермакова Ю.А.",
    "ИП Зайцев Е.А.",
    "ИП Леви Ю.В.",
    "ИП Мирная Е.А.",
    "ИП Назарова С.Р.",
    "ИП Сорокина С.Н.",
    "ИП Степанов А.В.",
    "ИП Стригина Д.Р.",
    "ИП Чуканова Л.И.",
]

DESSERTS = {
    "mango_passion": {
        "button": "Манго — маракуйя",
        "label_title": "ПИРОЖНОЕ «МАНГО — МАРАКУЙЯ»",
        "shelf_life": timedelta(hours=72),
        "storage": DEFAULT_STORAGE,
    },
    "three_chocolates": {
        "button": "Чизкейк Три шоколада",
        "label_title": "ТОРТ «ЧИЗКЕЙК ТРИ ШОКОЛАДА»",
        "shelf_life": timedelta(days=5),
        "storage": DEFAULT_STORAGE,
    },
    "caramel_cheesecake": {
        "button": "Чизкейк Карамельный",
        "label_title": "ТОРТ «ЧИЗКЕЙК КАРАМЕЛЬНЫЙ»",
        "shelf_life": timedelta(days=7),
        "storage": DEFAULT_STORAGE,
    },
    "pistachio_raspberry": {
        "button": "Фисташковый с малиной",
        "label_title": "ТОРТ «ФИСТАШКОВЫЙ С МАЛИНОЙ»",
        "shelf_life": timedelta(hours=72),
        "storage": DEFAULT_STORAGE,
    },
    "raspberry_cheesecake": {
        "button": "Чизкейк Малиновый",
        "label_title": "ТОРТ «ЧИЗКЕЙК МАЛИНОВЫЙ»",
        "shelf_life": timedelta(days=7),
        "storage": DEFAULT_STORAGE,
    },
    "dubai_chocolate": {
        "button": "Дубайский шоколад",
        "label_title": "ТОРТ «ДУБАЙСКИЙ ШОКОЛАД»",
        "shelf_life": timedelta(days=5),
        "storage": DEFAULT_STORAGE,
    },
    "raspberry_tartlet": {
        "button": "Тарталетка Малиновая",
        "label_title": "ПИРОЖНОЕ «ТАРТАЛЕТКА МАЛИНОВАЯ»",
        "shelf_life": timedelta(hours=24),
        "storage": DEFAULT_STORAGE,
    },
    "tiramisu": {
        "button": "Тирамису Маскарпоне",
        "label_title": "ПИРОЖНОЕ «ТИРАМИСУ МАСКАРПОНЕ»",
        "shelf_life": timedelta(hours=48),
        "storage": "Хранить при t +4 °C",
    },
}
