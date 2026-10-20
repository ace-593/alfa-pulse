export function rankEvents(events, company, role) {
  return events.map(event => {
    const matches = event.tags.filter(tag => company.tags.includes(tag));
    const focus = event.tags.filter(tag => role.focus.includes(tag));
    const score = Math.min(99, 35 + matches.length * 18 + focus.length * 7 + (event.age === 1 ? 4 : 0));
    return { ...event, score, matches };
  }).filter(event => event.matches.length > 0).sort((a, b) => b.score - a.score || a.age - b.age);
}

export function filterEvents(events, { filter = 'all', query = '', saved = [], view = 'overview' } = {}) {
  const q = query.trim().toLocaleLowerCase('ru');
  return events.filter(e => (view !== 'saved' || saved.includes(e.id)) &&
    (filter === 'all' || (filter === 'bank' ? e.sourceIds.some(s => s.startsWith('b-')) : e.kind === filter)) &&
    (!q || `${e.title} ${e.summary} ${e.category}`.toLocaleLowerCase('ru').includes(q)));
}

export function contextReasons(event, company) {
  const reasons = [];
  if (event.tags.includes('credit') && company.tags.includes('credit')) reasons.push('В профиле компании есть кредитные продукты');
  if (event.tags.includes('leasing') && company.tags.includes('leasing')) reasons.push('В профиле компании есть лизинговые продукты');
  if (event.tags.includes('fx') && company.tags.includes('fx')) reasons.push(`Есть внешнеторговые связи: ${company.countries.join(', ')}`);
  if (event.tags.includes('deposit') && company.tags.includes('deposit')) reasons.push('В профиле компании есть депозитные продукты');
  if (event.tags.includes('metal') && company.tags.includes('metal')) reasons.push(`Отрасль компании — ${company.industry.toLowerCase()}`);
  if (event.tags.includes('logistics') && company.tags.includes('logistics')) reasons.push('Основной вид деятельности связан с грузоперевозками');
  if (event.tags.includes('agro') && company.tags.includes('agro')) reasons.push('Основной вид деятельности — выращивание зерновых');
  return reasons;
}

export function makeDemoAnswer(question, event, company) {
  const q = question.toLocaleLowerCase('ru');
  const reasons = contextReasons(event, company).join('. ');
  if (/источник|основан|откуда|банк/.test(q)) return `Демоответ. Основание персонализации: ${reasons}. Использованы синтетическая новость и название материала банка из кейса. Оригинал отчёта не загружен, поэтому подтвердить позицию банка нельзя. Откройте «Источники», чтобы проверить статус каждого материала.`;
  if (/данн|не хватает|уточн/.test(q)) return `Демоответ. Для более точного анализа нужны: ${event.missing.join(', ').toLowerCase()}. Пока можно описать направления влияния, но нельзя надёжно рассчитать денежный эффект для компании «${company.name}».`;
  if (/сценар|разрез|сравн|если/.test(q)) return `Демоответ: сценарный разрез для компании «${company.name}». Базовый вариант: ${event.risks[0]} Альтернативный вариант: ${event.opportunities[0]} Для количественного сравнения нужны: ${event.missing.join(', ').toLowerCase()}. Это шаблон демонстрации, реальный агент не подключён.`;
  if (/делать|действ|шаг/.test(q)) return `Демоответ. Возможные следующие шаги: ${event.actions.join(' ')} Основание: ${reasons}. Выбор действия требует проверки недостающих данных: ${event.missing.join(', ').toLowerCase()}.`;
  if (/риск|влия|важно|компан/.test(q)) return `Демоответ для компании «${company.name}»: ${reasons}. Возможные риски: ${event.risks.join(' ')} Возможность: ${event.opportunities[0]} ${event.missing.length ? `Точность ограничена: нужны ${event.missing.join(', ').toLowerCase()}.` : ''}`;
  return `Это демонстрационный чат без подключения LLM. Он показывает работу с контекстом события «${event.title}» и компании «${company.name}». Попробуйте спросить о рисках, источниках, сценариях, следующих действиях или недостающих данных. Произвольные вопросы обрабатываются после подключения API.`;
}
