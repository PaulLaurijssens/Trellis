// Tijdcodes: seconden -> "mm:ss" / "h:mm:ss", en "spring naar moment"-links.
export function fmtTs(sec) {
  if (sec == null || !Number.isFinite(Number(sec))) return "";
  const s = Math.max(0, Math.floor(Number(sec)));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const mm = h ? String(m).padStart(2, "0") : String(m);
  return (h ? h + ":" : "") + mm + ":" + String(r).padStart(2, "0");
}

export const isYoutube = (url) => /(?:youtube\.com|youtu\.be)\//i.test(url || "");

// YouTube: url + t=<sec>s (nieuw tabblad). Andere bron met url: de url zelf.
export function momentLink(url, sec) {
  if (!url) return null;
  if (!isYoutube(url) || sec == null) return url;
  const s = Math.floor(Number(sec));
  try {
    const u = new URL(url);
    u.searchParams.set("t", s + "s");
    return u.toString();
  } catch {
    return url + (url.includes("?") ? "&" : "?") + "t=" + s + "s";
  }
}
