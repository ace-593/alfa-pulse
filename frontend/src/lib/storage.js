export function readStore(userId, key, fallback) {
  try {
    return (
      JSON.parse(localStorage.getItem(`pulse:${userId}:${key}`)) ?? fallback
    );
  } catch {
    return fallback;
  }
}
export function writeStore(userId, key, value) {
  try {
    localStorage.setItem(`pulse:${userId}:${key}`, JSON.stringify(value));
  } catch {
    /* Browsers may disable persistence. The interface remains usable. */
  }
}
export function safeUrl(url) {
  try {
    const parsed = new URL(url);
    return ["https:", "http:"].includes(parsed.protocol) ? parsed.href : null;
  } catch {
    return null;
  }
}
export function formatDate(value) {
  if (!value || Number.isNaN(new Date(value).getTime()))
    return "Дата не указана";
  return new Intl.DateTimeFormat("ru", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Moscow",
  }).format(new Date(value));
}
export function plural(count, forms) {
  const n = Math.abs(count);
  return forms[
    n % 100 >= 11 && n % 100 <= 14
      ? 2
      : n % 10 === 1
        ? 0
        : n % 10 >= 2 && n % 10 <= 4
          ? 1
          : 2
  ];
}
