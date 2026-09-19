"use client";

import { useEffect } from "react";

/* Registreert de service worker. Client component, want dit hoort bij de browser.
 * Een service worker vereist een secure context: https, of localhost. Op de VPS komt
 * die https van Tailscale (tailscale serve), niet van een publieke reverse proxy. */
export default function PwaRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    // Alleen in productie. In `next dev` hebben /_next/static-bestanden geen hash in de naam,
    // en de cache-first regel van sw.js serveerde dan oude JS op nieuwe HTML (hydratiefout).
    if (process.env.NODE_ENV !== "production") {
      navigator.serviceWorker.getRegistrations().then((regs) => regs.forEach((r) => r.unregister())).catch(() => {});
      return;
    }
    const register = () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
        /* stil: een mislukte registratie mag de app nooit breken */
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
