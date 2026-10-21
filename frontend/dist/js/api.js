import { config } from '../config.js';
import { companyView, insightView, answerView, roles } from './models.js';

export class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.name = 'ApiError'; this.status = status; }
}

export function createApi({ baseUrl = config.apiBaseUrl, fetcher = (...args) => fetch(...args), storage = globalThis.sessionStorage, delay = (ms, signal) => new Promise((resolve, reject) => {
  const abort = () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')); };
  const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, ms);
  if (signal?.aborted) abort(); else signal?.addEventListener('abort', abort, { once: true });
}) } = {}) {
  let refreshing, user;
  const digests = new Map();
  const read = () => { try { return JSON.parse(storage.getItem('pulse:session') || 'null'); } catch { return null; } };
  const save = value => storage.setItem('pulse:session', JSON.stringify(value));
  const clear = () => { storage.removeItem('pulse:session'); digests.clear(); user = null; };
  const path = id => encodeURIComponent(id);
  async function request(route, { signal, auth = true, retry = true, ...options } = {}) {
    const tokens = read();
    const timeout = AbortSignal.timeout(config.timeoutMs);
    let response;
    try {
      response = await fetcher(`${baseUrl}${route}`, { ...options, signal: signal ? AbortSignal.any([signal, timeout]) : timeout, headers: {
        'Content-Type': 'application/json', ...(auth && tokens ? { Authorization: `Bearer ${tokens.accessToken}` } : {}), ...options.headers,
      } });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new ApiError(error.name === 'TimeoutError' ? 'Сервер отвечает слишком долго.' : 'Нет связи с сервером.');
    }
    if (response.status === 401 && auth && retry && tokens?.refreshToken) {
      if (!refreshing) refreshing = request('/auth/refresh', { method: 'POST', auth: false, body: JSON.stringify({ refreshToken: tokens.refreshToken }) }).then(save).catch(error => { clear(); throw error; }).finally(() => { refreshing = null; });
      try { await refreshing; } catch { throw new ApiError('Сессия истекла. Войди снова.', 401); }
      return request(route, { signal, auth, retry: false, ...options });
    }
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      if (response.status === 401 && auth) clear();
      throw new ApiError(error.message || 'Не удалось выполнить запрос.', response.status);
    }
    return response.status === 204 ? null : response.json();
  }
  async function all(route, signal) {
    const values = []; let cursor;
    do {
      const response = await request(`${route}${route.includes('?') ? '&' : '?'}limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`, { signal });
      values.push(...response.items); cursor = response.nextCursor;
    } while (cursor);
    return values;
  }
  async function job(route, body, signal) {
    const started = await request(route, { method: 'POST', signal, headers: { 'Idempotency-Key': globalThis.crypto.randomUUID() }, body: JSON.stringify(body) });
    const expires = Date.now() + config.jobTimeoutMs;
    let current = started;
    while (!['succeeded', 'failed'].includes(current.status)) {
      if (Date.now() > expires) throw new ApiError('Задача продолжает выполняться. Открой историю сводок позже.');
      await delay(1000, signal);
      current = await request(`/jobs/${path(started.id)}`, { signal });
    }
    if (current.status === 'failed') throw new ApiError(current.error?.message || 'Не удалось подготовить аналитику.');
    if (!current.result.href.startsWith('/api/v1/')) throw new ApiError('Некорректная ссылка на результат.');
    return request(current.result.href.slice('/api/v1'.length), { signal });
  }
  function current(companyId) {
    const digest = digests.get(companyId);
    if (!digest) throw new ApiError('Сначала загрузи сводку.');
    return digest;
  }
  return {
    hasSession: () => Boolean(read()), currentUser: () => user,
    async login(email, password) { const response = await request('/auth/login', { method: 'POST', auth: false, body: JSON.stringify({ email, password }) }); clear(); save(response.tokens); user = response.user; return user; },
    async register(email, password, displayName) { const response = await request('/auth/register', { method: 'POST', auth: false, body: JSON.stringify({ email, password, displayName }) }); clear(); save(response.tokens); user = response.user; return user; },
    async logout() { try { await request('/auth/logout', { method: 'POST' }); } finally { clear(); } },
    async getBootstrap(signal) {
      user = await request('/me', { signal });
      const companies = await all('/companies', signal);
      const mapped = await Promise.all(companies.map(async company => companyView(company, await request(`/companies/${path(company.id)}/context`, { signal }))));
      return { companies: mapped, roles, user };
    },
    async getFeed(companyId, roleId, signal) {
      const root = `/companies/${path(companyId)}`;
      const preferences = await request(`${root}/preferences`, { signal });
      await request(`${root}/preferences`, { method: 'PUT', signal, body: JSON.stringify({ ...preferences, role: roleId }) });
      const now = new Date();
      const digest = await job(`${root}/digests`, { scope: preferences.scope, period: { from: new Date(now.getTime() - 30*86400000).toISOString(), to: new Date(now.getTime() + 1000).toISOString() }, maxItems: 50 }, signal);
      digests.set(companyId, digest);
      return { items: digest.items.map(item => insightView(item, digest)), updatedAt: digest.createdAt, limitations: digest.limitations };
    },
    async getInsight(companyId, insightId, signal) {
      const cached = current(companyId);
      const digest = await request(`/companies/${path(companyId)}/digests/${path(cached.id)}`, { signal });
      const item = digest.items.find(v => v.id === insightId);
      if (!item) throw new ApiError('Событие не найдено в сводке.', 404);
      return insightView(item, digest);
    },
    async ask(companyId, insightId, message, history, signal) {
      const digest = current(companyId);
      const result = await job(`/companies/${path(companyId)}/digests/${path(digest.id)}/questions`, { question: message, insightId, ...(digest._answerId ? { parentAnswerId: digest._answerId } : {}) }, signal);
      digest._answerId = result.id;
      return answerView(result, digest);
    },
    async feedback(companyId, insightId, value) {
      const digest = current(companyId);
      return request(`/companies/${path(companyId)}/digests/${path(digest.id)}/feedback`, { method: 'POST', body: JSON.stringify({ targetType: 'insight', targetId: insightId, rating: value === 'useful' ? 'useful' : 'not_useful', reasons: value === 'useful' ? [] : ['irrelevant'] }) });
    },
    async getTrace(companyId, signal) { return request(`/runs/${path(current(companyId).runId)}/trace`, { signal }); },
    async getHistory(companyId, signal) { return all(`/companies/${path(companyId)}/digests`, signal); },
    async restoreDigest(companyId, digestId, signal) {
      const digest = await request(`/companies/${path(companyId)}/digests/${path(digestId)}`, { signal });
      digests.set(companyId, digest);
      return { items: digest.items.map(v => insightView(v, digest)), updatedAt: digest.createdAt, limitations: digest.limitations };
    },
  };
}

export const api = createApi();
