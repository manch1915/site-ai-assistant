"""Sample traffic for the demo shop, so the inbox and analytics aren't empty on first visit."""

from dataclasses import dataclass

PRICES = "prices"
HOME = "index"
WARRANTY = "warranty"
ABOUT = "about"
PRICE_LIST = "price-list"


@dataclass(frozen=True, slots=True)
class Exchange:
    question: str
    answer: str
    page: str
    language: str = "en"


ANSWERED = [
    Exchange(
        "How much is an iPhone 15 screen?",
        "An iPhone 15 screen replacement is €189 with an original display. It takes about an "
        "hour when the part is in stock [1].",
        PRICES,
    ),
    Exchange(
        "do you replace macbook air batteries",
        "Yes. A MacBook Air M1 or M2 battery costs €169 and is usually done the same day. A "
        "MacBook Pro 14 battery is €229 and takes one working day [1].",
        PRICES,
    ),
    Exchange(
        "Do I need to book an appointment?",
        "No, you can just walk in. Booking a slot online only guarantees that a technician is "
        "free when you arrive [1].",
        HOME,
    ),
    Exchange(
        "What time do you open on Saturday?",
        "On Saturdays we're open from 11:00 to 17:00. Monday to Friday it's 10:00 to 19:00, and "
        "we're closed on Sundays [1].",
        HOME,
    ),
    Exchange(
        "how long is the warranty on a new battery",
        "Batteries come with a twelve month warranty. Other repairs are covered for six months "
        "on parts and labour [1].",
        WARRANTY,
    ),
    Exchange(
        "Can a courier pick up my laptop from the office?",
        "Yes, a courier can collect it anywhere in Lisbon for €10 each way. It's free for laptop "
        "repairs over €150, and pickups booked before 15:00 happen the same day [1].",
        ABOUT,
    ),
    Exchange(
        "Is the diagnostic free?",
        "It's free if you go ahead with the repair. Otherwise diagnostics cost €15 for phones and "
        "tablets and €25 for laptops and consoles [1].",
        PRICES,
    ),
    Exchange(
        "my switch joycon keeps drifting, can you fix it?",
        "Yes, we fix Joy-Con drift for €29 per controller. It takes about 30 minutes [1].",
        PRICES,
    ),
    Exchange(
        "Do you need my phone passcode?",
        "For most screen and battery repairs, no. If the phone doesn't start properly we may ask "
        "for it to test the device, and you can change it after pickup [1].",
        WARRANTY,
    ),
    Exchange(
        "can I pay with MB Way?",
        "Yes. You pay at pickup by card, MB Way or cash [1].",
        WARRANTY,
    ),
    Exchange(
        "Do you use original Apple screens?",
        "We fit original parts where manufacturers sell them to independent shops. For older "
        "models you can choose a certified aftermarket screen for 20 to 30 percent less, with "
        "the same warranty [1].",
        WARRANTY,
    ),
    Exchange(
        "Can you replace Face ID?",
        "No. Face ID modules are paired to the phone's board, so only Apple can replace them. We "
        "can still check what's wrong and tell you what Apple is likely to charge [1].",
        WARRANTY,
    ),
    Exchange(
        "Do you have business rates for our office laptops?",
        "Yes. Companies with five or more devices can open a business account: 15% off labour, "
        "priority repairs, a free loan laptop and one invoice a month with VAT [1].",
        PRICE_LIST,
    ),
    Exchange(
        "Сколько стоит замена батареи на iPhone 13?",
        "Замена батареи на iPhone 11 и новее стоит от €79 до €99 и занимает около 45 минут [1].",
        PRICES,
        "ru",
    ),
    Exchange(
        "Вы работаете в воскресенье?",
        "В воскресенье и праздники мы закрыты. В будни открыто с 10:00 до 19:00, в субботу с "
        "11:00 до 17:00 [1].",
        HOME,
        "ru",
    ),
    Exchange(
        "Есть скидка для студентов?",
        "Да, студентам скидка 10% на работу при предъявлении студенческого билета [1].",
        PRICES,
        "ru",
    ),
]

# Questions the shop's pages don't answer. They end up in "Knowledge gaps".
UNANSWERED = [
    ("Do you buy used phones?", "en", 7),
    ("Can you fix an Apple Watch screen?", "en", 6),
    ("Can you repair a DJI drone?", "en", 5),
    ("Do you sell gift cards?", "en", 4),
    ("Вы продаёте восстановленные айфоны?", "ru", 3),
    ("Do you fix electric scooters?", "en", 2),
]

HANDOFFS = [
    (
        "We have 12 laptops at our coworking that need new batteries. Can someone call me "
        "about a quote?",
        "Thanks for writing! For 12 laptops I'd suggest a business account: 15% off labour and "
        "a free loan laptop. Send me the models and I'll put a quote together today. Inês",
    ),
    (
        "My MacBook got coffee spilled on it this morning and won't turn on. What should I do?",
        "Please don't try to charge it. Bring it in today if you can and Marta will open it up "
        "first thing. Water damage treatment is €49. Inês",
    ),
    (
        "Мне нужно срочно поменять экран до пятницы, деталь есть в наличии?",
        "Здравствуйте! Для какой модели? Если это iPhone 14 или 15, экраны есть на складе, "
        "приходите в любое время до 18:00. Inês",
    ),
]

LEADS = [
    ("Ana Ribeiro", "ana.ribeiro@example.com", "Quote for 8 office laptops, battery and cleaning"),
    ("Tom Baker", "tom.baker@example.com", "Can you fix an Apple Watch Series 8 screen?"),
    ("Marina Kovaleva", "marina.k@example.com", "Нужна замена экрана на Pixel 8, когда можно?"),
    ("João Ferreira", "joao.ferreira@example.com", "Drone gimbal repair, DJI Mini 3"),
    ("Sofia Martins", "sofia.martins@example.com", "Business account for our school, 30 iPads"),
    ("Lukas Weber", "lukas.weber@example.com", "Water damage, iPhone 14 Pro"),
]
