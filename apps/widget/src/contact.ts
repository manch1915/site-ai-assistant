// Same rules as the server: a Telegram username, a phone number or an email.
const EMAIL = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;
const TELEGRAM = /^@[A-Za-z][A-Za-z0-9_]{4,31}$/;
const TELEGRAM_LINK = /^(?:https?:\/\/)?t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?$/i;
const PHONE = /^\+?\d{7,15}$/;

export function isValidContact(raw: string): boolean {
  const text = raw.trim();
  return (
    EMAIL.test(text) ||
    TELEGRAM.test(text) ||
    TELEGRAM_LINK.test(text) ||
    PHONE.test(text.replace(/[\s\-().]/g, ""))
  );
}
