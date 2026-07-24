import type { NextConfig } from "next";

const FASTAPI_BASE = process.env.FASTAPI_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${FASTAPI_BASE}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
