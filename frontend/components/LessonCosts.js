"use client";
// Cost card in Settings: lessons and tokens of the last 30 days, with a rough estimate in dollars.
// The provider's bill is the truth; this card only shows what Trellis measured.
import { useEffect, useState } from "react";
import { useT } from "../lib/i18n";
import { teach } from "../lib/teach";

const k = (n) => (n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "k" : String(n));

export default function LessonCosts() {
  const { t } = useT();
  const [data, setData] = useState(null);
  useEffect(() => { teach.usageSummary(30).then(setData).catch(() => setData(false)); }, []);
  if (!data) return null;
  return <div className="card costs-card">
    <h4>{t("costs.title")}</h4>
    <p className="costs-headline">{t("costs.headline", { lessons: data.lessons, usd: data.estimated_usd.toFixed(2) })}</p>
    <p className="hint">{t("costs.tokens", { total: k(data.total), cached: k(data.cached), model: data.model })}</p>
    <p className="hint">{t("costs.disclaimer", { inp: data.price_per_mtok.input, out: data.price_per_mtok.output })}</p>
  </div>;
}
