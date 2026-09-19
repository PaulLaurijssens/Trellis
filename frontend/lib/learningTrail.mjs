// A tab's navigation path is separate from the persisted conversation history.
export function visitTrail(trail, name) {
  const clean = (trail || []).filter((item) => typeof item === "string" && item.trim());
  const index = clean.findIndex((item) => item.toLowerCase() === name.toLowerCase());
  return index >= 0 ? clean.slice(0, index + 1) : [...clean, name].slice(-24);
}

export function readTrail(raw) {
  try {
    const value = JSON.parse(raw);
    if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item.trim())) return [];
    return value.reduce(visitTrail, []);
  } catch {
    return [];
  }
}
