import { useMemo, useState } from "react";
import { filterEvents } from "../lib/domain.js";
import { formatDate, plural } from "../lib/storage.js";
import { Empty, Icon, Loading } from "./ui.jsx";

const filters = [
  ["all", "Все события"],
  ["risk", "Риски"],
  ["opportunity", "Возможности"],
  ["bank", "Аналитика банка"],
];
export function EventCard({ event, saved, onSave, onOpen }) {
  return (
    <article className="news-card">
      <div className="news-meta">
        <span className={`event-kind ${event.kind}`}>
          <Icon name={event.kind === "risk" ? "risk" : "trend"} />
          {event.kind === "risk" ? "Риск" : "Возможность"}
        </span>
        <span>{event.category}</span>
        <span className="meta-time">{event.time}</span>
      </div>
      <button
        className={`bookmark-button ${saved ? "marked" : ""}`}
        aria-label={saved ? "Удалить из сохранённого" : "Сохранить событие"}
        aria-pressed={saved}
        onClick={() => onSave(event.id)}
      >
        <Icon name="bookmark" />
      </button>
      <h3>
        <button className="event-title" onClick={() => onOpen(event.id)}>
          {event.title}
        </button>
      </h3>
      <p className="news-summary">{event.summary}</p>
      {event.contextReasons?.[0] && (
        <div className="why-line">
          <Icon name="spark" />
          <span>{event.contextReasons[0]}</span>
        </div>
      )}
      <div className="news-footer">
        <button
          className="text-button read-button"
          onClick={() => onOpen(event.id)}
        >
          Разобраться
          <Icon name="arrow" />
        </button>
        <div className="news-footnote">
          <span className={event.score >= 75 ? "high-priority" : ""}>
            {event.score >= 75 ? "Высокая значимость" : "По контексту компании"}
          </span>
          <span>
            <Icon name="clock" />
            {event.minutes} мин
          </span>
        </div>
      </div>
    </article>
  );
}

export function CompanyContext({ company: c, navigate }) {
  return (
    <section className="context-card">
      <div className="card-topline">
        <span className="eyebrow">КОНТЕКСТ КОМПАНИИ</span>
        <button
          className="icon-button"
          aria-label="Открыть профиль компании"
          onClick={() => navigate("companies")}
        >
          <Icon name="external" />
        </button>
      </div>
      <div className="company-identity">
        <span className="company-avatar">{c.initials}</span>
        <div>
          <h3>{c.name}</h3>
          <p>{c.industry}</p>
        </div>
      </div>
      {c.synthetic && (
        <span className="synthetic-label">Синтетический профиль</span>
      )}
      <dl className="context-data">
        <div>
          <dt>Годовая выручка</dt>
          <dd>
            {c.revenue === null
              ? "Нет данных"
              : `${c.revenue.toLocaleString("ru")} млрд ₽`}
          </dd>
        </div>
        <div>
          <dt>Регион регистрации</dt>
          <dd>{c.region}</dd>
        </div>
        <div>
          <dt>Банковские продукты</dt>
          <dd className="product-tags">
            {c.products.length
              ? c.products.map((p) => <span key={p}>{p}</span>)
              : "Нет данных"}
          </dd>
        </div>
      </dl>
      <div className="completeness">
        <span>
          Заполненность профиля<b>{c.completeness}%</b>
        </span>
        <progress
          aria-label="Заполненность профиля"
          max="100"
          value={c.completeness}
        />
        <p>Больше данных — точнее контекст.</p>
      </div>
    </section>
  );
}

