export const config = Object.freeze({
  apiBaseUrl: "/api/v1",
  timeoutMs: 20000,
  jobTimeoutMs: 600000,
  ...globalThis.PULSE_CONFIG,
});
