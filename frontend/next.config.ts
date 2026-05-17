import type { NextConfig } from "next";

const appMode = process.env.APP_MODE?.replace(/[^a-zA-Z0-9_-]/g, "") || "default";

const nextConfig: NextConfig = {
  distDir: `.next-${appMode}`,
};

export default nextConfig;
