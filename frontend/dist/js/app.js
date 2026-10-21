import { api } from './api.js';
import { renderAuth } from './auth.js';
import { config } from '../config.js';
import { filterEvents, contextReasons } from './domain.js';
import { icon } from './icons.js';

const $ = (selector) => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(`pulse:${api.currentUser()?.id || "anonymous"}:${key}`)) ?? fallback; } catch { return fallback; } };
const write = (key, value) => { try { localStorage.setItem(`pulse:${api.currentUser()?.id || "anonymous"}:${key}`, JSON.stringify(value)); } catch {  } };
const state = { user: null, limitations: [], companies: [], roles: [], companyId: read('company', 'metal'), roleId: read('role', 'cfo'), view: 'overview', filter: 'all', query: '', sort: 'relevance', events: [], loading: true, error: null, updatedAt: null, modal: null, tab: 'analysis', messages: [], asking: false, chatError: '', feedback: read('feedback', {}), mobileMenu: false };
let feedController, detailController, chatController, toastTimer, lastFocus;
const company = () => state.companies.find(c => c.id === state.companyId);
const role = () => state.roles.find(r => r.id === state.roleId);
const saved = () => read(`saved:${state.companyId}`, []);
const navItems = [['overview', 'grid', 'Обзор'], ['feed', 'news', 'Все события'], ['saved', 'bookmark', 'Сохранённое']];
const plural = (n, forms) => forms[n % 100 >= 11 && n % 100 <= 14 ? 2 : n % 10 === 1 ? 0 : n % 10 >= 2 && n % 10 <= 4 ? 1 : 2];
const time = value => value ? new Intl.DateTimeFormat('ru', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' }).format(new Date(value)) : '—';
function toast(message) { clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').classList.add('show'); toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 3500); }
function persistContext() { write('company', state.companyId); write('role', state.roleId); }
function navigate(view) { location.hash = view; }
function render() {
  if (!company()) return;
  const c = company();
  $('#app').innerHTML = `
    <aside class="sidebar ${state.mobileMenu ? 'mobile-open' : ''}">
      <a class="brand" href="#overview" aria-label="Альфа-Бизнес, обзор"><span class="alfa-mark">А<span></span></span><span>Альфа<span class="brand-sub">Бизнес</span></span></a>
      <div class="workspace-label">ИНТЕРНЕТ-БАНК</div>
      <nav aria-label="Главная навигация">
        ${navItems.map(([id, ico, title]) => `<a class="nav-item ${state.view === id ? 'active' : ''}" href="#${id}" ${state.view === id ? 'aria-current="page"' : ''}>${icon(ico)}<span>${title}</span>${id === 'overview' ? '<span class="nav-dot"></span>' : id === 'saved' ? `<span class="nav-count">${saved().length}</span>` : ''}</a>`).join('')}
        <div class="nav-divider"></div><div class="workspace-label nav-label">ВАШ КОНТЕКСТ</div>
        <a class="nav-item ${state.view === 'companies' ? 'active' : ''}" href="#companies">${icon('building')}<span>Профиль компании</span></a>
        <a class="nav-item ${state.view === 'method' ? 'active' : ''}" href="#method">${icon('help')}<span>Как это работает</span></a>
      </nav>
      <div class="sidebar-bottom"><div class="sidebar-promo"><span class="promo-dot"></span><strong>Больше контекста.<br>Точнее решения.</strong><p>Новости, которые имеют<br>значение для вашего бизнеса.</p>${icon('spark')}</div>
      <div class="user-card"><span class="avatar">${esc(state.user?.displayName?.[0] || "П")}</span><div><strong>${esc(state.user?.displayName || "Пользователь")}</strong><small>${esc(role().short)}</small></div><button class="text-button" data-action="logout">Выйти</button></div></div>
    </aside>
    ${state.mobileMenu ? '<button class="mobile-backdrop" data-action="menu" aria-label="Закрыть навигацию"></button>' : ''}
    <div class="shell">
      <header class="topbar"><div class="topbar-left"><button class="icon-button mobile-menu" data-action="menu" aria-label="Открыть навигацию">${icon('menu')}</button><span class="breadcrumb">Альфа-Бизнес <span>/</span> <b>Аналитика</b></span></div>
      <div class="topbar-right"><span class="demo-pill"><span></span>${config.mode === 'demo' ? 'Демо-режим' : 'API подключён'}</span><span class="header-divider"></span><label class="company-select">${icon('building')}<select id="company-select" aria-label="Компания">${state.companies.map(x => `<option value="${esc(x.id)}" ${x.id === c.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>${icon('chevron')}</label></div></header>
      <main id="main" tabindex="-1"><div class="page-heading"><div><div class="eyebrow">ВАШ БИЗНЕС В КОНТЕКСТЕ</div><h1>${state.view === 'saved' ? 'Сохранённое' : state.view === 'companies' ? 'Профиль компании' : state.view === 'method' ? 'Как это работает' : 'Пульс бизнеса'}<span class="heading-dot">.</span></h1></div><div class="heading-actions"><label class="role-select">${icon('user')}<select id="role-select" aria-label="Роль пользователя">${state.roles.map(x => `<option value="${x.id}" ${x.id === state.roleId ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>${icon('chevron')}</label></div></div>
      <div id="page-content">${['overview', 'feed', 'saved'].includes(state.view) ? dashboard() : state.view === 'companies' ? companyPage() : methodPage()}</div>
      <footer class="page-footer"><span>Пульс бизнеса · Прототип для Альфа Хак</span><span>${config.mode === 'demo' ? 'Синтетические данные · реальный AI не подключён' : 'Данные и аналитика предоставляются API'}</span></footer>
      </main>
    </div>`;
}

function dashboard() {
  const c = company();
  const riskCount = state.events.filter(e => e.risks.length > 0).length;
  const opportunityCount = state.events.filter(e => e.opportunities.length > 0).length;
  return `<div class="dashboard-grid"><section class="primary-column" aria-label="Новостная аналитика">
    ${state.view === 'overview' ? `<section class="hero"><div class="hero-content"><span class="hero-kicker">ПЕРСОНАЛЬНАЯ АНАЛИТИКА ${icon('spark')}</span><h2>Большая картина.<br>Для вашего бизнеса.</h2><p>Что происходит на рынке — и что это<br class="desktop-break"> значит именно для вашей компании.</p><button class="button dark" data-action="top-insight">Главное событие ${icon('arrow')}</button></div><div class="hero-art" aria-hidden="true"><div class="art-grid"></div><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="art-core"><svg viewBox="0 0 160 160"><path d="M20 93h28l14-34 23 59 18-44h37" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg></div><div class="floating-label label-one">${icon('shield')} Риски под контролем</div><div class="floating-label label-two">${icon('trend')} Возможности в фокусе</div><span class="art-star">✳</span></div></section>
    <div class="metrics"><div class="metric"><span class="metric-icon neutral">${icon('layers')}</span><div><span>Значимых событий</span><strong>${state.loading ? '—' : state.events.length}<small>для вашей компании</small></strong></div></div><div class="metric"><span class="metric-icon red">${icon('risk')}</span><div><span>В зоне внимания</span><strong>${state.loading ? '—' : riskCount}<small>${plural(riskCount, ['возможный риск', 'возможных риска', 'возможных рисков'])}</small></strong></div></div><div class="metric"><span class="metric-icon green">${icon('trend')}</span><div><span>Точки роста</span><strong>${state.loading ? '—' : opportunityCount}<small>${plural(opportunityCount, ['возможность', 'возможности', 'возможностей'])}</small></strong></div></div></div>` : `<p class="page-intro">${state.view === 'saved' ? 'События, к которым вы хотите вернуться. Сохранения привязаны к выбранной компании.' : 'События, отобранные с учётом профиля компании и вашей роли.'}</p>`}
    <div class="section-heading"><div><h2>${state.view === 'saved' ? 'Ваши сохранённые события' : 'Важное для вашей компании'}</h2><span class="update-label">${state.loading ? 'Обновляем ленту…' : `Обновлено в ${time(state.updatedAt)} МСК`}</span></div><button class="icon-button" data-action="refresh" aria-label="Обновить ленту" ${state.loading ? 'disabled' : ''}>${icon('refresh', state.loading ? 'spin' : '')}</button></div>
    <div class="feed-toolbar"><div class="filter-tabs" role="group" aria-label="Тип событий">${[['all', 'Все события'], ['risk', 'Риски'], ['opportunity', 'Возможности'], ['bank', 'С аналитикой банка']].map(([id, label]) => `<button class="filter-tab ${state.filter === id ? 'selected' : ''}" data-filter="${id}" aria-pressed="${state.filter === id}">${label}</button>`).join('')}</div></div>
    <div class="search-sort"><label class="search-field">${icon('search')}<input id="search" type="search" placeholder="Найти событие или тему" value="${esc(state.query)}" autocomplete="off" aria-label="Поиск по событиям"></label><label class="sort-select">${icon('filter')}<select id="sort-select" aria-label="Сортировка"><option value="relevance" ${state.sort === 'relevance' ? 'selected' : ''}>По значимости</option><option value="newest" ${state.sort === 'newest' ? 'selected' : ''}>Сначала новые</option></select></label></div>
    ${state.limitations.length ? `<section class="notice"><strong>Ограничения анализа</strong><p>${esc(state.limitations.join(" · "))}</p></section>` : ""}<div id="feed" aria-live="polite">${feedContent()}</div>
    <div class="feed-bottom"><span>События собраны с учётом контекста компании</span><button class="text-button" data-action="history">История сводок</button><button class="text-button" data-action="export">${icon('download')} Скачать сводку</button></div>
    </section><aside class="context-column" aria-label="Контекст аналитики">
      <section class="context-card company-context"><div class="card-topline"><span class="small-label">КОНТЕКСТ КОМПАНИИ</span><button class="icon-button small" data-action="profile" aria-label="Открыть профиль компании">${icon('external')}</button></div><div class="company-identity"><span class="company-avatar" style="--company-color:${esc(c.color)}">${esc(c.initials)}</span><div><h3>${esc(c.name)}</h3><p>${esc(c.industry)}</p></div></div><div class="context-data"><div><span>Годовая выручка</span><strong>${c.revenue === null ? 'Нет данных' : c.revenue.toLocaleString('ru') + ' млрд ₽'}</strong></div><div><span>Регион регистрации</span><strong>${esc(c.region)}</strong></div><div><span>Банковские продукты</span><div class="product-tags">${c.products.map(x => `<span>${esc(x)}</span>`).join('')}</div></div></div><div class="completeness"><span>Заполненность доступных полей <b>${c.completeness}%</b></span><div class="progress-track"><i style="width:${c.completeness}%"></i></div><p>Чем больше данных, тем точнее контекст.</p></div></section>
      <section class="context-card bank-card"><div class="bank-symbol">А<span>ЭКСПЕРТИЗА БАНКА</span></div><h3>От новости —<br>к пониманию</h3><p>Макроэкономика, отраслевые обзоры и взгляд экспертов в одном контексте.</p><div class="bank-report">${icon('news')}<div><strong>Аналитика Альфа-Банка</strong><span>Материалы из приложения к кейсу</span></div></div><button class="text-button" data-action="bank-filter">События с аналитикой ${icon('arrow')}</button><span class="bank-note">Позиция банка показывается только<br>при наличии подтверждающего материала.</span></section>
      <section class="transparent-card">${icon('shield')}<div><strong>Выводы с основанием</strong><p>Отделяем факты, экспертизу банка и интерпретацию AI. Источники — внутри каждого события.</p><button class="text-button" data-action="method">Как устроен анализ ${icon('arrow')}</button></div></section>
    </aside></div>`;
}

function visibleEvents() {
  const list = filterEvents(state.events, { filter: state.filter, query: state.query, saved: saved(), view: state.view });
  if (state.sort === 'newest') list.sort((a, b) => a.age - b.age || String(b.time).localeCompare(String(a.time)));
  return list;
}
function feedContent() {
  if (state.loading) return `<div class="skeleton" aria-label="Загрузка событий"></div><div class="skeleton"></div>`;
  if (state.error) return `<div class="empty-state">${icon('risk')}<h3>Не удалось обновить ленту</h3><p>${esc(state.error)}</p><button class="button dark" data-action="refresh">Попробовать ещё раз</button></div>`;
  const list = visibleEvents();
  if (!list.length) return `<div class="empty-state">${icon(state.view === 'saved' ? 'bookmark' : 'search')}<h3>${state.view === 'saved' && !saved().length ? 'Здесь будут важные события' : 'Событий не найдено'}</h3><p>${state.view === 'saved' && !saved().length ? 'Нажмите на закладку у события, чтобы сохранить его для этой компании.' : 'Попробуйте другую тему или сбросьте фильтры.'}</p><button class="button light" data-action="${state.view === 'saved' && !saved().length ? 'all-events' : 'reset-filters'}">${state.view === 'saved' && !saved().length ? 'Перейти к событиям' : 'Сбросить фильтры'}</button></div>`;
  return list.map((event, i) => {
    const marked = saved().includes(event.id);
    const reason = contextReasons(event, company())[0];
    return `<article class="news-card" style="--card-delay:${Math.min(i, 4) * 45}ms"><div class="news-main"><div class="news-meta"><span class="event-kind ${event.kind}">${icon(event.kind === 'risk' ? 'risk' : 'trend')}${event.kind === 'risk' ? 'Риск' : 'Возможность'}</span><span>${esc(event.category)}</span><span class="meta-time">${esc(event.time)}</span></div><h3><button class="event-title" data-open="${esc(event.id)}">${esc(event.title)}</button></h3><p class="news-summary">${esc(event.summary)}</p><div class="why-line">${icon('spark')}<span>${esc(reason)}</span></div><div class="news-footer"><button class="text-button read-button" data-open="${event.id}">Разобраться ${icon('arrow')}</button><div class="news-footnote"><span title="Приоритет события в контексте компании, не вероятность">${event.score >= 75 ? '<i class="priority-dot"></i> Высокая значимость' : 'По контексту компании'}</span><span>${icon('clock')} ${event.minutes} мин</span></div></div></div><button class="bookmark-button ${marked ? 'marked' : ''}" data-save="${event.id}" aria-label="${marked ? 'Удалить из сохранённого' : 'Сохранить событие'}" aria-pressed="${marked}">${icon('bookmark')}</button></article>`;
  }).join('');
}

function companyPage() {
  const c = company();
  return `<p class="page-intro">Персонализация опирается на признаки конкретного бизнеса. Источники и ограничения данных указаны в профиле и каждой сводке.</p><div class="profile-grid"><section class="panel"><div class="company-identity large"><span class="company-avatar" style="--company-color:${c.color}">${esc(c.initials)}</span><div><h2>${esc(c.name)}</h2><p>${esc(c.industry)} · ОКВЭД ${esc(c.okved)}</p></div></div><p class="profile-description">${esc(c.description)}</p><dl class="profile-fields">${[['Идентификатор', c.id], ['Выручка', `${c.revenue === null ? 'Нет данных' : c.revenue.toLocaleString('ru') + ' млрд ₽'}`], ['Регион регистрации', c.region], ['Город регистрации', c.city], ['Численность сотрудников', c.workers], ['Группа компаний', c.group || 'Не указана'], ['Внешнеторговые связи', c.countries.join(', ') || 'Нет данных']].map(([label, value]) => `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl><div class="product-tags">${c.products.map(p => `<span>${esc(p)}</span>`).join('')}</div></section><section class="panel"><span class="eyebrow">ПРОЗРАЧНАЯ ПЕРСОНАЛИЗАЦИЯ</span><h2>Что влияет на вашу ленту</h2><ul class="feature-list"><li>${icon('building')} Отрасль и виды деятельности</li><li>${icon('layers')} Наличие банковских продуктов</li><li>${icon('globe')} Внешнеторговые связи</li><li>${icon('user')} Роль: ${esc(role().name)}</li></ul><div class="notice"><strong>Каких данных пока не хватает</strong><p>Объём и структура долга, валюты контрактов, доля рынка, платёжный календарь. Наличие кредитного продукта не определяет размер долговой нагрузки.</p></div><p class="muted">Регион регистрации не означает все регионы присутствия. Страны ФТС сами по себе не определяют направление операций.</p><button class="button dark" data-action="all-events">Открыть персональную ленту ${icon('arrow')}</button></section></div>`;
}

function methodPage() {
  const cards = [
    ['Контекст компании', 'Учитываем доступные признаки бизнеса, выбранную роль и настройки. Неизвестные показатели отмечаем явно.'],
    ['Значимые события', 'Собираем материалы, выделяем темы, объединяем дубликаты и ранжируем события для выбранной компании.'],
    ['Последствия', 'Отделяем факты, позицию банка и сценарные выводы. Показываем риски, возможности и вопросы для проверки.'],
    ['Основания', 'Каждый вывод связан с версиями материалов и признаками компании. Первичные материалы доступны во вкладке источников.'],
    ['Уточнения', 'Вопрос учитывает выбранное событие и сохраненный контекст. Если данных или подключения модели недостаточно, сервис сообщает об этом.'],
    ['Проверка', 'Проверяем цитаты и связи между основаниями. Существенные шаги анализа доступны во вкладке трассировки.'],
  ];
  return `<p class="page-intro">Ограничения источников и данных указаны в каждой сводке.</p><div class="method-grid">${cards.map(([title, description], i) => `<section class="panel method-card"><span>${i+1}</span><h2>${esc(title)}</h2><p>${esc(description)}</p></section>`).join('')}</div>`;
}

async function loadFeed() {
  feedController?.abort();
  feedController = new AbortController();
  const controller = feedController;
  state.loading = true; state.error = null; state.events = [];
  render();
  try {
    const response = await api.getFeed(state.companyId, state.roleId, controller.signal);
    if (controller.signal.aborted) return;
    if (!Array.isArray(response.items)) throw new Error('Сервер вернул неверный формат ленты.');
    state.limitations = response.limitations || []; state.events = response.items; state.updatedAt = response.updatedAt; state.loading = false; render();
  } catch (error) {
    if (controller.signal.aborted) return;
    if (error.status === 401) { renderAuth(boot); return; } state.loading = false; state.error = error.message; render();
  }
}

function closeModal() {
  detailController?.abort(); chatController?.abort();
  const dialog = $('#insight-dialog');
  if (dialog?.open) dialog.close();
  $('#overlay-root').innerHTML = '';
  document.body.classList.remove('modal-open');
  state.modal = null; state.messages = []; state.asking = false;
  if (lastFocus?.isConnected) lastFocus.focus();
}
async function openInsight(id) {
  detailController?.abort(); chatController?.abort();
  detailController = new AbortController();
  const controller = detailController;
  lastFocus = document.activeElement;
  state.modal = { id, loading: true }; state.tab = 'analysis'; state.messages = []; state.chatError = ''; state.asking = false;
  renderModal(true);
  try {
    const [event, trace] = await Promise.all([api.getInsight(state.companyId, id, controller.signal), api.getTrace(state.companyId, controller.signal)]); event.trace = trace;
    if (controller.signal.aborted) return;
    state.modal = event; renderModal();
  } catch (error) {
    if (controller.signal.aborted) return;
    state.modal = { id, error: error.message }; renderModal();
  }
}
function sourceButton(id, label) { return `<button class="evidence-link" data-source="${esc(id)}">${icon('link')} ${esc(label)}</button>`; }
function renderModal(initial = false) {
  const event = state.modal;
  if (!event) return;
  if (initial) $('#overlay-root').innerHTML = '<dialog id="insight-dialog" aria-labelledby="insight-title"></dialog>';
  const dialog = $('#insight-dialog');
  const scroll = dialog.querySelector('.analysis-body')?.scrollTop || 0;
  const focused = document.activeElement?.id;
  const draft = $('#chat-input')?.value || '';
  dialog.innerHTML = `<div class="dialog-top"><span class="dialog-breadcrumb">${icon('spark')} Персональный разбор <span>/</span> ${esc(company().name)}</span><button class="icon-button" data-action="close" aria-label="Закрыть разбор">${icon('close')}</button></div>${event.loading ? '<h2 id="insight-title" class="loading-title">Готовим разбор…</h2><div class="skeleton modal-skeleton"></div>' : event.error ? `<div class="empty-state"><h2 id="insight-title">Не удалось открыть событие</h2><p>${esc(event.error)}</p><button class="button dark" data-open="${esc(event.id)}">Повторить</button></div>` : `<div class="dialog-heading"><div class="news-meta"><span class="event-kind ${event.kind}">${icon(event.kind === 'risk' ? 'risk' : 'trend')}${event.kind === 'risk' ? 'Риск' : 'Возможность'}</span><span>${esc(event.category)}</span><span class="demo-mini">${config.mode === 'demo' ? 'Синтетический сценарий' : 'Персональная аналитика'}</span></div><h2 id="insight-title">${esc(event.title)}</h2></div><div class="detail-layout"><section class="analysis-pane"><div class="detail-tabs" role="tablist" aria-label="Разделы разбора">${[['analysis', 'Разбор события'], ['sources', `Источники · ${event.sources.length}`], ['trace', 'Как получен вывод']].map(([id, label]) => `<button id="tab-${id}" role="tab" tabindex="${state.tab === id ? 0 : -1}" aria-selected="${state.tab === id}" aria-controls="detail-panel" data-tab="${id}">${label}</button>`).join('')}</div><div id="detail-panel" class="analysis-body" role="tabpanel" aria-labelledby="tab-${state.tab}">${state.tab === 'sources' ? sourcesContent(event) : state.tab === 'trace' ? traceContent(event) : analysisContent(event)}</div></section>${chatContent()}</div>`}`;
  if (initial) { dialog.showModal(); document.body.classList.add('modal-open'); dialog.addEventListener('cancel', e => { e.preventDefault(); closeModal(); }); dialog.addEventListener('click', e => { if (e.target === dialog) { const r = dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) closeModal(); } }); }
  if (dialog.querySelector('.analysis-body')) dialog.querySelector('.analysis-body').scrollTop = scroll;
  if ($('#chat-input')) { $('#chat-input').value = draft; if (focused === 'chat-input') $('#chat-input').focus(); }
  const log = $('.chat-messages'); if (log) log.scrollTop = log.scrollHeight;
}
function analysisContent(event) {
  const reasons = contextReasons(event, company());
  const rated = state.feedback[`${state.companyId}:${event.id}`];
  return `<section class="analysis-section"><span class="content-label fact-label">${icon('news')} ФАКТЫ ${config.mode === 'demo' ? '· ДЕМОСЦЕНАРИЙ' : ''}</span><h3>Что произошло</h3><p>${esc(event.fact)}</p>${sourceButton(event.sourceIds[0], 'Основание события')}</section>
  <section class="analysis-section personalized"><span class="content-label ai-label">${icon('spark')} ИНТЕРПРЕТАЦИЯ ${config.mode === 'demo' ? '· ДЕМО' : ''}</span><h3>Почему это важно для компании «${esc(company().name)}»</h3><ul class="reason-list">${reasons.map(r => `<li>${icon('check')}${esc(r)}</li>`).join('')}</ul><p>${esc(event.summary)}</p><span class="context-origin">Основание: ${config.mode === 'demo' ? 'синтетический ' : ''}профиль компании · ${esc(role().name)}</span></section>
  <div class="consequence-grid"><section class="consequence risk-block"><span class="content-label">${icon('risk')} ВОЗМОЖНЫЕ РИСКИ</span><ul>${event.risks.map(x => `<li>${esc(x)}</li>`).join('')}</ul></section><section class="consequence opportunity-block"><span class="content-label">${icon('trend')} ВОЗМОЖНОСТИ</span><ul>${event.opportunities.map(x => `<li>${esc(x)}</li>`).join('')}</ul></section></div>
  <section class="analysis-section bank-analysis"><span class="content-label">А &nbsp; АНАЛИТИКА БАНКА ${config.mode === 'demo' ? '· ДЕМОПРИМЕР' : ''}</span><h3>Как событие связано с аналитикой банка</h3><p>${esc(event.bank)}</p>${event.sources.some(s => s.kind === 'bank') ? sourceButton(event.sources.find(s => s.kind === 'bank').id, 'Материал банка') : ''}</section>
  <section class="analysis-section"><span class="content-label">${icon('arrow')} СЛЕДУЮЩИЕ ШАГИ</span><h3>Что можно проверить</h3><ol class="actions-list">${event.actions.map(x => `<li>${esc(x)}</li>`).join('')}</ol></section>
  <section class="notice"><strong>${icon('help')} Чего не хватает для точной оценки</strong><p>${esc(event.missing.join(' · '))}. Количественный эффект не рассчитан.</p></section><div class="feedback-row"><span>Этот разбор полезен?</span><button class="feedback-button ${rated === 'useful' ? 'chosen' : ''}" data-feedback="useful" aria-pressed="${rated === 'useful'}">${icon('thumb')} Да</button><button class="feedback-button ${rated === 'irrelevant' ? 'chosen' : ''}" data-feedback="irrelevant" aria-pressed="${rated === 'irrelevant'}">Не для меня</button></div>`;
}
function sourcesContent(event) {
  return `<p class="muted sources-intro">${config.mode === 'demo' ? 'Все внешние события в демо синтетические. Названия банковских отчётов взяты из кейса, но их содержимое не загружено.' : 'Проверьте источники и статус материалов, использованных в анализе.'}</p>${event.sources.map(source => `<section id="source-${esc(source.id)}" class="source-card"><span class="content-label ${source.kind === 'bank' ? 'bank-label' : 'fact-label'}">${icon(source.kind === 'bank' ? 'building' : 'news')} ${source.kind === 'bank' ? 'АНАЛИТИКА БАНКА' : 'НОВОСТНОЙ МАТЕРИАЛ'}</span><h3>${esc(source.title)}</h3><p class="source-publisher">${esc(source.publisher)} · ${esc(source.date)}</p><blockquote>${esc(source.excerpt)}</blockquote>${source.url && /^https:\/\//.test(source.url) ? `<a class="text-button" href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${config.mode === 'demo' ? 'Открыть папку материалов кейса' : 'Открыть первоисточник'} ${icon('external')}</a>` : '<span class="source-unavailable">Внешняя ссылка отсутствует; см. выдержку и статус материала</span>'}</section>`).join('')}<section class="source-card"><span class="content-label">${icon('building')} КЛИЕНТСКИЙ КОНТЕКСТ</span><h3>${esc(company().name)}</h3><ul class="reason-list">${contextReasons(event, company()).map(x => `<li>${icon('check')}${esc(x)}</li>`).join('')}</ul><p class="muted">${config.mode === 'demo' ? 'Вымышленный профиль. Это не данные реального клиента банка.' : 'Признаки компании предоставлены сервером.'}</p></section>`;
}
function traceContent(event) {
  const labels = { planning: "Планирование", context: "Контекст компании", retrieval: "Поиск материалов", classification: "Классификация", deduplication: "Объединение дубликатов", ranking: "Ранжирование", interpretation: "Интерпретация", verification: "Проверка", adaptation: "Уточнение анализа" };
  const steps = event.trace?.steps || [];
  return `<p class="muted">Существенные этапы анализа и использованные основания. Скрытые рассуждения модели не отображаются.</p><div class="trace-list">${steps.map((step, i) => `<section class="trace-step"><span>${i+1}</span><div><h3>${esc(labels[step.stage] || step.stage)} · ${step.status === "succeeded" ? "Выполнено" : step.status === "failed" ? "Ошибка" : "Пропущено"}</h3><p>${esc(step.resultSummary)}</p><small>Источников: ${step.materialIds.length} · Признаков: ${step.featureIds.length}</small></div></section>`).join('')}</div>`;
}
function chatContent() {
  return `<aside class="chat-pane"><div class="chat-header"><span class="chat-symbol">${icon('spark')}</span><div><h3>Обсудим влияние?</h3><span>${config.mode === 'demo' ? 'Демо-ассистент' : 'AI-ассистент'} · контекст события</span></div></div><div class="chat-messages" role="log" aria-label="Переписка по событию" aria-live="polite"><div class="chat-bubble assistant">Могу помочь разобраться, как событие связано с вашей компанией. Спросите о рисках, источниках или следующих шагах.</div>${state.messages.map(m => `<div class="chat-bubble ${m.role === 'user' ? 'user' : 'assistant'}">${esc(m.text)}${(m.citations || []).map(c => `<div class="chat-citation">${c.url && /^https:\/\//.test(c.url) ? `<a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">${esc(c.title)}</a>` : esc(c.title)}</div>`).join('')}</div>`).join('')}${state.asking ? '<div class="chat-bubble assistant typing" aria-label="Готовим ответ"><i></i><i></i><i></i></div>' : ''}</div>${!state.messages.length ? `<div class="chat-suggestions">${['Какие риски для нашей компании?', 'Покажи сценарный разрез', 'Каких данных не хватает?'].map(q => `<button data-question="${esc(q)}">${esc(q)} ${icon('arrow')}</button>`).join('')}</div>` : ''}<div class="chat-error" role="alert">${esc(state.chatError)}</div><form id="chat-form" class="chat-form"><label class="sr-only" for="chat-input">Вопрос об этом событии</label><textarea id="chat-input" rows="2" maxlength="1500" placeholder="Задайте уточняющий вопрос…" ${state.asking ? 'disabled' : ''}></textarea><button class="send-button" type="submit" aria-label="Отправить вопрос" ${state.asking ? 'disabled' : ''}>${icon('send')}</button></form><p class="chat-note">${config.mode === 'demo' ? 'Шаблонные ответы без LLM. Контекст: компания и выбранное событие.' : 'Проверяйте основания выводов во вкладке «Источники».'}</p></aside>`;
}

async function ask(question) {
  const message = question.trim().slice(0, 1500);
  if (!message || state.asking || !state.modal || state.modal.loading || state.modal.error) return;
  chatController?.abort(); chatController = new AbortController();
  const controller = chatController;
  const history = [...state.messages];
  state.messages.push({ role: 'user', text: message }); state.asking = true; state.chatError = '';
  if ($('#chat-input')) $('#chat-input').value = '';
  renderModal();
  try {
    const answer = await api.ask(state.companyId, state.modal.id, message, history, controller.signal);
    if (controller.signal.aborted) return;
    state.messages.push({ role: 'assistant', text: answer.text, citations: answer.citations });
  } catch (error) { if (controller.signal.aborted) return; state.chatError = `${error.message} Задайте вопрос ещё раз.`; }
  if (controller.signal.aborted) return;
  state.asking = false; renderModal(); $('#chat-input')?.focus();
}

function toggleSave(id) {
  const list = saved(); const exists = list.includes(id);
  write(`saved:${state.companyId}`, exists ? list.filter(x => x !== id) : [...list, id]);
  const focused = document.activeElement?.closest('[data-save]')?.dataset.save;
  if ($('#feed')) $('#feed').innerHTML = feedContent();
  const count = $('.nav-count'); if (count) count.textContent = saved().length;
  if (focused) document.querySelector(`[data-save="${CSS.escape(focused)}"]`)?.focus();
  toast(exists ? 'Событие удалено из сохранённого' : 'Событие сохранено для этой компании');
}
function exportBrief() {
  const items = visibleEvents();
  if (state.loading || state.error || !items.length) { toast('Нет загруженных событий для сводки'); return; }
  const content = [`# Пульс бизнеса — ${company().name}`, `Роль: ${role().name}`, `Режим: ${config.mode === 'demo' ? 'синтетическая демонстрация; не реальная аналитика банка' : 'API'}`, `Время выгрузки: ${new Date().toISOString()}`, ...items.flatMap(e => ['', `## ${e.title}`, `Категория: ${e.category}`, `Факты: ${e.fact}`, `Связь с компанией: ${contextReasons(e, company()).join('. ')}`, `Риски: ${e.risks.join(' ')}`, `Возможности: ${e.opportunities.join(' ')}`, `Аналитика банка: ${e.bank}`, `Следующие шаги: ${e.actions.join(' ')}`, `Недостающие данные: ${e.missing.join(', ')}`, `Идентификаторы оснований: ${e.sourceIds.join(', ')}`])].join('\n\n');
  const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }));
  const a = document.createElement('a'); a.href = url; a.download = `pulse-${state.companyId}.md`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast('Сводка скачана в формате Markdown');
}

document.addEventListener('click', async e => {
  const button = e.target.closest('button');
  if (!button || button.disabled) return;
  if (button.dataset.open) { openInsight(button.dataset.open); return; }
  if (button.dataset.save) { toggleSave(button.dataset.save); return; }
  if (button.dataset.filter) {
    state.filter = button.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(b => { b.classList.toggle('selected', b.dataset.filter === state.filter); b.setAttribute('aria-pressed', String(b.dataset.filter === state.filter)); });
    $('#feed').innerHTML = feedContent(); return;
  }
  if (button.dataset.tab) { state.tab = button.dataset.tab; renderModal(); $(`#tab-${state.tab}`)?.focus(); return; }
  if (button.dataset.source) { state.tab = 'sources'; renderModal(); const target = document.getElementById(`source-${button.dataset.source}`); target?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); return; }
  if (button.dataset.question) { ask(button.dataset.question); return; }
  if (button.dataset.feedback && state.modal) {
    const key = `${state.companyId}:${state.modal.id}`, value = button.dataset.feedback;
    button.disabled = true;
    try { await api.feedback(state.companyId, state.modal.id, value); state.feedback[key] = value; write('feedback', state.feedback); if (state.modal) renderModal(); toast(config.mode === 'demo' ? 'Спасибо! Демо-оценка сохранена в этом браузере.' : 'Спасибо за обратную связь'); }
    catch (error) { toast(error.message); button.disabled = false; }
    return;
  }
  switch (button.dataset.action) {
    case 'logout': feedController?.abort(); closeModal(); await api.logout().catch(() => {}); state.events = []; state.companies = []; state.user = null; renderAuth(boot); break;
    case 'history': await showHistory(); break;
    case 'close': closeModal(); break;
    case 'refresh': await loadFeed(); toast(state.error ? 'Обновление не выполнено' : 'Лента обновлена'); break;
    case 'profile': navigate('companies'); break;
    case 'method': navigate('method'); break;
    case 'menu': state.mobileMenu = !state.mobileMenu; render(); break;
    case 'top-insight': if (state.events[0]) openInsight(state.events[0].id); else toast('Подождите загрузки событий'); break;
    case 'all-events': state.filter = 'all'; state.query = ''; navigate('feed'); if (state.view === 'feed') render(); break;
    case 'bank-filter': state.filter = 'bank'; navigate('feed'); if (state.view === 'feed') render(); break;
    case 'reset-filters': state.filter = 'all'; state.query = ''; render(); break;
    case 'export': exportBrief(); break;
  }
});
document.addEventListener('input', e => { if (e.target.id === 'search') { state.query = e.target.value; $('#feed').innerHTML = feedContent(); } });
document.addEventListener('change', e => {
  if (e.target.id === 'company-select' || e.target.id === 'role-select') {
    closeModal();
    if (e.target.id === 'company-select') { state.companyId = e.target.value; state.query = ''; state.filter = 'all'; }
    else state.roleId = e.target.value;
    persistContext(); loadFeed();
  }
  if (e.target.id === 'sort-select') { state.sort = e.target.value; $('#feed').innerHTML = feedContent(); }
});
document.addEventListener('submit', e => { if (e.target.id === 'chat-form') { e.preventDefault(); ask($('#chat-input').value); } });
document.addEventListener('keydown', e => {
  if (e.target.id === 'chat-input' && e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(e.target.value); }
  if (e.target.matches('[role="tab"]') && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) {
    e.preventDefault(); const tabs = ['analysis', 'sources', 'trace']; const i = tabs.indexOf(state.tab);
    state.tab = e.key === 'Home' ? tabs[0] : e.key === 'End' ? tabs[2] : tabs[(i + (e.key === 'ArrowRight' ? 1 : 2)) % 3]; renderModal(); $(`#tab-${state.tab}`)?.focus();
  }
});
window.addEventListener('hashchange', () => { if (location.hash === '#main') return; state.view = ['overview', 'feed', 'saved', 'companies', 'method'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview'; state.mobileMenu = false; closeModal(); render(); window.scrollTo({ top: 0 }); });

async function boot() {
  if (!api.hasSession()) { renderAuth(boot); return; }
  try {
    const data = await api.getBootstrap(); state.user = data.user; state.companies = data.companies; state.roles = data.roles;
    if (!state.companies.length) { $('#app').innerHTML = `<main class="startup-error"><h1>Аккаунт создан</h1><p>Пока нет доступных компаний. Попросите оператора назначить доступ и обновите страницу.</p><button class="button dark" data-action="logout">Выйти</button></main>`; return; }
    if (!company()) state.companyId = state.companies[0].id;
    if (!role()) state.roleId = state.roles[0].id;
    state.view = ['overview', 'feed', 'saved', 'companies', 'method'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
    await loadFeed();
  } catch (error) {
    if (error.status === 401) { renderAuth(boot); return; }
    $('#app').innerHTML = `<main class="startup-error"><h1>Пульс бизнеса</h1><p role="alert">${esc(error.message)}</p><button class="button dark" id="retry-boot">Повторить загрузку</button></main>`;
    $('#retry-boot').addEventListener('click', boot);
  }
}
boot();

async function showHistory() {
  try {
    const history = await api.getHistory(state.companyId);
    $('#page-content').innerHTML = `<section class="panel"><h2>История сводок</h2><p>Снимки сохраняют контекст компании и основания на момент подготовки.</p>${history.length ? history.map(v => `<button class="history-item" data-digest="${esc(v.id)}"><span>${esc(new Date(v.createdAt).toLocaleString('ru'))}</span><strong>${v.itemCount} событий</strong><span>${esc(v.status)}</span></button>`).join('') : '<p>Сводок пока нет.</p>'}</section>`;
  } catch (error) { toast(error.message); }
}
document.addEventListener('click', async event => {
  const button = event.target.closest('[data-digest]');
  if (!button) return;
  button.disabled = true;
  try {
    const result = await api.restoreDigest(state.companyId, button.dataset.digest);
    state.events = result.items; state.updatedAt = result.updatedAt; state.limitations = result.limitations;
    state.view = 'feed'; state.loading = false; render();
  } catch (error) { toast(error.message); button.disabled = false; }
});
