import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The sidebar's theme toggle sits bottom-left; keep the dev-only indicator out of its way.
  devIndicators: { position: "bottom-right" },
};

export default nextConfig;
