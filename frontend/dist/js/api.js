import { config } from '../config.js';
import { companies, roles, events, sources } from './data.js';
import { rankEvents, makeDemoAnswer } from './domain.js';

export class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.name = 'ApiError'; this.status = status; }
}
async function request(path, { signal, ...options } = {}) {
  const timeout = AbortSignal.timeout(config.timeoutMs);
  try {
    const response = await fetch(`${config.apiBaseUrl}${path}`, { ...options, signal: signal ? AbortSignal.any([signal, timeout]) : timeout, credentials: 'include', headers: { 'Content-Type': 'application/json', ...options.headers } });
    if (!response.ok) throw new ApiError(response.status === 429 ? 'Лимит запросов исчерпан. Попробуйте позже.' : response.status === 403 ? 'Недостаточно прав для просмотра данных.' : 'Не удалось загрузить данные. Попробуйте ещё раз.', response.status);
    return await response.json();
  } catch (error) {
    if (signal?.aborted) throw error;
    if (error.name === 'TimeoutError') throw new ApiError('Ответ занимает слишком много времени. Повторите запрос.');
    if (error instanceof ApiError) throw error;
    throw new ApiError('Нет связи с сервером. Проверьте подключение.');
  }
}
export const api = {
  async getBootstrap(signal) { return config.mode === 'demo' ? { companies, roles } : request('/bootstrap', { signal }); },
  async getFeed(companyId, roleId, signal) {
    if (config.mode !== 'demo') return request(`/companies/${encodeURIComponent(companyId)}/insights?role=${encodeURIComponent(roleId)}`, { signal });
    const company = companies.find(c => c.id === companyId);
    const role = roles.find(r => r.id === roleId);
    if (!company || !role) throw new ApiError('Компания или роль не найдены.');
    return { items: rankEvents(events, company, role), updatedAt: new Date().toISOString(), demo: true };
  },
  async getInsight(companyId, insightId, signal) {
    if (config.mode !== 'demo') return request(`/companies/${encodeURIComponent(companyId)}/insights/${encodeURIComponent(insightId)}`, { signal });
    const event = events.find(e => e.id === insightId);
    const company = companies.find(c => c.id === companyId);
    if (!event || !company || !event.tags.some(t => company.tags.includes(t))) throw new ApiError('Событие недоступно для этой компании.', 404);
    return { ...event, sources: sources.filter(s => event.sourceIds.includes(s.id)), demo: true };
  },
  async ask(companyId, insightId, message, history, signal) {
    if (config.mode !== 'demo') return request(`/companies/${encodeURIComponent(companyId)}/insights/${encodeURIComponent(insightId)}/questions`, { method: 'POST', body: JSON.stringify({ message, history }), signal });
    const company = companies.find(c => c.id === companyId);
    const event = events.find(e => e.id === insightId);
    if (!company || !event) throw new ApiError('Контекст вопроса не найден.');
    await new Promise((resolve, reject) => {
      const id = setTimeout(resolve, 650);
      signal?.addEventListener('abort', () => { clearTimeout(id); reject(new DOMException('Aborted', 'AbortError')); }, { once: true });
    });
    return { text: makeDemoAnswer(message, event, company), sourceIds: event.sourceIds, demo: true };
  },
  async feedback(companyId, insightId, value) {
    if (config.mode !== 'demo') return request(`/companies/${encodeURIComponent(companyId)}/insights/${encodeURIComponent(insightId)}/feedback`, { method: 'POST', body: JSON.stringify({ value }) });
    return { ok: true, demo: true };
  },
};
