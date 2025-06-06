import type { NextConfig } from "next";

const api = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8011";

const nextConfig: NextConfig = {
  basePath: "/admin",
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  // In production Caddy sends /v1 and the widget files straight to the API.
  // These rewrites keep the same URLs working when the admin runs on its own.
  async rewrites() {
    return [
      { source: "/v1/:path*", destination: `${api}/v1/:path*`, basePath: false },
      { source: "/widget.js", destination: `${api}/widget.js`, basePath: false },
      { source: "/widget-app.js", destination: `${api}/widget-app.js`, basePath: false },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
