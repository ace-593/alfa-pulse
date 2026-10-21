import test from 'node:test';
import assert from 'node:assert/strict';
import { companyView, insightView, answerView } from '../dist/js/models.js';
import { filterEvents, contextReasons } from '../dist/js/domain.js';

const claim = (text, material = 'bank') => ({ id: text, text, kind: 'model_inference', citations: [{ materialId: material, materialVersion: '1', quote: 'Точный фрагмент' }], featureIds: ['f'], supportingClaimIds: [], assumptions: [] });
const item = { id: 'event', title: 'Ставка', summary: 'Влияние на ликвидность', occurredAt: '2026-10-01T00:00:00Z', relevanceScore: .83, facts: [claim('Факт')], bankPosition: [claim('Позиция банка')], bankPositionStatus: 'available', interpretation: [claim('Вывод')], relevanceExplanation: claim('Серверное основание'), risks: [{ claim: claim('Риск') }], opportunities: [{ claim: claim('Возможность') }], suggestedActions: [claim('Действие')], limitations: [] };
const digest = { id: 'digest', materials: [{ id: 'bank', version: '1', title: 'Банковский отчет', kind: 'bank_analytics', text: 'Точный фрагмент', publisher: 'Банк', publishedAt: null, url: 'https://example.com/report' }], limitations: ['Неполные данные'], runId: 'trace' };

test('компания сохраняет неизвестную выручку и переводит известную в млрд', () => {
  const company = { id: 'c', displayName: 'Компания', mainOkvedName: null };
  const unknown = companyView(company, { features: [], summary: 'Нет данных' });
  assert.equal(unknown.revenue, null);
  assert.equal(unknown.completeness, 0);
  const known = companyView(company, { features: [{ sourceField: 'REVENUE_COMPANY', value: '38000000000', datasetVersion: 'real-v1' }], summary: 'Контекст' });
  assert.equal(known.revenue, 38);
});

test('адаптер переносит основания и явный тип банковского материала', () => {
  const event = insightView(item, digest);
  assert.equal(event.score, 83);
  assert.equal(event.bank, 'Позиция банка');
  assert.equal(event.sources[0].kind, 'bank');
  assert.equal(event.sources[0].excerpt, 'Точный фрагмент');
  assert.deepEqual(contextReasons(event), ['Серверное основание']);
  assert(event.hasBankAnalysis);
  assert.equal(filterEvents([event], { filter: 'bank' }).length, 1);
  assert.equal(filterEvents([event], { filter: 'risk' }).length, 1);
  assert.equal(filterEvents([event], { filter: 'opportunity' }).length, 1);
});

test('поиск и сохранения применяются вместе, входные данные не меняются', () => {
  const event = insightView(item, digest);
  const before = JSON.stringify(event);
  assert.equal(filterEvents([event], { query: 'СТАВКА', view: 'saved', saved: ['event'] }).length, 1);
  assert.equal(filterEvents([event], { query: 'no result' }).length, 0);
  assert.equal(filterEvents([event], { view: 'saved', saved: [] }).length, 0);
  assert.equal(JSON.stringify(event), before);
});

test('ответ чата содержит цитаты, а отсутствие данных показывается явно', () => {
  assert.equal(answerView({ claims: [], materials: [], limitations: ['Нет данных'], status: 'insufficient_data' }, digest).text, 'Нет данных');
  const answer = answerView({ claims: [claim('Ответ')], materials: [], limitations: [], status: 'answered' }, digest);
  assert.equal(answer.text, 'Ответ');
  assert.equal(answer.citations[0].title, 'Банковский отчет');
});
