import { useState } from "react";
import { api } from "../lib/api.js";
import { Brand, Icon } from "./ui.jsx";

export default function Auth({ onSuccess }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const values = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      if (register)
        await api.register(
          values.get("email").trim(),
          values.get("password"),
          values.get("displayName").trim(),
        );
      else await api.login(values.get("email").trim(), values.get("password"));
      await onSuccess();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="main" className="auth-shell">
      <section className="auth-left">
        <Brand />
        <div className="auth-card">
          <span className="eyebrow">ВАШ БИЗНЕС В КОНТЕКСТЕ</span>
          <h1>{register ? "Начнём с главного." : "С возвращением."}</h1>
          <p>
            {register
              ? "Создайте аккаунт для персональной аналитики вашей компании."
              : "Войдите, чтобы увидеть, что важно для вашего бизнеса сегодня."}
          </p>
          <form onSubmit={submit} aria-busy={busy}>
            {register && (
              <label>
                Как к вам обращаться
                <input
                  name="displayName"
                  autoComplete="name"
                  required
                  maxLength={100}
                  placeholder="Ваше имя"
                  disabled={busy}
                />
              </label>
            )}
            <label>
              Электронная почта
              <input
                name="email"
                type="email"
                autoComplete="username"
                required
                maxLength={254}
                placeholder="name@company.ru"
                disabled={busy}
              />
            </label>
            <label>
              Пароль
              <input
                name="password"
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                required
                minLength={12}
                maxLength={128}
                placeholder="Не менее 12 символов"
                disabled={busy}
              />
            </label>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            <button className="button primary" type="submit" disabled={busy}>
              {busy ? "Подождите…" : register ? "Создать аккаунт" : "Войти"}
              <Icon
                name={busy ? "refresh" : "arrow"}
                className={busy ? "spin" : ""}
              />
            </button>
          </form>
          <button
            className="text-button auth-toggle"
            disabled={busy}
            onClick={() => {
              setRegister((v) => !v);
              setError("");
            }}
          >
            {register
              ? "Уже есть аккаунт? Войти"
              : "Впервые здесь? Создать аккаунт"}
          </button>
          <div className="auth-trust">
            <Icon name="shield" /> Ваши данные остаются в контексте вашей
            компании
          </div>
        </div>
        <footer>Пульс бизнеса · Персональная аналитика</footer>
      </section>
      <aside className="auth-aside">
        <span className="eyebrow">МЕНЬШЕ ШУМА. БОЛЬШЕ СМЫСЛА.</span>
        <h2>
          Видеть события.
          <br />
          Понимать влияние.
          <br />
          <span>Действовать.</span>
        </h2>
        <div className="auth-visual" aria-hidden="true">
          <div className="visual-orbit" />
          <svg viewBox="0 0 520 180">
            <path d="M0 100H90L120 75L160 120L200 30L250 150L290 80L330 100H520" />
          </svg>
          <span>
            <Icon name="spark" /> Контекст меняет всё
          </span>
        </div>
        <p>
          Новости, риски и возможности — через призму вашего бизнеса. С
          источниками, объяснениями и следующим шагом.
        </p>
        <div className="auth-aside-bottom">
          <span>01 / КОНТЕКСТ</span>
          <span>02 / АНАЛИЗ</span>
          <span>03 / РЕШЕНИЕ</span>
        </div>
      </aside>
    </main>
  );
}
