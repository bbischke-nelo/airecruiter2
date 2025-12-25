/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  basePath: '/recruiter2',
  assetPrefix: '/recruiter2',
  async rewrites() {
    // In production with Docker, use the container name
    const apiUrl = process.env.API_URL || (process.env.NODE_ENV === 'production' ? 'http://airecruiter2-api:8000' : 'http://localhost:8000');

    return {
      beforeFiles: [
        // Proxy API calls to FastAPI backend
        {
          source: '/api/:path*',
          destination: `${apiUrl}/api/:path*`,
        }
      ],
      afterFiles: [],
      fallback: []
    };
  }
};

module.exports = nextConfig;
