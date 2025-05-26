const en = {
  open: "Open chat",
  close: "Close chat",
  placeholder: "Ask a question",
  send: "Send",
  sources: "Sources",
  talkToPerson: "Talk to a person",
  leaveContact: "Leave my contact",
  helpful: "Helpful",
  notHelpful: "Not helpful",
  thanks: "Thanks for the feedback",
  waiting: "Waiting for a manager",
  joined: "{name} is in the chat",
  managerLabel: "Manager",
  yourName: "Your name",
  contact: "Telegram, phone or email",
  question: "What do you need help with?",
  sendRequest: "Send request",
  cancel: "Cancel",
  formTitle: "We'll get back to you",
  error: "Something went wrong. Please try again.",
  rateLimited: "You're sending messages too fast. Wait a minute and try again.",
  poweredBy: "Answers come from {site}'s own pages",
  newMessage: "New reply",
} as const;

type Key = keyof typeof en;

const ru: Record<Key, string> = {
  open: "Открыть чат",
  close: "Закрыть чат",
  placeholder: "Задайте вопрос",
  send: "Отправить",
  sources: "Источники",
  talkToPerson: "Позвать человека",
  leaveContact: "Оставить контакт",
  helpful: "Полезно",
  notHelpful: "Не помогло",
  thanks: "Спасибо за оценку",
  waiting: "Ждём менеджера",
  joined: "{name} в чате",
  managerLabel: "Менеджер",
  yourName: "Как вас зовут",
  contact: "Telegram, телефон или почта",
  question: "С чем помочь?",
  sendRequest: "Отправить заявку",
  cancel: "Отмена",
  formTitle: "Мы с вами свяжемся",
  error: "Что-то пошло не так. Попробуйте ещё раз.",
  rateLimited: "Слишком много сообщений подряд. Подождите минуту.",
  poweredBy: "Ответы берутся с сайта {site}",
  newMessage: "Новый ответ",
};

export type Lang = "en" | "ru";
export type Translate = (key: Key, values?: Record<string, string>) => string;

export function pickLanguage(setting: "auto" | Lang, browser: string | undefined): Lang {
  if (setting !== "auto") return setting;
  return browser?.toLowerCase().startsWith("ru") ? "ru" : "en";
}

export function translator(lang: Lang): Translate {
  const table = lang === "ru" ? ru : en;
  return (key, values = {}) =>
    table[key].replace(/\{(\w+)\}/g, (_, name: string) => values[name] ?? `{${name}}`);
}
