// Errors from the API, in the language on screen. A provider error comes as {code, params, message}:
// the code is translated here and kept on the error (err.code, err.params) for components that need it.
import { translate } from "./i18n";
import { errorText } from "./providerErrors.mjs";

export function networkError(base) {
  const err = new Error(translate("error.network", { base }));
  err.network = true;
  return err;
}

export function httpError(status, data) {
  const detail = data && data.detail;
  let message = translate("error.http", { status }), info = null, code = null, params = null;
  if (typeof detail === "string") message = detail;
  else if (Array.isArray(detail)) message = detail.map((d) => d && d.msg).filter(Boolean).join("; ") || message;   // FastAPI validation
  else if (detail && typeof detail === "object") {
    info = detail;                     // e.g. {message, paste, title} from /ingest/url
    if (detail.code) { code = detail.code; params = detail.params || {}; message = errorText(translate, code, params, { fallback: detail.message }); }
    else if (detail.message) message = detail.message;
    else message = JSON.stringify(detail);
  }
  const err = new Error(message);
  err.status = status;
  err.info = info;
  err.code = code;
  err.params = params;
  return err;
}