export default function Dashboard({
  pulse,
  company,
  role,
  view,
  navigate,
  onOpen,
}) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("relevance");
  const { feed, saved, toggleSave } = pulse;
  const items = useMemo(() => {
    const result = filterEvents(feed.items, { filter, query, saved, view });
    return result.sort(
      sort === "newest"
        ? (a, b) =>
            a.age - b.age || String(b.time).localeCompare(String(a.time))
        : (a, b) => b.score - a.score,
    );
  }, [feed.items, filter, query, saved, view, sort]);
  const risks = feed.items.filter((e) => e.risks.length).length;
  const opportunities = feed.items.filter((e) => e.opportunities.length).length;
  function download() {
    const content = [
      `# Пульс бизнеса — ${company.name}`,
      `Роль: ${role.name}`,
      `Сводка: ${formatDate(feed.updatedAt)}`,
      ...items.flatMap((e) => [
        `\n## ${e.title}`,
        e.summary,
        `Факты: ${e.fact}`,
        `Риски: ${e.risks.join("; ")}`,
        `Возможности: ${e.opportunities.join("; ")}`,
        `Позиция банка: ${e.bank}`,
        `Следующие шаги: ${e.actions.join("; ")}`,
        `Ограничения: ${e.missing.join("; ")}`,
        ...e.sources.map(
          (s) => `Источник: ${s.title} — ${s.url || "ссылка отсутствует"}`,
        ),
      ]),
    ].join("\n\n");
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/markdown;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `pulse-${company.id}.md`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    pulse.notify("Сводка скачана");
  }
  const reset = () => {
    setFilter("all");
    setQuery("");
  };
  return (
    <div className="dashboard-grid">
      <section className="primary-column" aria-label="Новостная аналитика">
        {view === "overview" ? (
          <>
            <section className="hero">
              <div className="hero-content">
                <span className="hero-kicker">
                  <span />
                  ПЕРСОНАЛЬНАЯ АНАЛИТИКА
                </span>
                <h2>
                  Большая картина.
                  <br />
                  <span>Для вашего бизнеса.</span>
                </h2>
                <p>
                  Что происходит на рынке — и что это значит
                  <br className="desktop-break" /> именно для вашей компании.
                </p>
                <button
                  className="button dark"
                  disabled={feed.loading || !feed.items.length}
                  onClick={() =>
                    onOpen(
                      [...feed.items].sort((a, b) => b.score - a.score)[0].id,
                    )
                  }
                >
                  Главное событие
                  <Icon name="arrow" />
                </button>
              </div>
              <div className="hero-art" aria-hidden="true">
                <div className="hero-orbit" />
                <div className="hero-orbit second" />
                <div className="pulse-core">
                  <svg viewBox="0 0 180 100">
                    <path d="M0 52H40L60 20L90 85L120 30L140 52H180" />
                  </svg>
                </div>
                <span className="art-label first">
                  <Icon name="shield" />
                  Риски в фокусе
                </span>
                <span className="art-label last">
                  <Icon name="trend" />
                  Точки роста
                </span>
                <span className="art-star">✳</span>
              </div>
            </section>
            <div className="metrics">
              {[
                [
                  "layers",
                  "Значимых событий",
                  feed.items.length,
                  "в вашем контексте",
                ],
                [
                  "risk",
                  "В зоне внимания",
                  risks,
                  plural(risks, [
                    "возможный риск",
                    "возможных риска",
                    "возможных рисков",
                  ]),
                ],
                [
                  "trend",
                  "Точки роста",
                  opportunities,
                  plural(opportunities, [
                    "возможность",
                    "возможности",
                    "возможностей",
                  ]),
                ],
              ].map(([icon, label, count, caption]) => (
                <div className={`metric ${icon}`} key={icon}>
                  <span className="metric-icon">
                    <Icon name={icon} />
                  </span>
                  <span className="metric-label">{label}</span>
                  <div>
                    <strong>{feed.loading ? "—" : count}</strong>
                    <small>{caption}</small>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="page-intro">
            {view === "saved"
              ? "Важное, к чему хочется вернуться. Сохранения привязаны к выбранной компании."
              : "События, отобранные с учётом компании и вашей роли."}
          </p>
        )}
        <div className="section-heading">
          <div>
            <h2>
              {view === "saved"
                ? "Ваши сохранённые события"
                : "Важное для вашей компании"}
            </h2>
            <span className="update-label">
              {feed.loading
                ? "Готовим персональную сводку…"
                : feed.updatedAt
                  ? `Обновлено ${formatDate(feed.updatedAt)} МСК`
                  : "Сводка ещё не загружена"}
            </span>
          </div>
          <button
            className="icon-button refresh-button"
            aria-label="Обновить ленту"
            disabled={feed.loading}
            onClick={pulse.refresh}
          >
            <Icon name="refresh" className={feed.loading ? "spin" : ""} />
          </button>
        </div>
        <div className="filter-tabs" role="group" aria-label="Тип событий">
          {filters.map(([id, label]) => (
            <button
              key={id}
              className={`filter-tab ${filter === id ? "selected" : ""}`}
              aria-pressed={filter === id}
              onClick={() => setFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="search-sort">
          <label className="search-field">
            <Icon name="search" />
            <input
              type="search"
              aria-label="Поиск по событиям"
              placeholder="Найти событие или тему"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label className="sort-select">
            <Icon name="filter" />
            <select
              aria-label="Сортировка"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="relevance">По значимости</option>
              <option value="newest">Сначала новые</option>
            </select>
          </label>
        </div>
        {feed.limitations?.length > 0 && (
          <section className="notice">
            <Icon name="help" />
            <div>
              <strong>Ограничения анализа</strong>
              <p>{feed.limitations.join(" · ")}</p>
            </div>
          </section>
        )}
        <div className="feed" aria-busy={feed.loading}>
          {feed.loading ? (
            <Loading />
          ) : feed.error ? (
            <Empty
              title="Не удалось обновить ленту"
              action={pulse.refresh}
              icon="risk"
            >
              {feed.error}
            </Empty>
          ) : !items.length ? (
            <Empty
              title={
                view === "saved" && !saved.length
                  ? "Здесь будет ваше важное"
                  : "Событий не найдено"
              }
              action={
                view === "saved" && !saved.length
                  ? () => navigate("feed")
                  : reset
              }
              label={
                view === "saved" && !saved.length
                  ? "Перейти к событиям"
                  : "Сбросить фильтры"
              }
              icon={view === "saved" ? "bookmark" : "search"}
            >
              {view === "saved" && !saved.length
                ? "Сохраните событие с помощью закладки на карточке."
                : "Попробуйте другую тему или проверьте источники и выбранную компанию."}
            </Empty>
          ) : (
            items.map((event) => (
              <EventCard
                event={event}
                key={event.id}
                saved={saved.includes(event.id)}
                onSave={toggleSave}
                onOpen={onOpen}
              />
            ))
          )}
        </div>
        <div className="feed-bottom">
          <span>
            {feed.loading
              ? "Анализируем контекст"
              : `${items.length} ${plural(items.length, ["событие", "события", "событий"])} в подборке`}
          </span>
          <button
            className="text-button"
            disabled={feed.loading || !!feed.error || !items.length}
            onClick={download}
          >
            <Icon name="download" />
            Скачать сводку
          </button>
        </div>
      </section>
      <aside className="context-column" aria-label="Контекст аналитики">
        <CompanyContext company={company} navigate={navigate} />
        <section className="bank-card">
          <div className="bank-symbol">
            А<span>ЭКСПЕРТИЗА БАНКА</span>
          </div>
          <h3>
            От новости —<br />к пониманию.
          </h3>
          <p>
            Макроэкономика, отраслевые обзоры и взгляд экспертов в одном
            контексте.
          </p>
          <button
            className="text-button"
            onClick={() => {
              setFilter("bank");
              if (view === "saved") navigate("feed");
            }}
          >
            События с аналитикой
            <Icon name="arrow" />
          </button>
          <small>
            Позиция банка появляется при наличии подтверждающего материала.
          </small>
        </section>
        <div className="transparent-card">
          <Icon name="shield" />
          <div>
            <strong>Выводы с основанием</strong>
            <p>Отделяем факты, экспертизу банка и интерпретацию AI.</p>
            <button className="text-button" onClick={() => navigate("method")}>
              Как устроен анализ
              <Icon name="arrow" />
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}
