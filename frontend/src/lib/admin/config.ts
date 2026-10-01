export type AdminConfig = { clientId: string; apiOrigin: string };

// Public build-time configuration only. A missing/unsafe origin never falls back
// to a guessed API: credentials must go only to an explicitly selected server.
export function readAdminConfig(
  clientId: string | undefined,
  apiOrigin: string | undefined,
  mode: string | undefined,
): AdminConfig | null {
  if (!clientId || !/^\d+-[a-zA-Z0-9_-]+\.apps\.googleusercontent\.com$/.test(clientId.trim()) || !apiOrigin) return null;
  try {
    const url = new URL(apiOrigin.trim());
    const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    const safeProtocol = url.protocol === "https:" || (url.protocol === "http:" && loopback && mode === "development");
    if (!safeProtocol || url.username || url.password || url.search || url.hash || url.pathname !== "/") return null;
    return { clientId: clientId.trim(), apiOrigin: url.origin };
  } catch {
    return null;
  }
}
