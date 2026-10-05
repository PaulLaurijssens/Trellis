"use client";
// Cost card in Settings: lessons and tokens of the last 30 days, with a rough estimate in dollars.
// The provider's bill is the truth; this card only shows what Trellis measured.
// Optional limit per lesson: off by default. Only the owner (who pays the provider) can change it.
import { useEffect, useState } from "react";
import { useT } from "../lib/i18n";
import { teach } from "../lib/teach";
import { session } from "../lib/session";

const k = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "k" : String(n));
const LIMITS = [0, 0.5, 1, 2];

export default function LessonCosts({ canEdit }) {
  const { t } = useT();
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);
  useEffect(() => { teach.usageSummary(30).then(setData).catch(() => setData(false)); }, []);
  if (!data) return null;
  const limit = Number(data.cost_limit || 0);
  const label = (v) => (v ? "$" + v.toFixed(2) : t("costs.limitOff"));
  const choose = async (v) => {
    if (v === limit) return;
    setSaving(true); setErr(null);
    try { await session.saveSettings({ lesson_cost_limit: v }); setData({ ...data, cost_limit: v }); }
    catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  };
  const options = LIMITS.includes(limit) ? LIMITS : [...LIMITS, limit].sort((a, b) => a - b);
  return <div className="card costs-card">
    <h4>{t("costs.title")}</h4>
    <p className="costs-headline">{t("costs.headline", { lessons: data.lessons, usd: data.estimated_usd.toFixed(2) })}</p>
    <p className="hint">{t("costs.tokens", { total: k(data.total), cached: k(data.cached), model: data.model })}</p>
    <div className="costs-limit">
      <h5>{t("costs.limit")}</h5>
      {canEdit
        ? <div className="seg" role="group" aria-label={t("costs.limit")}>{options.map((v) => <button key={v} className={v === limit ? "on" : ""} aria-pressed={v === limit} disabled={saving} onClick={() => choose(v)}>{label(v)}</button>)}</div>
        : <p>{label(limit)}</p>}
      <p className="hint">{limit ? t("costs.limitOnHint", { usd: limit.toFixed(2) }) : t("costs.limitOffHint")}</p>
      {err && <p className="hint error" role="alert">{err}</p>}
    </div>
    <p className="hint">{t("costs.disclaimer", { inp: data.price_per_mtok.input, out: data.price_per_mtok.output })}</p>
  </div>;
}
