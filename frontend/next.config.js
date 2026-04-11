/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  compress: true,
  poweredByHeader: false,
  async rewrites() {
    const backend = process.env.INTERNAL_API_URL || "http://backend:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        // Cache the background and icons for a year — they're fingerprinted
        // by filename in practice (we'd rename if we replaced them).
        source: "/(bg.webp|bg.jpg|favicon.svg|icon-192.svg|icon-512.svg)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        // Next.js already hashes files under _next/static, so we can
        // cache them aggressively too.
        source: "/_next/static/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
