import { NextResponse, type NextRequest } from "next/server";

import { readAdminConfig } from "@/lib/admin/config";
import { readApiOrigin } from "@/lib/api-origin";

const GOOGLE_GSI = "https://accounts.google.com/gsi/";

// Every page gets a per-request nonce CSP (pages render dynamically for it): injected markup
// cannot run script or send data elsewhere. /admin keeps a Google ID token; /reserva keeps the
// booking link token (read from the URL fragment, never sent to this server); public pages post
// the contact form to the API.
export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const development = process.env.NODE_ENV === "development";
  const admin = request.nextUrl.pathname.startsWith("/admin");
  const apiOrigin = admin
    ? readAdminConfig(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID, process.env.NEXT_PUBLIC_API_BASE_URL, process.env.NODE_ENV)?.apiOrigin
    : readApiOrigin(process.env.NEXT_PUBLIC_API_BASE_URL, process.env.NODE_ENV);
  const google = admin ? ` ${GOOGLE_GSI}` : "";
  const policy = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${admin ? ` ${GOOGLE_GSI}client` : ""}${development ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'unsafe-inline'${admin ? ` ${GOOGLE_GSI}style` : ""}`,
    `connect-src 'self'${google}${apiOrigin ? ` ${apiOrigin}` : ""}`,
    admin ? `frame-src ${GOOGLE_GSI}` : "frame-src 'none'",
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
  const private_ = admin || request.nextUrl.pathname === "/reserva";
  if (private_) {
    response.headers.set("Cache-Control", "no-store");
    response.headers.set("Referrer-Policy", "no-referrer");
    response.headers.set("X-Robots-Tag", "noindex, nofollow");
  }
  return response;
}

export const config = {
  matcher: [
    {
      // Pages only: no static assets, images, metadata files or prefetches.
      source: "/((?!_next/static|_next/image|favicon.ico|icon.svg|robots.txt|sitemap.xml).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
