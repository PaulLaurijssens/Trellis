/** @type {import('next').NextConfig} */
const config = { reactStrictMode: false };

// DEV ONLY. Production is same-origin through nginx (/api -> API) and never sets DEV_API_PROXY, so
// this block does not exist there. Locally it gives the same shape: the lesson frame and the API share
// the page's host, which is what the frame's CSP (frame-ancestors 'self') expects.
// Run: NEXT_PUBLIC_API_URL=/api DEV_API_PROXY=http://localhost:8000 npm run dev
if (process.env.DEV_API_PROXY) {
  config.rewrites = async () => [{ source: "/api/:path*", destination: process.env.DEV_API_PROXY + "/:path*" }];
  config.experimental = { proxyTimeout: 300000 };      // a mentor answer is an LLM call; the default is 30 s
}
module.exports = config;
