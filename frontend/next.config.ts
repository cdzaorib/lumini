import type { NextConfig } from "next";
import { mediaOrigins } from "./src/lib/media";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  turbopack: { root: __dirname },
  images: {
    maximumRedirects: 0,
    remotePatterns: mediaOrigins(process.env.LUMINI_MEDIA_ORIGINS).map((origin) => ({
      protocol: "https" as const,
      hostname: origin.hostname,
      port: origin.port,
      pathname: "/**",
      search: "",
    })),
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          // Closed to search engines until the launch gate (LUMINI_SITE_PUBLIC=true at build).
          ...(process.env.LUMINI_SITE_PUBLIC === "true"
            ? []
            : [{ key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" }]),
        ],
      },
    ];
  },
};

export default nextConfig;
