import test from 'node:test';
import assert from 'node:assert/strict';
import { createApi } from '../dist/js/api.js';

function storage() {
  const values = new Map();
  return { getItem: k => values.get(k) ?? null, setItem: (k, v) => values.set(k, v), removeItem: k => values.delete(k) };
}
const reply = (body, status = 200) => new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

test('вход сохраняет токены и выход корректно обрабатывает 204', async () => {
  const calls = [];
  const client = createApi({ storage: storage(), fetcher: async (url, options) => {
    calls.push([url, options]);
    return url.endsWith('/auth/login') ? reply({ user: { id: 'user' }, tokens: { accessToken: 'access', refreshToken: 'refresh' } }) : reply(null, 204);
  } });
  await client.login('user@example.com', 'Example-password-321');
  assert(client.hasSession());
  await client.logout();
  assert.equal(calls[1][1].headers.Authorization, 'Bearer access');
  assert(!client.hasSession());
});

test('параллельные запросы используют одно обновление токена', async () => {
  const store = storage();
  store.setItem('pulse:session', JSON.stringify({ accessToken: 'old', refreshToken: 'refresh' }));
  let refreshes = 0;
  const client = createApi({ storage: store, fetcher: async (url, options) => {
    if (url.endsWith('/auth/refresh')) { refreshes++; await new Promise(resolve => setTimeout(resolve, 10)); return reply({ accessToken: 'new', refreshToken: 'new-refresh' }); }
    if (options.headers.Authorization === 'Bearer old') return reply({ message: 'Expired' }, 401);
    return reply({ items: [], nextCursor: null });
  } });
  await Promise.all([client.getHistory('c'), client.getHistory('c')]);
  assert.equal(refreshes, 1);
});

test('лента создается через preferences, digests и jobs, не через старые ручки', async () => {
  const urls = [];
  const client = createApi({ storage: storage(), delay: async () => {}, fetcher: async (url, options) => {
    urls.push(url);
    if (url.endsWith('/preferences')) return reply({ role: 'other', topics: [], regions: [], scope: 'company' });
    if (url.endsWith('/digests') && options.method === 'POST') {
      assert(options.headers['Idempotency-Key']);
      return reply({ id: 'job', status: 'queued' }, 202);
    }
    if (url.endsWith('/jobs/job')) return reply({ id: 'job', status: 'succeeded', result: { href: '/api/v1/companies/c/digests/d' } });
    return reply({ id: 'd', items: [], materials: [], createdAt: '2026-10-21T00:00:00Z', limitations: [] });
  } });
  const result = await client.getFeed('c', 'cfo');
  assert.deepEqual(result.items, []);
  assert(urls.some(v => v.endsWith('/jobs/job')));
  assert(!urls.some(v => v.includes('bootstrap') || v.includes('insights')));
});

test('отмена запроса не превращается в общую сетевую ошибку', async () => {
  const controller = new AbortController();
  const client = createApi({ storage: storage(), fetcher: async () => { controller.abort(); throw new DOMException('Aborted', 'AbortError'); } });
  await assert.rejects(client.getHistory('c', controller.signal), { name: 'AbortError' });
});
