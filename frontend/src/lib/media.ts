/** Explicit media origins owned/configured by the clinic; invalid configuration stays closed. */
export function mediaOrigins(raw: string | undefined): URL[] {
  if (!raw) return [];
  try {
    const values: unknown = JSON.parse(raw);
    if (!Array.isArray(values) || !values.every((value) => typeof value === "string")) return [];
    const origins = values.map((value: string) => {
      const url = new URL(value);
      if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
        throw new Error("Invalid media origin");
      }
      return url.origin;
    });
    return [...new Set(origins)].map((origin) => new URL(origin));
  } catch {
    return [];
  }
}
