// Timestamps: seconds -> "mm:ss" / "h:mm:ss", and "jump to moment" links.
export function fmtTs(sec) {
  if (sec == null || !Number.isFinite(Number(sec))) return "";
  const s = Math.max(0, Math.floor(Number(sec)));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const mm = h ? String(m).padStart(2, "0") : String(m);
  return (h ? h + ":" : "") + mm + ":" + String(r).padStart(2, "0");
}

export const isYoutube = (url) => /(?:youtube\.com|youtu\.be)\//i.test(url || "");

// Only web links are ever made clickable: a source URL can come from an imported file, and a
// javascript: or data: link must not run.
export function safeUrl(url) {
  try { return ["http:", "https:"].includes(new URL(String(url)).protocol) ? String(url) : null; } catch { return null; }
}

// YouTube: url + t=<sec>s (new tab). Another source with a url: the url itself.
export function momentLink(url, sec) {
  url = safeUrl(url);
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
