import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

class ErrorBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main id="main" className="startup">
        <h1>Не удалось открыть интерфейс</h1>
        <p>Обновите страницу, чтобы попробовать ещё раз.</p>
        <button className="button primary" onClick={() => location.reload()}>
          Обновить страницу
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
createRoot(document.getElementById("app")).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
