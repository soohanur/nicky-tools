/** @type {import('next').NextConfig} */

// Static export: `next build` writes frontend/out, which nginx serves next to
// the FastAPI backend (see deploy.sh). No Node process at runtime, so auth is
// client-side (JWT in localStorage, see src/lib/auth.js) and every page is a
// client component that talks to the API through src/lib/api-client.js.
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  output: "export",
  // /login -> out/login/index.html, so nginx `try_files $uri $uri/` resolves it.
  trailingSlash: true,
  images: { unoptimized: true },
  agentRules: false,
};

export default nextConfig;
