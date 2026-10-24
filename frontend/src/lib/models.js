export const roles = [
  { id: "owner", name: "Собственник", short: "Бизнес" },
  { id: "ceo", name: "Генеральный директор", short: "Управление" },
  { id: "cfo", name: "Финансовый директор", short: "Финансы" },
  { id: "chief_accountant", name: "Главный бухгалтер", short: "Учёт" },
  { id: "treasurer", name: "Казначей", short: "Казначейство" },
  { id: "other", name: "Другая роль", short: "Аналитика" },
];

export function companyView(company, context) {
  const features = context.features || [];
  const value = (field) => features.find((f) => f.sourceField === field)?.value;
  const revenue = Number(value("REVENUE_COMPANY"));
  const synthetic = features.some((f) => f.datasetVersion === "synthetic-v1");
  const known = features.filter(
    (f) => f.value !== null && f.value !== undefined,
  ).length;
  return {
    id: company.id,
    name: company.displayName,
    initials: company.displayName
      .split(" ")
      .map((x) => x[0])
      .join("")
      .slice(0, 2),
    industry: company.mainOkvedName || "Нет данных",
    okved: company.mainOkvedCode || "—",
    revenue:
      value("REVENUE_COMPANY") === undefined ||
      value("REVENUE_COMPANY") === null ||
      !Number.isFinite(revenue)
        ? null
        : revenue / (synthetic ? 1 : 1e9),
    region: company.region || "Нет данных",
    city: company.city || "Нет данных",
    group: company.groupId,
    workers:
      value("AMOUNT_WORKERS_FNS_GRADATION") || value("WORKERS") || "Нет данных",
    products:
      value("BANK_PRODUCTS")?.split(", ") ||
      ["CL_PRODUCT_LOA_MARK", "CL_PRODUCT_DEP_MARK", "CL_PRODUCT_LEA_MARK"]
        .filter((key) =>
          ["1", "true", "да"].includes(String(value(key)).toLowerCase()),
        )
        .map(
          (key) =>
            ({
              CL_PRODUCT_LOA_MARK: "Кредитование",
              CL_PRODUCT_DEP_MARK: "Депозиты",
              CL_PRODUCT_LEA_MARK: "Лизинг",
            })[key],
        ),
    countries: value("FTS_COUNTRY_NAME")?.split(", ") || [],
    description: context.summary,
    completeness: features.length
      ? Math.round((100 * known) / features.length)
      : 0,
    tags: [],
    color: "#dce9e5",
    synthetic,
  };
}

const text = (claims) => (claims || []).map((c) => c.text).join("\n\n");
export function insightView(item, digest) {
  const allClaims = [
    ...item.facts,
    ...item.bankPosition,
    ...item.interpretation,
    item.relevanceExplanation,
    ...item.risks.map((v) => v.claim),
    ...item.opportunities.map((v) => v.claim),
    ...item.suggestedActions,
  ];
  const ids = [
    ...new Set(allClaims.flatMap((v) => v.citations.map((c) => c.materialId))),
  ];
  const sources = digest.materials
    .filter((v) => ids.includes(v.id))
    .map((source) => {
      const quotes = allClaims
        .flatMap((v) => v.citations)
        .filter((v) => v.materialId === source.id)
        .map((v) => v.quote);
      return {
        id: source.id,
        kind: source.kind === "bank_analytics" ? "bank" : "fact",
        title: source.title,
        publisher: source.publisher,
        date: source.publishedAt
          ? new Date(source.publishedAt).toLocaleDateString("ru")
          : "Дата неизвестна",
        excerpt: [...new Set(quotes)].join("\n\n"),
        url: source.url,
      };
    });
  const published = item.occurredAt ? new Date(item.occurredAt) : null;
  return {
    id: item.id,
    title: item.title,
    summary: item.summary,
    fact: text(item.facts),
    bank:
      item.bankPositionStatus === "not_found"
        ? "Подтвержденная позиция банка по этому событию не найдена."
        : text(item.bankPosition),
    risks: item.risks.map((v) => v.claim.text),
    opportunities: item.opportunities.map((v) => v.claim.text),
    actions: item.suggestedActions.map((v) => v.text),
    missing: [...item.limitations, ...digest.limitations],
    sourceIds: ids,
    sources,
    hasBankAnalysis: sources.some((s) => s.kind === "bank"),
    score: Math.round(item.relevanceScore * 100),
    kind: item.risks.length ? "risk" : "opportunity",
    category: "Бизнес-аналитика",
    age: published
      ? Math.max(0, Math.floor((Date.now() - published.getTime()) / 86400000))
      : Number.MAX_SAFE_INTEGER,
    time: published
      ? published.toLocaleTimeString("ru", {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "—",
    minutes: Math.max(1, Math.ceil(text(allClaims).length / 1300)),
    contextReasons: [item.relevanceExplanation.text],
    tags: [],
    claims: allClaims,
    runId: digest.runId,
  };
}

export function answerView(answer, digest) {
  const materials = [...digest.materials, ...answer.materials];
  const ids = [
    ...new Set(
      answer.claims.flatMap((v) => v.citations.map((c) => c.materialId)),
    ),
  ];
  return {
    text: text(answer.claims) || answer.limitations.join("\n"),
    citations: materials
      .filter((v) => ids.includes(v.id))
      .map((v) => ({ id: v.id, title: v.title, url: v.url })),
    status: answer.status,
  };
}
