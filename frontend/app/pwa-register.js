"use client";

import { useEffect } from "react";

/* Registreert de service worker. Client component, want dit hoort bij de browser.
 * Een service worker vereist een secure context: https, of localhost. Op de VPS komt
 * die https van Tailscale (tailscale serve), niet van een publieke reverse proxy. */
export default function PwaRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
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
