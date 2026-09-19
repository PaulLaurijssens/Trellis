"use client";
import { createContext, useContext } from "react";
import nl from "./nl";
import en from "./en";

export const DICTS = { nl, en };
export const LANGS = [["nl", "Nederlands"], ["en", "English"]];
export const LangContext = createContext({ lang: "nl", setLang: () => {} });

// t("key", {n: 3}) -> tekst; ontbrekende sleutel valt terug op nl, dan op de sleutel.
export function useT() {
  const { lang, setLang } = useContext(LangContext);
  const t = (key, vars) => {
    let s = (DICTS[lang] && DICTS[lang][key]) ?? nl[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll("{" + k + "}", String(v));
    return s;
  };
  return { t, lang, setLang, dict: DICTS[lang] || nl };
}
