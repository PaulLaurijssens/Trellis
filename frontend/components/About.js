"use client";
// Version line and a "Report a problem" link that opens a prefilled GitHub issue (no keys, ever).
import { useEffect, useState } from "react";
import { useT } from "../lib/i18n";
import { session } from "../lib/session";
import { reportUrl } from "../lib/providerErrors.mjs";

export default function About() {
  const { t } = useT();
  const [health, setHealth] = useState(null);
  const [settings, setSettings] = useState(null);
  useEffect(() => {
    session.health().then(setHealth).catch(() => setHealth({}));
    session.settings().then(setSettings).catch(() => {});
  }, []);
  if (!health) return null;
  const version = health.version || "dev";
  const commit = health.commit ? String(health.commit).slice(0, 7) : "";
  const href = reportUrl({ version, commit, ua: typeof navigator !== "undefined" ? navigator.userAgent : "",
    provider: settings?.provider, model: settings?.models?.mentor });
  return <div className="card about-card">
    <h4>{t("about.title")}</h4>
    <p>{t("about.version", { version })}{commit && <> <code>({commit})</code></>}</p>
    <p className="row"><a className="btn ghost" href={href} target="_blank" rel="noopener noreferrer">{t("about.report")} ↗</a></p>
    <p className="hint">{t("about.reportHint")}</p>
  </div>;
}
