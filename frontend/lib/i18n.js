"use client";
import { createContext, useContext } from "react";
import { LANGUAGES, DEFAULT_LANGUAGE } from "./languages";

export const DICTS = Object.fromEntries(LANGUAGES.map((l) => [l.code, l.dict]));
export const LANGS = LANGUAGES.map((l) => [l.code, l.native]);
export const LangContext = createContext({ lang: DEFAULT_LANGUAGE, setLang: () => {} });

// t("key", {n: 3}) -> text; a missing key falls back to English, then to the key itself.
export function useT() {
  const { lang, setLang } = useContext(LangContext);
  const t = (key, vars) => {
    let s = (DICTS[lang] && DICTS[lang][key]) ?? DICTS[DEFAULT_LANGUAGE][key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll("{" + k + "}", String(v));
    return s;
  };
  return { t, lang, setLang, dict: DICTS[lang] || DICTS[DEFAULT_LANGUAGE] };
}
