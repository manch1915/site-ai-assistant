"""Questions for checking the confidence threshold against the demo shop.

`python -m app.cli calibrate` prints the confidence for each one and how many land on the
right side of the site's threshold.
"""

ANSWERABLE = [
    "how much for a new screen on iphone 15",
    "price of a galaxy s24 display",
    "Pixel 8 screen cost",
    "how long does a battery swap take",
    "are you open on saturdays",
    "what are your hours",
    "where is the shop",
    "do i have to book first",
    "can i walk in without an appointment",
    "is diagnostics free",
    "warranty on repairs",
    "do you use genuine parts",
    "will you look at my photos",
    "can you collect my laptop from home",
    "student discount?",
    "do you fix ps5 hdmi port",
    "my joycons drift",
    "how do i pay",
    "do you do invoices for companies",
    "water damage on my phone, what now",
    "Сколько стоит замена экрана на iPhone 14?",
    "Во сколько вы открываетесь?",
    "Какая гарантия на батарею?",
    "Можно ли забрать ноутбук курьером?",
    "Нужна ли запись заранее?",
]

UNANSWERABLE = [
    "do you buy used phones",
    "can you fix my washing machine",
    "repair a DJI drone",
    "do you sell gift cards",
    "who won the football yesterday",
    "write me a poem about cats",
    "what's the capital of Australia",
    "can you unlock bootloader on my Xiaomi",
    "do you have a shop in Porto",
    "Вы ремонтируете холодильники?",
    "Какая погода в Лиссабоне?",
    "Продаёте ли вы чехлы?",
]
