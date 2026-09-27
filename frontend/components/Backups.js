"use client";
// Owner's backup card in Settings: make one now, see the list, verify one. Restore is a script
// (scripts/restore.sh), because it replaces the whole database; the card says so.
import { useEffect, useState } from "react";
import { useT } from "../lib/i18n";
import { api } from "../lib/api";

const mb = (n) => (n ? (n / 1e6).toFixed(1) + " MB" : "–");

export default function Backups() {
  const { t } = useT();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const load = () => api.backups().then(setData).catch(() => setData({ available: false, backups: [] }));
  useEffect(() => { load(); }, []);
  if (!data) return null;
  const run = async (fn, done) => { setBusy(true); setNote(""); try { const r = await fn(); setNote(done(r)); await load(); } catch (e) { setNote(e.message || "error"); } finally { setBusy(false); } };
  return <div className="card backups-card">
    <h4>{t("backup.title")}</h4>
    <p className="hint">{data.available ? t("backup.hint", { hour: data.nightly_hour_utc, keep: data.keep }) : t("backup.unavailable")}</p>
    <button className="btn" disabled={busy || !data.available} onClick={() => run(api.createBackup, (r) => t("backup.made", { nodes: r.nodes, seconds: r.seconds }))}>{busy ? <span className="spinner" /> : t("backup.makeNow")}</button>
    {note && <p className="hint" role="status">{note}</p>}
    {data.backups.length > 0 && <ul className="backup-list">{data.backups.slice(0, 8).map((b) => <li key={b.stamp}>
      <code>{b.stamp}</code><span>{mb(b.graph_bytes)} · {mb(b.artifacts_bytes)}</span>
      <button className="textlink" disabled={busy} onClick={() => run(() => api.verifyBackup(b.stamp), (r) => r.ok ? t("backup.verified", { n: r.lesson_versions }) : t("backup.broken"))}>{t("backup.verify")}</button>
    </li>)}</ul>}
    <p className="hint">{t("backup.restoreHint")} <code>scripts/restore.sh &lt;stamp&gt;</code></p>
  </div>;
}
