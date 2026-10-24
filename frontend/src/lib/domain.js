export function filterEvents(
  events,
  { filter = "all", query = "", saved = [], view = "overview" } = {},
) {
  const q = query.trim().toLocaleLowerCase("ru");
  return events.filter(
    (event) =>
      (view !== "saved" || saved.includes(event.id)) &&
      (filter === "all" ||
        (filter === "bank"
          ? event.hasBankAnalysis
          : filter === "risk"
            ? event.risks.length > 0
            : filter === "opportunity"
              ? event.opportunities.length > 0
              : false)) &&
      (!q ||
        `${event.title} ${event.summary} ${event.category}`
          .toLocaleLowerCase("ru")
          .includes(q)),
  );
}

export function contextReasons(event) {
  return event.contextReasons || [];
}
