import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};
window.scrollTo = () => {};
afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
  location.hash = "";
});
