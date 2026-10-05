// Public build-time API origin. A missing/unsafe value never falls back to a guessed server:
// credentials (ID tokens, booking links) must go only to an explicitly selected API.
export function readApiOrigin(apiOrigin: string | undefined, mode: string | undefined): string | null {
  if (!apiOrigin) return null;
  try {
    const url = new URL(apiOrigin.trim());
    const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    const safeProtocol = url.protocol === "https:" || (url.protocol === "http:" && loopback && mode === "development");
    if (!safeProtocol || url.username || url.password || url.search || url.hash || url.pathname !== "/") return null;
    return url.origin;
  } catch {
    return null;
  }
}
