import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { readStore, safeUrl, writeStore } from "../lib/storage.js";
import { Empty, Icon, Loading, SourceLink } from "./ui.jsx";

const tabs = [
  ["analysis", "Разбор события"],
  ["sources", "Источники"],
  ["trace", "Как получен вывод"],
];
const traceLabels = {
  planning: "Планирование",
  context: "Контекст компании",
  retrieval: "Поиск материалов",
  classification: "Классификация",
  deduplication: "Объединение дубликатов",
  ranking: "Ранжирование",
  interpretation: "Интерпретация",
  verification: "Проверка",
  adaptation: "Уточнение анализа",
};

export default function InsightDialog({
  id,
  company,
  role,
  user,
  onClose,
  notify,
}) {
  const dialog = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;
  const [state, setState] = useState({ loading: true, event: null, error: "" });
  const [retry, setRetry] = useState(0);
  const [tab, setTab] = useState("analysis");
  const [feedback, setFeedback] = useState(() =>
    readStore(user.id, `feedback:${company.id}:${id}`, ""),
  );
  const [rating, setRating] = useState(false);
  const [controller] = useState(() => new AbortController());
  useEffect(() => {
    const previousFocus = document.activeElement;
    const element = dialog.current;
    element.showModal();
    document.body.classList.add("modal-open");
    return () => {
      controller.abort();
      element.close();
      document.body.classList.remove("modal-open");
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [controller]);
  useEffect(() => {
    const request = new AbortController();
    setState({ loading: true, event: null, error: "" });
    Promise.all([
      api.getInsight(company.id, id, request.signal),
      api
        .getTrace(company.id, request.signal)
        .catch((error) => ({ steps: [], error: error.message })),
    ])
      .then(([event, trace]) => {
        if (!request.signal.aborted)
          setState({ loading: false, event: { ...event, trace }, error: "" });
      })
      .catch((error) => {
        if (!request.signal.aborted)
          setState({ loading: false, event: null, error: error.message });
      });
    return () => request.abort();
  }, [id, company.id, retry]);
  async function rate(value) {
    if (rating) return;
    setRating(true);
    try {
      await api.feedback(company.id, id, value);
      if (controller.signal.aborted) return;
      setFeedback(value);
      writeStore(user.id, `feedback:${company.id}:${id}`, value);
      notify("Спасибо за обратную связь");
    } catch (error) {
      if (!controller.signal.aborted) notify(error.message);
    } finally {
      if (!controller.signal.aborted) setRating(false);
    }
  }
  const event = state.event;
  return (
    <dialog
      ref={dialog}
      className="insight-dialog"
      aria-labelledby="insight-title"
      onCancel={(e) => {
        e.preventDefault();
        close.current();
      }}
      onClick={(e) => {
        if (e.target === dialog.current) {
          const r = dialog.current.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            close.current();
        }
      }}
    >
      <div className="dialog-top">
        <span>
          <Icon name="spark" />
          Персональный разбор <i>/</i> {company.name}
        </span>
        <button
          className="icon-button"
          aria-label="Закрыть разбор"
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>
      {state.loading ? (
        <div className="dialog-loading">
          <h2 id="insight-title">Готовим разбор…</h2>
          <Loading />
        </div>
      ) : state.error ? (
        <div className="dialog-loading">
          <h2 id="insight-title">Не удалось открыть событие</h2>
          <Empty
            title="Попробуем ещё раз"
            action={() => setRetry((v) => v + 1)}
          >
            {state.error}
          </Empty>
        </div>
      ) : (
        <>
          <header className="dialog-heading">
            <div className="news-meta">
              <span className={`event-kind ${event.kind}`}>
                <Icon name={event.kind === "risk" ? "risk" : "trend"} />
                {event.kind === "risk" ? "Риск" : "Возможность"}
              </span>
              <span>{event.category}</span>
            </div>
            <h2 id="insight-title">{event.title}</h2>
          </header>
          <div className="detail-layout">
            <section className="analysis-pane">
              <div
                className="detail-tabs"
                role="tablist"
                aria-label="Разделы разбора"
              >
                {tabs.map(([value, label], i) => (
                  <button
                    key={value}
                    id={`tab-${value}`}
                    role="tab"
                    aria-controls={`panel-${value}`}
                    aria-selected={tab === value}
                    tabIndex={tab === value ? 0 : -1}
                    onClick={() => setTab(value)}
                    onKeyDown={(e) => {
                      if (
                        !["ArrowLeft", "ArrowRight", "Home", "End"].includes(
                          e.key,
                        )
                      )
                        return;
                      e.preventDefault();
                      const next =
                        e.key === "Home"
                          ? 0
                          : e.key === "End"
                            ? tabs.length - 1
                            : (i +
                                (e.key === "ArrowRight"
                                  ? 1
                                  : tabs.length - 1)) %
                              tabs.length;
                      setTab(tabs[next][0]);
                      document.getElementById(`tab-${tabs[next][0]}`)?.focus();
                    }}
                  >
                    {label}
                    {value === "sources" && <span>{event.sources.length}</span>}
                  </button>
                ))}
              </div>
              <div
                className="analysis-body"
                id={`panel-${tab}`}
                role="tabpanel"
                aria-labelledby={`tab-${tab}`}
                tabIndex={0}
                key={tab}
              >
                {tab === "analysis" && (
                  <>
                    <section className="analysis-section">
                      <span className="content-label">
                        <Icon name="news" />
                        ФАКТЫ
                      </span>
                      <h3>Что произошло</h3>
                      <p>{event.fact}</p>
                      <button
                        className="text-button"
                        onClick={() => setTab("sources")}
                      >
                        Проверить источники
                        <Icon name="external" />
                      </button>
                    </section>
                    <section className="analysis-section personalized">
                      <span className="content-label">
                        <Icon name="spark" />
                        ВАШ КОНТЕКСТ
                      </span>
                      <h3>Почему это важно для «{company.name}»</h3>
                      <ul className="reason-list">
                        {event.contextReasons.map((text, i) => (
                          <li key={i}>
                            <Icon name="check" />
                            {text}
                          </li>
                        ))}
                      </ul>
                      <p>{event.summary}</p>
                      <small className="muted">
                        Основание: профиль компании · {role.name}
                      </small>
                    </section>
                    <div className="consequence-grid">
                      <section className="consequence risk-block">
                        <span className="content-label">
                          <Icon name="risk" />
                          РИСКИ
                        </span>
                        <TextList
                          items={event.risks}
                          empty="Не выявлены в этой сводке"
                        />
                      </section>
                      <section className="consequence opportunity-block">
                        <span className="content-label">
                          <Icon name="trend" />
                          ВОЗМОЖНОСТИ
                        </span>
                        <TextList
                          items={event.opportunities}
                          empty="Не выявлены в этой сводке"
                        />
                      </section>
                    </div>
                    <section className="analysis-section">
                      <span className="content-label bank-label">
                        А · АНАЛИТИКА БАНКА
                      </span>
                      <h3>Взгляд экспертов</h3>
                      <p>{event.bank}</p>
                    </section>
                    <section className="analysis-section">
                      <span className="content-label">
                        <Icon name="arrow" />
                        СЛЕДУЮЩИЕ ШАГИ
                      </span>
                      <h3>Что можно проверить</h3>
                      <TextList
                        items={event.actions}
                        empty="Рекомендации пока не сформированы"
                        ordered
                      />
                    </section>
                    {event.missing.length > 0 && (
                      <section className="notice">
                        <Icon name="help" />
                        <div>
                          <strong>Чего не хватает для точной оценки</strong>
                          <p>{event.missing.join(" · ")}</p>
                        </div>
                      </section>
                    )}
                    <div className="feedback-row">
                      <span>Этот разбор полезен?</span>
                      {[
                        ["useful", "Да, полезен"],
                        ["irrelevant", "Не для меня"],
                      ].map(([value, label]) => (
                        <button
                          key={value}
                          disabled={rating}
                          className={`feedback-button ${feedback === value ? "chosen" : ""}`}
                          aria-pressed={feedback === value}
                          onClick={() => rate(value)}
                        >
                          {value === "useful" && <Icon name="thumb" />}
                          {label}
                        </button>
                      ))}
                    </div>
                  </>
                )}
                {tab === "sources" && (
                  <>
                    <p className="muted">
                      Материалы и цитаты, на которые опирается разбор.
                    </p>
                    {event.sources.map((source) => (
                      <section className="source-card" key={source.id}>
                        <span className="content-label">
                          {source.kind === "bank"
                            ? "АНАЛИТИКА БАНКА"
                            : "НОВОСТНОЙ МАТЕРИАЛ"}
                        </span>
                        <h3>{source.title}</h3>
                        <p className="muted">
                          {source.publisher} · {source.date}
                        </p>
                        <blockquote>
                          {source.excerpt || "Цитата не предоставлена"}
                        </blockquote>
                        <SourceLink url={safeUrl(source.url)}>
                          Открыть первоисточник
                        </SourceLink>
                      </section>
                    ))}
                    {event.sources.length === 0 && (
                      <Empty title="Нет доступных источников">
                        Для этого события материалы не предоставлены.
                      </Empty>
                    )}
                  </>
                )}
                {tab === "trace" && (
                  <>
                    <p className="muted">
                      Этапы обработки и использованные основания. Скрытые
                      рассуждения модели не отображаются.
                    </p>
                    {event.trace.error ? (
                      <p role="alert" className="form-error">
                        {event.trace.error}
                      </p>
                    ) : event.trace.steps.length === 0 ? (
                      <p>Этапы обработки пока недоступны.</p>
                    ) : (
                      <div className="trace-list">
                        {event.trace.steps.map((step, i) => (
                          <section className="trace-step" key={i}>
                            <span>{i + 1}</span>
                            <div>
                              <h3>{traceLabels[step.stage] || step.stage}</h3>
                              <small>
                                {step.status === "succeeded"
                                  ? "Выполнено"
                                  : step.status === "failed"
                                    ? "Ошибка"
                                    : step.status}
                              </small>
                              <p>{step.resultSummary}</p>
                              <small>
                                Источников: {step.materialIds?.length || 0} ·
                                Признаков: {step.featureIds?.length || 0}
                              </small>
                            </div>
                          </section>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </section>
            <Chat companyId={company.id} eventId={id} />
          </div>
        </>
      )}
    </dialog>
  );
}
function TextList({ items, empty, ordered }) {
  const Tag = ordered ? "ol" : "ul";
  return items.length ? (
    <Tag>
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </Tag>
  ) : (
    <p className="muted">{empty}</p>
  );
}

export function Chat({ companyId, eventId }) {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(null);
  const log = useRef(null);
  const input = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [messages, busy]);
  async function send(value) {
    const text = value.trim().slice(0, 1500);
    if (!text || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    setDraft("");
    setMessages((v) => [...v, { role: "user", text }]);
    try {
      const answer = await api.ask(
        companyId,
        eventId,
        text,
        messages,
        controller.signal,
      );
      if (!controller.signal.aborted)
        setMessages((v) => [...v, { role: "assistant", ...answer }]);
    } catch (e) {
      if (!controller.signal.aborted) {
        setError(e.message);
        setDraft(text);
      }
    } finally {
      if (!controller.signal.aborted) {
        request.current = null;
        setBusy(false);
        requestAnimationFrame(() => input.current?.focus());
      }
    }
  }
  return (
    <aside className="chat-pane">
      <div className="chat-header">
        <span className="chat-symbol">
          <Icon name="spark" />
        </span>
        <div>
          <h3>Обсудим влияние?</h3>
          <span>AI-ассистент · контекст события</span>
        </div>
      </div>
      <div
        className="chat-messages"
        ref={log}
        role="log"
        aria-label="Переписка по событию"
        aria-live="polite"
      >
        <div className="chat-bubble assistant">
          Помогу разобраться в рисках, основаниях и следующих шагах для вашей
          компании.
        </div>
        {messages.map((m, i) => (
          <div className={`chat-bubble ${m.role}`} key={i}>
            {m.text}
            {m.citations?.map((c) => (
              <div className="chat-citation" key={c.id}>
                <SourceLink url={safeUrl(c.url)}>{c.title}</SourceLink>
              </div>
            ))}
          </div>
        ))}
        {busy && (
          <div className="chat-bubble assistant" role="status">
            <Icon name="refresh" className="spin" /> Готовим ответ…
          </div>
        )}
      </div>
      {messages.length === 0 && (
        <div className="chat-suggestions">
          {[
            "Какие риски для нашей компании?",
            "Каких данных не хватает?",
            "Какие следующие шаги?",
          ].map((q) => (
            <button key={q} disabled={busy} onClick={() => send(q)}>
              {q}
              <Icon name="arrow" />
            </button>
          ))}
        </div>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error} Вопрос сохранён — можно отправить ещё раз.
        </p>
      )}
      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
      >
        <textarea
          ref={input}
          aria-label="Вопрос об этом событии"
          placeholder="Задайте уточняющий вопрос…"
          maxLength={1500}
          rows={2}
          value={draft}
          disabled={busy}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              send(draft);
            }
          }}
        />
        <button
          className="send-button"
          type="submit"
          aria-label="Отправить вопрос"
          disabled={busy || !draft.trim()}
        >
          <Icon name="send" />
        </button>
      </form>
      <p className="chat-note">
        Проверяйте основания выводов во вкладке «Источники».
      </p>
    </aside>
  );
}
