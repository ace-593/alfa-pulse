import { useEffect, useState } from "react";
import { usePulse } from "./usePulse.js";
import Auth from "./components/Auth.jsx";
import Dashboard from "./components/Dashboard.jsx";
import InsightDialog from "./components/InsightDialog.jsx";
import { CompanyPage, MethodPage, HistoryPage } from "./components/Pages.jsx";
import { Brand, Empty, Icon } from "./components/ui.jsx";

const pages = ["overview", "feed", "saved", "companies", "history", "method"];
const currentPage = () =>
  pages.includes(location.hash.slice(1)) ? location.hash.slice(1) : "overview";
const navigation = [
  ["overview", "grid", "Обзор"],
  ["feed", "news", "Все события"],
  ["saved", "bookmark", "Сохранённое"],
  ["history", "history", "История сводок"],
];

export default function App() {
  const pulse = usePulse();
  const [view, setView] = useState(currentPage);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [selected, setSelected] = useState(null);
  useEffect(() => {
    const change = () => {
      if (location.hash === "#main") return;
      setView(currentPage());
      setMobileMenu(false);
      setSelected(null);
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(
    () => setSelected(null),
    [pulse.companyId, pulse.roleId, pulse.feed.loading],
  );
  const navigate = (page) => {
    location.hash = page;
    setView(page);
    setMobileMenu(false);
  };

  if (pulse.bootstrap.loading)
    return (
      <main id="main" className="startup">
        <Brand />
        <Icon name="refresh" className="spin" />
        <p>Собираем контекст вашего бизнеса…</p>
      </main>
    );
  if (pulse.bootstrap.error)
    return (
      <main id="main" className="startup">
        <Brand />
        <Empty title="Не удалось подключиться" action={pulse.reload}>
          {pulse.bootstrap.error}
        </Empty>
      </main>
    );
  if (!pulse.user) return <Auth onSuccess={pulse.reload} />;
  const data = pulse.bootstrap.data;
  const company = data.companies.find((c) => c.id === pulse.companyId);
  const role = data.roles.find((r) => r.id === pulse.roleId);
  if (!company)
    return (
      <main id="main" className="startup">
        <Empty title="Аккаунт готов" icon="building">
          Пока нет доступных компаний. Попросите оператора назначить доступ.
        </Empty>
        <button className="button secondary" onClick={pulse.reload}>
          Обновить
        </button>
        <button className="text-button" onClick={pulse.logout}>
          Выйти
        </button>
      </main>
    );
  const title = {
    overview: "Пульс бизнеса",
    feed: "Все события",
    saved: "Сохранённое",
    companies: "Профиль компании",
    history: "История сводок",
    method: "Как это работает",
  }[view];
  return (
    <>
      <aside className={`sidebar ${mobileMenu ? "mobile-open" : ""}`}>
        <Brand />
        <div className="workspace-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav aria-label="Главная навигация">
          {navigation.map(([id, icon, label]) => (
            <a
              href={`#${id}`}
              key={id}
              className={`nav-item ${view === id ? "active" : ""}`}
              aria-current={view === id ? "page" : undefined}
            >
              <Icon name={icon} />
              <span>{label}</span>
              {id === "saved" && (
                <span className="nav-count">{pulse.saved.length}</span>
              )}
            </a>
          ))}
          <div className="nav-divider" />
          <span className="workspace-label">ВАШ КОНТЕКСТ</span>
          {[
            ["companies", "building", "Компания"],
            ["method", "help", "Как это работает"],
          ].map(([id, icon, label]) => (
            <a
              href={`#${id}`}
              key={id}
              className={`nav-item ${view === id ? "active" : ""}`}
              aria-current={view === id ? "page" : undefined}
            >
              <Icon name={icon} />
              {label}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Icon name="shield" />
            <strong>
              У каждого вывода
              <br />
              есть основание.
            </strong>
            <p>Факты, источники и контекст — в одном месте.</p>
          </div>
          <div className="user-card">
            <span className="avatar">{pulse.user.displayName?.[0] || "П"}</span>
            <div>
              <strong>{pulse.user.displayName || "Пользователь"}</strong>
              <small>{role?.short}</small>
            </div>
            <button
              className="icon-button"
              aria-label="Выйти из аккаунта"
              onClick={() => {
                setSelected(null);
                pulse.logout();
              }}
            >
              <Icon name="logout" />
            </button>
          </div>
        </div>
      </aside>
      {mobileMenu && (
        <button
          className="mobile-backdrop"
          aria-label="Закрыть навигацию"
          onClick={() => setMobileMenu(false)}
        />
      )}
      <div className="shell">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              aria-label="Открыть навигацию"
              aria-expanded={mobileMenu}
              onClick={() => setMobileMenu((v) => !v)}
            >
              <Icon name="menu" />
            </button>
            <span className="breadcrumb">
              Альфа-Бизнес <span>/</span> Аналитика
            </span>
          </div>
          <label className="company-select">
            <Icon name="building" />
            <select
              aria-label="Компания"
              value={company.id}
              onChange={(e) => pulse.setCompany(e.target.value)}
            >
              {data.companies.map((c) => (
                <option value={c.id} key={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <Icon name="chevron" />
          </label>
        </header>
        <main id="main" className="main-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">ВАШ БИЗНЕС В КОНТЕКСТЕ</span>
              <h1>
                {title}
                <span className="heading-dot">.</span>
              </h1>
            </div>
            <label className="role-select">
              <Icon name="user" />
              <span className="sr-only">Роль пользователя</span>
              <select
                value={pulse.roleId}
                onChange={(e) => pulse.setRole(e.target.value)}
              >
                {data.roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
              <Icon name="chevron" />
            </label>
          </div>
          {["overview", "feed", "saved"].includes(view) && (
            <Dashboard
              key={`${company.id}:${pulse.roleId}`}
              pulse={pulse}
              company={company}
              role={role}
              view={view}
              navigate={navigate}
              onOpen={setSelected}
            />
          )}
          {view === "companies" && (
            <CompanyPage company={company} role={role} navigate={navigate} />
          )}
          {view === "method" && <MethodPage />}
          {view === "history" && (
            <HistoryPage
              key={company.id}
              companyId={company.id}
              restore={pulse.restore}
              navigate={navigate}
            />
          )}
          <footer className="page-footer">
            <span>Пульс бизнеса · Альфа-Бизнес</span>
            <span>Персональная аналитика с проверяемыми источниками</span>
          </footer>
        </main>
      </div>
      {selected && (
        <InsightDialog
          key={`${company.id}:${selected}`}
          id={selected}
          company={company}
          role={role}
          user={pulse.user}
          onClose={() => setSelected(null)}
          notify={pulse.notify}
        />
      )}
      <div
        className={`toast ${pulse.notice ? "show" : ""}`}
        role="status"
        aria-live="polite"
      >
        {pulse.notice && (
          <>
            <Icon name="check" />
            {pulse.notice}
          </>
        )}
      </div>
    </>
  );
}
