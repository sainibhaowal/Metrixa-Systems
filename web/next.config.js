/** @type {import('next').NextConfig} */
const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const nextConfig = {
  distDir: process.env.METRIXA_NEXT_DIST_DIR || ".next",
  reactStrictMode: false,
  swcMinify: true,
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBaseUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
