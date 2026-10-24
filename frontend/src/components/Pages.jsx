import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { formatDate } from "../lib/storage.js";
import { Empty, Icon, Loading } from "./ui.jsx";

export function CompanyPage({ company: c, role, navigate }) {
  const fields = [
    ["Идентификатор", c.id],
    ["Отрасль", c.industry],
    ["ОКВЭД", c.okved],
    [
      "Выручка",
      c.revenue === null
        ? "Нет данных"
        : `${c.revenue.toLocaleString("ru")} млрд ₽`,
    ],
    ["Регион", c.region],
    ["Город", c.city],
    ["Сотрудники", c.workers],
    ["Группа компаний", c.group || "Не указана"],
    ["Внешнеторговые связи", c.countries.join(", ") || "Нет данных"],
  ];
  return (
    <>
      <p className="page-intro">
        Персонализация начинается с понимания вашего бизнеса.
      </p>
      <div className="profile-grid">
        <section className="panel">
          <div className="company-identity large">
            <span className="company-avatar">{c.initials}</span>
            <div>
              <h2>{c.name}</h2>
              <p>
                {c.synthetic
                  ? "Синтетический профиль компании"
                  : "Данные компании"}
              </p>
            </div>
          </div>
          <p className="profile-description">{c.description}</p>
          <dl className="profile-fields">
            {fields.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <div className="product-tags">
            {c.products.map((p) => (
              <span key={p}>{p}</span>
            ))}
          </div>
        </section>
        <section className="panel">
          <span className="eyebrow">ПЕРСОНАЛЬНЫЙ КОНТЕКСТ</span>
          <h2>Почему лента именно такая</h2>
          <p>
            Отбор событий учитывает вашу отрасль, банковские продукты, доступные
            признаки бизнеса и роль: <strong>{role.name}</strong>.
          </p>
          <div className="notice">
            <Icon name="help" />
            <div>
              <strong>Что пока неизвестно</strong>
              <p>
                Структура долга, валюты контрактов, доля рынка и платёжный
                календарь. Наличие кредитного продукта само по себе не
                определяет долговую нагрузку.
              </p>
            </div>
          </div>
          <p className="muted">
            Регион регистрации не означает все регионы присутствия. Страны ФТС
            не определяют направление операций.
          </p>
          <button className="button dark" onClick={() => navigate("feed")}>
            Открыть персональную ленту
            <Icon name="arrow" />
          </button>
        </section>
      </div>
    </>
  );
}
export function MethodPage() {
  const steps = [
    [
      "building",
      "Контекст компании",
      "Анализ учитывает признаки бизнеса и вашу роль. Неизвестные данные остаются неизвестными.",
    ],
    [
      "news",
      "Факты и источники",
      "Каждое событие опирается на материалы. Цитаты и первоисточники доступны в разборе.",
    ],
    [
      "spark",
      "Персональное влияние",
      "Риски, возможности и следующие шаги отделены от фактов и позиции банка.",
    ],
    [
      "shield",
      "Проверяемые основания",
      "Показываем ограничения, использованные материалы и этапы обработки.",
    ],
  ];
  return (
    <>
      <p className="page-intro">
        От события — к решению. С объяснением каждого шага.
      </p>
      <div className="method-grid">
        {steps.map(([icon, title, text], i) => (
          <section className="panel method-card" key={title}>
            <div className="method-card-top">
              <Icon name={icon} />
              <span>0{i + 1}</span>
            </div>
            <h2>{title}</h2>
            <p>{text}</p>
          </section>
        ))}
      </div>
      <section className="notice">
        <Icon name="help" />
        <div>
          <strong>Аналитика помогает задавать правильные вопросы</strong>
          <p>
            Количественный эффект не рассчитывается без необходимых данных. Если
            LLM не настроена или источников недостаточно, интерфейс показывает
            это явно.
          </p>
        </div>
      </section>
    </>
  );
}
export function HistoryPage({ companyId, restore, navigate }) {
  const [state, setState] = useState({ loading: true, items: [], error: "" });
  const [retry, setRetry] = useState(0);
  const [restoring, setRestoring] = useState("");
  const [restoreError, setRestoreError] = useState("");
  const [controller] = useState(() => new AbortController());
  useEffect(() => () => controller.abort(), [controller]);
  useEffect(() => {
    const request = new AbortController();
    setState({ loading: true, items: [], error: "" });
    api
      .getHistory(companyId, request.signal)
      .then((items) => {
        if (!request.signal.aborted)
          setState({ loading: false, items, error: "" });
      })
      .catch((error) => {
        if (!request.signal.aborted)
          setState({ loading: false, items: [], error: error.message });
      });
    return () => request.abort();
  }, [companyId, retry]);
  async function open(id) {
    if (restoring) return;
    setRestoring(id);
    setRestoreError("");
    try {
      const result = await api.restoreDigest(companyId, id, controller.signal);
      if (!controller.signal.aborted) {
        restore(result);
        navigate("feed");
      }
    } catch (error) {
      if (!controller.signal.aborted) setRestoreError(error.message);
    } finally {
      if (!controller.signal.aborted) setRestoring("");
    }
  }
  return (
    <>
      <p className="page-intro">
        Снимки аналитики сохраняют источники и контекст на момент подготовки.
      </p>
      <section className="panel history-panel">
        {state.loading ? (
          <Loading label="Загружаем историю…" />
        ) : state.error ? (
          <Empty
            title="Не удалось загрузить историю"
            action={() => setRetry((v) => v + 1)}
          >
            {state.error}
          </Empty>
        ) : state.items.length === 0 ? (
          <Empty title="История начинается здесь" icon="history">
            Создайте первую сводку в разделе «Обзор».
          </Empty>
        ) : (
          state.items.map((item) => (
            <button
              className="history-item"
              key={item.id}
              disabled={!!restoring}
              onClick={() => open(item.id)}
            >
              <span className="history-icon">
                <Icon name="news" />
              </span>
              <div>
                <strong>{formatDate(item.createdAt)}</strong>
                <span>
                  {item.itemCount} событий ·{" "}
                  {item.status === "completed" || item.status === "ready"
                    ? "Готово"
                    : item.status}
                </span>
              </div>
              <Icon
                name={restoring === item.id ? "refresh" : "arrow"}
                className={restoring === item.id ? "spin" : ""}
              />
            </button>
          ))
        )}
        {restoreError && (
          <p className="form-error" role="alert">
            {restoreError}
          </p>
        )}
      </section>
    </>
  );
}
