"""Canned replies the widget shows without calling the model."""

_REPLIES: dict[str, dict[str, str]] = {
    "no_answer": {
        "en": (
            "I couldn't find a reliable answer to that in {site}'s materials, and I'd rather not "
            "guess. I can pass your question to a manager, or you can leave a contact and "
            "they'll get back to you."
        ),
        "ru": (
            "В материалах {site} нет точного ответа на этот вопрос, а гадать я не хочу. "
            "Могу передать вопрос менеджеру или оставьте контакт, вам ответят."
        ),
    },
    "quote_intro": {
        "en": "Here's what I found in {site}'s materials:",
        "ru": "Вот что нашёл в материалах {site}:",
    },
    "handoff_waiting": {
        "en": "I've passed the conversation to a manager. They usually reply within a few "
        "minutes during working hours, right here in this chat.",
        "ru": "Передал диалог менеджеру. В рабочее время он обычно отвечает за несколько минут, "
        "прямо здесь, в этом чате.",
    },
    "handoff_unavailable": {
        "en": "Managers aren't connected to this chat yet. Leave your contact and we'll get back "
        "to you.",
        "ru": "Менеджеры пока не подключены к чату. Оставьте контакт, и с вами свяжутся.",
    },
    "lead_saved": {
        "en": "Thanks, {name}. Your request is saved and a manager will contact you.",
        "ru": "Спасибо, {name}. Заявка сохранена, менеджер свяжется с вами.",
    },
    "closed": {
        "en": "The manager closed this conversation. You can keep asking me questions.",
        "ru": "Менеджер завершил диалог. Можете и дальше задавать вопросы мне.",
    },
}


def reply(key: str, language: str, **values: str) -> str:
    variants = _REPLIES[key]
    template = variants.get(language, variants["en"])
    return template.format(**values)
