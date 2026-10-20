// Production integration: set mode to 'http' and a trusted HTTPS API origin.
// No LLM keys or confidential client data belong in this file.
export const config = Object.freeze({ mode: 'demo', apiBaseUrl: '/api', timeoutMs: 20000 });
