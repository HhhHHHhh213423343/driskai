import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Keep generated build artifacts out of iCloud Drive synchronization.
  // Development and production use separate folders so `next build` cannot
  // invalidate chunks used by a running local preview.
  distDir: process.env.NODE_ENV === "development" ? ".next.dev.nosync" : ".next.nosync",
};

export default nextConfig;
