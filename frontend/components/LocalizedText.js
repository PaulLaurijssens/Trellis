"use client";
import { useEffect, useState } from "react";
import { useT } from "../lib/i18n";
const cache = new Map();
const pending = new Map();
let timer;
const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
function flush() {
  const entries = [...pending.values()]; pending.clear();
  for (const language of ["en", "nl"]) {
    const remaining = entries.filter(e => e.language === language);
    while (remaining.length) {
      const batch = []; let size = 0;
      while (remaining.length && batch.length < 30 && size + remaining[0].text.length <= 24000) {
        const e = remaining.shift(); batch.push(e); size += e.text.length;
      }
      if (!batch.length) { remaining.shift().reject(new Error("Text too long")); continue; }
      fetch(base + "/translations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ language, texts: batch.map(e => e.text) }) })
        .then(async r => { if (!r.ok) throw new Error("Translation unavailable"); return r.json(); })
        .then(data => { if (!Array.isArray(data.texts) || data.texts.length !== batch.length) throw new Error("Invalid translation"); batch.forEach((e, i) => { cache.set(e.key, data.texts[i]); e.resolve(data.texts[i]); }); })
        .catch(error => batch.forEach(e => { cache.delete(e.key); e.reject(error); }));
    }
  }
}
function request(text, language) {
  const key = JSON.stringify([language, text]);
  if (cache.has(key)) return Promise.resolve(cache.get(key));
  const promise = new Promise((resolve, reject) => pending.set(key, { key, text, language, resolve, reject }));
  cache.set(key, promise); clearTimeout(timer); timer = setTimeout(flush, 40); return promise;
}
export default function LocalizedText({ children, render = x => x, block = false }) {
  const text = String(children || ""); const { lang } = useT();
  const [state, setState] = useState(null); const [retry, setRetry] = useState(0); const [original, setOriginal] = useState(false);
  useEffect(() => {
    let alive = true; setState(null); setOriginal(false);
    if (text.trim()) request(text, lang).then(value => { if (alive) setState({ text, lang, value }); }, () => { if (alive) setState({ text, lang, error: true }); });
    return () => { alive = false; };
  }, [text, lang, retry]);
  if (!text) return null;
  const current = state?.text === text && state?.lang === lang ? state : null;
  const Tag = block ? "div" : "span";
  return <><Tag>{render(original || !current?.value ? text : current.value)}</Tag>{current?.error ? <button className="textlink translation-note" onClick={() => setRetry(x => x + 1)}>{lang === "en" ? "Translation unavailable · Retry" : "Vertaling niet beschikbaar · Opnieuw"}</button> : current?.value !== text && current?.value ? <button className="textlink translation-note" onClick={() => setOriginal(x => !x)}>{original ? (lang === "en" ? "Show translation" : "Toon vertaling") : (lang === "en" ? "Translated · Original" : "Vertaald · Origineel")}</button> : null}</>;
}
