import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

/** Orígenes a los que el navegador puede llamar: la API del monitor y la del CMM. */
function apiOrigins(): string[] {
  const urls = [
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    process.env.NEXT_PUBLIC_CMM_API_URL || "http://localhost:8001/api/v1",
  ];
  return [...new Set(urls.map((u) => new URL(u).origin))];
}

// El token del CMM vive en localStorage: la CSP es la barrera contra un XSS
// que intente leerlo o mandarlo a otro dominio (connect-src solo a las APIs).
// Next inyecta scripts inline al hidratar, por eso 'unsafe-inline'; en
// desarrollo el HMR además necesita 'unsafe-eval' y websockets.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiOrigins().join(" ")}${isDev ? " ws: wss:" : ""}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(isDev ? [] : ["upgrade-insecure-requests"]),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]),
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
