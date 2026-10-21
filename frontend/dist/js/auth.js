import { api } from './api.js';

export function renderAuth(onSuccess, register = false) {
  document.getElementById('app').innerHTML = `<main class="auth-shell" id="main"><section class="auth-card"><a class="brand" href="#"><span class="alfa-mark">А<span></span></span><span>Пульс бизнеса</span></a><div class="eyebrow">ВАШ БИЗНЕС В КОНТЕКСТЕ</div><h1>${register ? 'Создать аккаунт' : 'С возвращением'}</h1><p>${register ? 'Сохраняйте аналитику и обсуждайте события в контексте вашей компании.' : 'Войдите, чтобы открыть персональную аналитику.'}</p><form id="auth-form">${register ? '<label>Имя<input name="displayName" autocomplete="name" required maxlength="100"></label>' : ''}<label>Email<input name="email" type="email" autocomplete="username" required maxlength="254"></label><label>Пароль<input name="password" type="password" autocomplete="${register ? 'new-password' : 'current-password'}" required minlength="12" maxlength="128"></label><small>От 12 до 128 символов.</small><p id="auth-error" role="alert"></p><button type="submit" class="button dark">${register ? 'Зарегистрироваться' : 'Войти'}</button></form><button type="button" class="text-button" id="auth-toggle">${register ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}</button></section><aside class="auth-aside"><span class="eyebrow">ПУЛЬС БИЗНЕСА</span><h2>События.<br>Контекст.<br>Решения.</h2><p>Факты, экспертиза банка и персональная интерпретация — с проверяемыми основаниями.</p></aside></main>`;
  document.getElementById('auth-toggle').addEventListener('click', () => renderAuth(onSuccess, !register));
  document.getElementById('auth-form').addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    const values = new FormData(form);
    try {
      if (register) await api.register(values.get('email'), values.get('password'), values.get('displayName'));
      else await api.login(values.get('email'), values.get('password'));
      form.reset();
      await onSuccess();
    } catch (error) {
      document.getElementById('auth-error').textContent = error.message;
      button.disabled = false;
    }
  });
}
