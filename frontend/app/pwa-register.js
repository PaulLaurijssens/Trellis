"use client";

import { useEffect } from "react";

/* Registers the service worker. A client component, because this belongs to the browser.
 * A service worker needs a secure context: https, or localhost. On a server, that https
 * can come from Tailscale (tailscale serve) instead of a public reverse proxy. */
export default function PwaRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    // Production only. In `next dev`, /_next/static files have no hash in their name, and the
    // cache-first rule of sw.js then served old JS with new HTML (a hydration error).
    if (process.env.NODE_ENV !== "production") {
      navigator.serviceWorker.getRegistrations().then((regs) => regs.forEach((r) => r.unregister())).catch(() => {});
      return;
    }
    const register = () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
        /* silent: a failed registration must never break the app */
      });
    };
    if (document.readyState === "complete") register();
    else {
      window.addEventListener("load", register);
      return () => window.removeEventListener("load", register);
    }
  }, []);
  return null;
}
