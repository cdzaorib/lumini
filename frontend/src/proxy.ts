import { NextResponse, type NextRequest } from "next/server";

import { readAdminConfig } from "@/lib/admin/config";

const GOOGLE_GSI = "https://accounts.google.com/gsi/";

// The admin page keeps a Google ID token in memory, so it gets a per-request
// nonce CSP: injected markup cannot run script or send the token elsewhere.
export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const development = process.env.NODE_ENV === "development";
  const config = readAdminConfig(
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
    process.env.NEXT_PUBLIC_API_BASE_URL,
    process.env.NODE_ENV,
  );
  const policy = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' ${GOOGLE_GSI}client${development ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'unsafe-inline' ${GOOGLE_GSI}style`,
    `connect-src 'self' ${GOOGLE_GSI}${config ? ` ${config.apiOrigin}` : ""}`,
    `frame-src ${GOOGLE_GSI}`,
    "img-src 'self' data:",
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export const config = { matcher: ["/admin/:path*"] };
