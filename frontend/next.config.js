/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/runs/:runId",
        destination: `${apiUrl}/api/runs/:runId`,
      },
      {
        source: "/api/runs",
        destination: `${apiUrl}/api/runs`,
      },
      {
        source: "/api/health/:path*",
        destination: `${apiUrl}/api/health/:path*`,
      },
      {
        source: "/api/exports/:path*",
        destination: `${apiUrl}/api/exports/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

