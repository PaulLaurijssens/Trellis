"use client";
import { createContext, useContext } from "react";
import { LANGUAGES, DEFAULT_LANGUAGE } from "./languages";

export const DICTS = Object.fromEntries(LANGUAGES.map((l) => [l.code, l.dict]));
export const LANGS = LANGUAGES.map((l) => [l.code, l.native]);
export const LangContext = createContext({ lang: DEFAULT_LANGUAGE, setLang: () => {} });

// The language of the screen, for code outside components (api.js errors). LangProvider keeps it in sync.
let currentLang = DEFAULT_LANGUAGE;
export function setCurrentLang(lang) { if (DICTS[lang]) currentLang = lang; }

// translate("key", {n: 3}) -> text; a missing key falls back to English, then to the key itself.
export function translate(key, vars, lang = currentLang) {
  let s = (DICTS[lang] && DICTS[lang][key]) ?? DICTS[DEFAULT_LANGUAGE][key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll("{" + k + "}", String(v ?? ""));
  return s;
}

// Use instead of LangContext.Provider, so translate() follows the language on screen.
export function LangProvider({ value, children }) {
  setCurrentLang(value.lang);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useT() {
  const { lang, setLang } = useContext(LangContext);
  const t = (key, vars) => translate(key, vars, lang);
  return { t, lang, setLang, dict: DICTS[lang] || DICTS[DEFAULT_LANGUAGE] };
}
