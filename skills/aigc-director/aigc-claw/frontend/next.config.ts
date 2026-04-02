import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/code/:path*',
        destination: 'http://127.0.0.1:8000/code/:path*',
      },
      {
        source: '/api/sessions',
        destination: 'http://127.0.0.1:8000/api/sessions',
      },
      {
        source: '/api/sessions/:path*',
        destination: 'http://127.0.0.1:8000/api/sessions/:path*',
      },
      // 工作流 API
      {
        source: '/api/project/:path*',
        destination: 'http://127.0.0.1:8000/api/project/:path*',
      },
      {
        source: '/api/stages',
        destination: 'http://127.0.0.1:8000/api/stages',
      },
      // 临时工作台 API
      {
        source: '/api/sandbox/:path*',
        destination: 'http://127.0.0.1:8000/api/sandbox/:path*',
      },
    ];
  },
};

export default nextConfig;
