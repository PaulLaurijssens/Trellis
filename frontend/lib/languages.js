// The one list of UI languages. Trellis ships in English only.
// Adding a language = one entry here + a dictionary file next to en.js (same keys; a missing key
// falls back to English) + the same code in backend/app/languages.py. The README section
// "Add your language" has a prompt that lets an AI coding agent do all three.
import en from "./en";

export const LANGUAGES = [
  { code: "en", native: "English", dict: en },
];
export const DEFAULT_LANGUAGE = "en";
