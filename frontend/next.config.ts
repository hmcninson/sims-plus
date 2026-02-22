import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Output standalone for Docker deployment
  output: "standalone",

  // Server Actions configuration
  experimental: {
    serverActions: {
      bodySizeLimit: "2mb",
    },
  },

  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**.simsplus.io",
      },
      {
        protocol: "https",
        hostname: "**.amazonaws.com",
      },
      {
        // MinIO local development
        protocol: "http",
        hostname: "minio",
        port: "9000",
      },
      {
        // MinIO via localhost
        protocol: "http",
        hostname: "localhost",
        port: "9000",
      },
    ],
  },

  // Security headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains",
          },
          {
            key: "Permissions-Policy",
            value:
              "geolocation=(), microphone=(), camera=(), payment=(self)",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://storage.googleapis.com",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' https://*.simsplus.io https://*.amazonaws.com data: blob:",
              "font-src 'self' data:",
              "connect-src 'self' http://localhost:8000 https://*.simsplus.io",
              "worker-src 'self'",
              "manifest-src 'self'",
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
