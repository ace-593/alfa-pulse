import { useCallback, useEffect, useState } from "react";
import { api } from "./lib/api.js";
import { readStore, writeStore } from "./lib/storage.js";

export function usePulse() {
  const [epoch, setEpoch] = useState(0);
  const [bootstrap, setBootstrap] = useState({
    loading: api.hasSession(),
    data: null,
    error: "",
  });
  const [companyId, setCompany] = useState("");
  const [roleId, setRole] = useState("cfo");
  const [revision, setRevision] = useState(0);
  const [feed, setFeed] = useState({
    items: [],
    loading: false,
    error: "",
    limitations: [],
  });
  const [notice, setNotice] = useState("");
  const [, invalidateStorage] = useState(0);
  const reload = useCallback(() => setEpoch((v) => v + 1), []);

  useEffect(() => {
    if (!api.hasSession()) {
      setBootstrap({ loading: false, data: null, error: "" });
      return;
    }
    const controller = new AbortController();
    setBootstrap({ loading: true, data: null, error: "" });
    api
      .getBootstrap(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        const savedCompany = readStore(data.user.id, "company", "");
        const savedRole = readStore(data.user.id, "role", "cfo");
        setCompany(
          data.companies.find((c) => c.id === savedCompany)?.id ||
            data.companies[0]?.id ||
            "",
        );
        setRole(
          data.roles.find((r) => r.id === savedRole)?.id ||
            data.roles[0]?.id ||
            "cfo",
        );
        setBootstrap({ loading: false, data, error: "" });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setBootstrap({
            loading: false,
            data: null,
            error: error.status === 401 ? "" : error.message,
          });
      });
    return () => controller.abort();
  }, [epoch]);

  const user = bootstrap.data?.user;
  useEffect(() => {
    if (!user || !companyId) return;
    const controller = new AbortController();
    setFeed({ items: [], loading: true, error: "", limitations: [] });
    writeStore(user.id, "company", companyId);
    writeStore(user.id, "role", roleId);
    api
      .getFeed(companyId, roleId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted)
          setFeed({ ...result, loading: false, error: "" });
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        if (error.status === 401) reload();
        else
          setFeed({
            items: [],
            loading: false,
            error: error.message,
            limitations: [],
          });
      });
    return () => controller.abort();
  }, [user, companyId, roleId, revision, reload]);

  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  const saved = readStore(user?.id, `saved:${companyId}`, []);
  const toggleSave = (id) => {
    const next = saved.includes(id)
      ? saved.filter((v) => v !== id)
      : [...saved, id];
    writeStore(user.id, `saved:${companyId}`, next);
    invalidateStorage((v) => v + 1);
    setNotice(
      next.includes(id)
        ? "Событие сохранено"
        : "Событие удалено из сохранённого",
    );
  };
  const restore = useCallback(
    (result) => setFeed({ ...result, loading: false, error: "" }),
    [],
  );
  const refresh = () => setRevision((v) => v + 1);
  const logout = async () => {
    try {
      await api.logout();
    } catch {
      /* api.logout always clears the session. */
    }
    setFeed({ items: [], loading: false, error: "", limitations: [] });
    reload();
  };
  return {
    bootstrap,
    user,
    companyId,
    roleId,
    setCompany,
    setRole,
    feed,
    saved,
    toggleSave,
    refresh,
    restore,
    logout,
    reload,
    notice,
    notify: setNotice,
  };
}
