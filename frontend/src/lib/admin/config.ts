import { readApiOrigin } from "../api-origin";

export type AdminConfig = { clientId: string; apiOrigin: string };

// Public build-time configuration only. A missing/unsafe origin never falls back
// to a guessed API: credentials must go only to an explicitly selected server.
export function readAdminConfig(
  clientId: string | undefined,
  apiOrigin: string | undefined,
  mode: string | undefined,
): AdminConfig | null {
  if (!clientId || !/^\d+-[a-zA-Z0-9_-]+\.apps\.googleusercontent\.com$/.test(clientId.trim())) return null;
  const origin = readApiOrigin(apiOrigin, mode);
  return origin ? { clientId: clientId.trim(), apiOrigin: origin } : null;
}
