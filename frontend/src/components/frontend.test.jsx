import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Auth from "./Auth.jsx";
import Dashboard from "./Dashboard.jsx";
import InsightDialog, { Chat } from "./InsightDialog.jsx";
import { usePulse } from "../usePulse.js";
import { api } from "../lib/api.js";

vi.mock("../lib/api.js", () => ({
  api: {
    hasSession: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    getBootstrap: vi.fn(),
    getFeed: vi.fn(),
    getInsight: vi.fn(),
    getTrace: vi.fn(),
    ask: vi.fn(),
    feedback: vi.fn(),
  },
}));
const company = {
  id: "c",
  name: "Металл",
  industry: "Производство",
  initials: "М",
  products: [],
  revenue: null,
  completeness: 0,
  region: "Москва",
};
const role = { id: "cfo", name: "Финансовый директор" };
const event = {
  id: "e",
  title: "Ставка и кредитование",
  summary: "Изменения для бизнеса",
  kind: "risk",
  category: "Экономика",
  time: "12:00",
  contextReasons: ["Кредитная нагрузка"],
  risks: ["Дорогой кредит"],
  opportunities: [],
  actions: [],
  missing: [],
  sources: [],
  fact: "Факт",
  bank: "Нет данных",
  score: 90,
  age: 0,
  minutes: 2,
};
const opportunity = {
  ...event,
  id: "o",
  title: "Новые рынки",
  kind: "opportunity",
  risks: [],
  opportunities: ["Экспорт"],
};
beforeEach(() => {
  vi.resetAllMocks();
});

describe("React-интерфейс", () => {
  it("показывает ошибку входа и позволяет повторно отправить форму", async () => {
    const user = userEvent.setup();
    api.login
      .mockRejectedValueOnce(new Error("Неверный пароль"))
      .mockResolvedValueOnce({ id: "u" });
    const onSuccess = vi.fn();
    render(<Auth onSuccess={onSuccess} />);
    await user.type(
      screen.getByLabelText("Электронная почта"),
      "user@example.com",
    );
    await user.type(screen.getByLabelText("Пароль"), "long-password-123");
    await user.click(
      screen.getByRole("button", { name: "Войти", exact: true }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Неверный пароль",
    );
    await user.click(
      screen.getByRole("button", { name: "Войти", exact: true }),
    );
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
    expect(api.login).toHaveBeenLastCalledWith(
      "user@example.com",
      "long-password-123",
    );
  });

  it("сочетает фильтры с поиском, сохраняет фокус ввода и закладки", async () => {
    const user = userEvent.setup();
    const save = vi.fn();
    const pulse = {
      feed: { items: [event, opportunity], limitations: [], loading: false },
      saved: [],
      toggleSave: save,
      refresh: vi.fn(),
    };
    render(
      <Dashboard
        pulse={pulse}
        company={company}
        role={role}
        view="feed"
        navigate={vi.fn()}
        onOpen={vi.fn()}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Риски", exact: true }),
    );
    expect(
      screen.queryByRole("button", { name: "Новые рынки" }),
    ).not.toBeInTheDocument();
    const search = screen.getByRole("searchbox");
    await user.type(search, "СТАВКА");
    expect(search).toHaveFocus();
    expect(
      screen.getByRole("button", { name: "Ставка и кредитование" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Сохранить событие" }));
    expect(save).toHaveBeenCalledWith("e");
    await user.type(search, " неизвестное");
    expect(screen.getByText("Событий не найдено")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Сбросить фильтры" }));
    expect(search).toHaveValue("");
    expect(
      screen.getByRole("button", { name: "Новые рынки" }),
    ).toBeInTheDocument();
  });

  it("показывает пустое сохранённое и переход в ленту", () => {
    const navigate = vi.fn();
    render(
      <Dashboard
        pulse={{ feed: { items: [event], limitations: [] }, saved: [] }}
        company={company}
        role={role}
        view="saved"
        navigate={navigate}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Перейти к событиям" }));
    expect(navigate).toHaveBeenCalledWith("feed");
    expect(
      screen.queryByRole("button", { name: event.title }),
    ).not.toBeInTheDocument();
  });

  it("отменяет прошлую ленту при смене компании и игнорирует запоздалый ответ", async () => {
    api.hasSession.mockReturnValue(true);
    api.getBootstrap.mockResolvedValue({
      user: { id: "u" },
      companies: [company, { ...company, id: "second" }],
      roles: [role],
    });
    let resolveFirst;
    api.getFeed
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockResolvedValueOnce({ items: [opportunity], limitations: [] });
    const { result } = renderHook(() => usePulse());
    await waitFor(() => expect(api.getFeed).toHaveBeenCalledOnce());
    const signal = api.getFeed.mock.calls[0][2];
    act(() => result.current.setCompany("second"));
    await waitFor(() =>
      expect(result.current.feed.items).toEqual([opportunity]),
    );
    expect(signal.aborted).toBe(true);
    await act(async () => resolveFirst({ items: [event], limitations: [] }));
    expect(result.current.feed.items).toEqual([opportunity]);
  });

  it("сохраняет вопрос после ошибки чата и позволяет повторить запрос", async () => {
    const user = userEvent.setup();
    api.ask
      .mockRejectedValueOnce(new Error("Нет связи"))
      .mockResolvedValueOnce({ text: "Ответ с основаниями", citations: [] });
    render(<Chat companyId="c" eventId="e" />);
    const input = screen.getByRole("textbox", {
      name: "Вопрос об этом событии",
    });
    await user.type(input, "Что проверить?");
    await user.click(screen.getByRole("button", { name: "Отправить вопрос" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Нет связи");
    expect(input).toHaveValue("Что проверить?");
    await user.click(screen.getByRole("button", { name: "Отправить вопрос" }));
    expect(await screen.findByText("Ответ с основаниями")).toBeInTheDocument();
  });

  it("оставляет разбор доступным при ошибке трассировки, экранирует текст и блокирует javascript-ссылки", async () => {
    const user = userEvent.setup();
    api.getInsight.mockResolvedValue({
      ...event,
      fact: "<img src=x onerror=alert(1)>",
      sources: [
        {
          id: "s",
          title: "Источник",
          url: "javascript:alert(1)",
          date: "Сегодня",
          excerpt: "Цитата",
        },
      ],
    });
    api.getTrace.mockRejectedValue(new Error("Трассировка недоступна"));
    const close = vi.fn();
    render(
      <InsightDialog
        id="e"
        company={company}
        role={role}
        user={{ id: "u" }}
        onClose={close}
        notify={vi.fn()}
      />,
    );
    expect(
      await screen.findByText("<img src=x onerror=alert(1)>"),
    ).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
    const sourceTab = screen.getByRole("tab", { name: /Источники/ });
    await user.click(sourceTab);
    expect(
      screen.queryByRole("link", { name: "Открыть первоисточник" }),
    ).not.toBeInTheDocument();
    fireEvent.keyDown(sourceTab, { key: "ArrowRight" });
    expect(
      screen.getByRole("tab", { name: "Как получен вывод" }),
    ).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Трассировка недоступна",
    );
    await user.click(screen.getByRole("button", { name: "Закрыть разбор" }));
    expect(close).toHaveBeenCalledOnce();
  });
});
