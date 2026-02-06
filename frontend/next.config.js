/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        // Exclude events endpoint as it has a custom API route for SSE streaming
        source: "/api/runs/:runId",
        destination: "http://localhost:8000/api/runs/:runId",
      },
      {
        source: "/api/runs",
        destination: "http://localhost:8000/api/runs",
      },
      {
        source: "/api/health/:path*",
        destination: "http://localhost:8000/api/health/:path*",
      },
      {
        source: "/api/exports/:path*",
        destination: "http://localhost:8000/api/exports/:path*",
      },
    ];
  },
};

module.exports = nextConfig;

