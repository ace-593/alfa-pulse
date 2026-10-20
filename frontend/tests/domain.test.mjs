import test from 'node:test';
import assert from 'node:assert/strict';
import { companies, roles, events, sources } from '../dist/js/data.js';
import { rankEvents, filterEvents, contextReasons, makeDemoAnswer } from '../dist/js/domain.js';
import { api } from '../dist/js/api.js';

test('переключение компании действительно меняет состав ленты', () => {
  const metal = rankEvents(events, companies[0], roles[0]);
  const logistics = rankEvents(events, companies[1], roles[0]);
  const agro = rankEvents(events, companies[2], roles[0]);
  assert(metal.some(e => e.id === 'metal-demand'));
  assert(!logistics.some(e => e.id === 'metal-demand'));
  assert(agro.some(e => e.id === 'grain'));
  assert(!metal.some(e => e.id === 'grain'));
  assert(!agro.some(e => e.id === 'fx'));
});
test('роль влияет на приоритет события, не изменяя исходные данные', () => {
  const cfo = rankEvents(events, companies[0], roles[0]);
  const ceo = rankEvents(events, companies[0], roles[1]);
  assert.notEqual(cfo.find(e => e.id === 'rate').score, ceo.find(e => e.id === 'rate').score);
  assert.equal(events[0].score, undefined);
  assert(cfo.every(e => e.score >= 0 && e.score <= 100));
});
test('каждый показанный разбор имеет основания и существующие источники', () => {
  for (const c of companies) for (const e of rankEvents(events, c, roles[0])) {
    assert(contextReasons(e, c).length > 0);
    assert(e.sourceIds.every(id => sources.some(s => s.id === id)));
    assert(e.missing.length > 0);
  }
});
test('поиск, фильтр и сохранения применяются совместно', () => {
  const ranked = rankEvents(events, companies[0], roles[0]);
  assert.deepEqual(filterEvents(ranked, { filter: 'risk', query: 'СТАВКА', view: 'saved', saved: ['rate'] }).map(e => e.id), ['rate']);
  assert.equal(filterEvents(ranked, { query: 'несуществующая тема' }).length, 0);
  assert.equal(filterEvents(ranked, { view: 'saved', saved: [] }).length, 0);
});
test('демочат честно обозначает ограничения и использует выбранную компанию', () => {
  const answer = makeDemoAnswer('Каких данных не хватает?', events[0], companies[2]);
  assert.match(answer, /Демоответ/);
  assert.match(answer, /АгроГоризонт/);
  assert.match(answer, /задолженности/);
  assert.match(makeDemoAnswer('произвольная тема', events[0], companies[0]), /без подключения LLM/);
});
test('API не отдаёт нерелевантное событие другой компании', async () => {
  await assert.rejects(api.getInsight('agro', 'metal-demand'), /недоступно/);
  const insight = await api.getInsight('metal', 'metal-demand');
  assert.equal(insight.sources.length, 2);
  assert.equal(insight.demo, true);
});
test('незавершённый ответ отменяется при смене контекста', async () => {
  const controller = new AbortController();
  const response = api.ask('metal', 'rate', 'риски', [], controller.signal);
  controller.abort();
  await assert.rejects(response, { name: 'AbortError' });
});
