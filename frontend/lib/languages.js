// The one list of UI languages. Adding a language = one entry here + a dictionary file next to
// en.js (same keys; missing keys fall back to English). The backend keeps the same list in
// backend/app/languages.py.
import en from "./en";
import nl from "./nl";

export const LANGUAGES = [
  { code: "en", native: "English", dict: en },
  { code: "nl", native: "Nederlands", dict: nl },
];
export const DEFAULT_LANGUAGE = "en";
