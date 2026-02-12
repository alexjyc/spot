/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/recommend",
        destination: `${apiUrl}/recommend`,
      },
      {
        source: "/health",
        destination: `${apiUrl}/health`,
      },
      {
        source: "/runs",
        destination: `${apiUrl}/runs`,
      },
      {
        source: "/runs/:path*",
        destination: `${apiUrl}/runs/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
