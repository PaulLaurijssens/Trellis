"use client";
import VoiceInput from "./VoiceInput";
import LocalizedText from "./LocalizedText";
import { useEffect, useRef, useState } from "react";
import { useT } from "../lib/i18n";
import ConversationSuggestions from "./ConversationSuggestions";
import TeachingIllustration from "./TeachingIllustration";

// De mentor gebruikt codeblokken; die moeten als code leesbaar zijn en niet
// als lopende tekst met backticks erin.
// Inline: `code` en **vet**; meer markdown doet de mentor niet.
function inline(text) {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g).map((seg, i) => {
    if (seg.startsWith("`")) return <code key={i}>{seg.slice(1, -1)}</code>;
    if (seg.startsWith("**")) return <b key={i}>{seg.slice(2, -2)}</b>;
    if (seg.startsWith("*") && seg.length > 2) return <em key={i}>{seg.slice(1, -1)}</em>;
    return seg;
  });
}

// A block of Markdown outside code fences: headings, bullet and numbered lists, simple tables, paragraphs.
function block(para, key) {
  const lines = para.split("\n");
  const h = para.match(/^(#{1,4})\s+(.*)$/);
  if (h && lines.length === 1) { const Tag = "h" + Math.min(4, h[1].length + 1); return <Tag key={key}>{inline(h[2])}</Tag>; }
  if (lines.every((l) => /^\s*[-*]\s+/.test(l))) return <ul key={key}>{lines.map((l, i) => <li key={i}>{inline(l.replace(/^\s*[-*]\s+/, ""))}</li>)}</ul>;
  if (lines.every((l) => /^\s*\d+[.)]\s+/.test(l))) return <ol key={key}>{lines.map((l, i) => <li key={i}>{inline(l.replace(/^\s*\d+[.)]\s+/, ""))}</li>)}</ol>;
  if (lines.length >= 2 && lines.every((l) => l.trim().startsWith("|"))) {
    const rows = lines.filter((l) => !/^\s*\|?\s*:?-+/.test(l)).map((l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
    return <table key={key}><thead><tr>{rows[0].map((c, i) => <th key={i}>{inline(c)}</th>)}</tr></thead><tbody>{rows.slice(1).map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>)}</tbody></table>;
  }
  // A heading glued to its paragraph without a blank line
  if (h) return <div key={key}>{block(lines[0], key + "h")}{block(lines.slice(1).join("\n"), key + "p")}</div>;
  return <p key={key}>{inline(para)}</p>;
}

export function render(content) {
  return String(content).split(/```/).map((part, i) =>
    i % 2
      ? <pre key={i}><code>{part.replace(/^[a-z]*\n/, "").trim()}</code></pre>
      : part.split(/\n\s*\n/).filter((x) => x.trim()).map((para, j) => block(para.trim(), i + "-" + j))
  );
}

export const CHIP_KEYS = ["chat.chip1", "chat.chip2", "chat.chip3", "chat.chip4", "chat.chip5"];

export default function Chat({
  concept, status, chat, busy, ending, onSend, onNew, onEnd, onExplain,
  suggestionBusy, onSuggestion,
  introduction, emptyState, examples=[], onSaveExample, exampleBusy,
  nextTopic, sessionMenu = true, draftKey = null,
}) {
  const { t } = useT();
  const [text, setText] = useState("");
  const [voiceBusy, setVoiceBusy] = useState(false);
  const endRef = useRef(null);
  const taRef = useRef(null);
  const messages = chat?.messages || [];

  const logRef = useRef(null);
  const nearBottom = useRef(true);
  // Na een nieuw antwoord begin je bovenaan DAT antwoord, niet onderaan het gesprek: anders
  // moet je eerst terugscrollen om het te lezen. Terwijl de mentor nadenkt blijft je eigen
  // vraag met de denk-indicator onderaan in beeld.
  useEffect(() => {
    const log = logRef.current;
    if (!log || !messages.length) return;
    const last = messages[messages.length - 1];
    if (busy || last.role !== "assistant") {
      if (nearBottom.current) log.scrollTo({ top: log.scrollHeight, behavior: "auto" });
      return;
    }
    const el = log.querySelector(`[data-seq="${last.seq}"]`);
    // 48px: onder de vervaging die .chat-log bovenaan heeft (mask-image, 44px).
    if (el) log.scrollTo({ top: log.scrollTop + el.getBoundingClientRect().top - log.getBoundingClientRect().top - 48, behavior: "auto" });
  }, [messages.length, busy]);
  useEffect(() => { nearBottom.current = true; setText(""); }, [concept]);
  // Unsent question draft survives an interruption (phone call, app switch). Only with draftKey,
  // i.e. when interactive lessons are on; without it this component behaves exactly as before.
  useEffect(() => { if (!draftKey) return; try { setText(localStorage.getItem(draftKey) || ""); } catch {} }, [draftKey]);
  useEffect(() => { if (!draftKey) return; try { text ? localStorage.setItem(draftKey, text) : localStorage.removeItem(draftKey); } catch {} }, [draftKey, text]);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
  }, [text]);

  const send = (value) => {
    const msg = (value ?? text).trim();
    if (!msg || busy || voiceBusy) return;
    setText("");
    nearBottom.current = true;
    onSend(msg);
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="chat">
      <div className="chat-log" ref={logRef} onScroll={(e) => { const el = e.currentTarget; nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120; }}>
        {chat?.memory_error&&<div className="memory-retry" role="alert"><p>{t("memory.failed")}</p><button className="btn" disabled={busy||ending} onClick={onEnd}>{ending?t("chat.ending"):t("memory.retry")}</button></div>}
        {introduction}
        {messages.length === 0 && !busy && (emptyState || <section className="lesson-start"><h2>{t("lesson.startTitle")}</h2><p>{t("lesson.startHint")}</p><button className="btn primary" onClick={onExplain}>{t("lesson.start")}</button></section>)}
        {messages.map((m) => (
          <div key={m.seq} data-seq={m.seq} className={"msg " + m.role}>{m.role === "assistant" ? <LocalizedText block render={render}>{m.content}</LocalizedText> : render(m.content)}{m.role === "assistant" && <><TeachingIllustration illustration={m.illustration} />{onSaveExample && (() => {
            // Feedback voor de mentor: bewaarde voorbeelden gaan mee in de prompt als je later
            // bij dit onderwerp terugkomt (journey.prompt_context, max. 3 per onderwerp).
            const saved = examples.some(e=>e.session_id===chat?.session_id && e.seq===m.seq);
            return <div className="helpful-row">
              <button className={"helpful-save" + (saved ? " saved" : "")} title={t("journey.helpedHint")} disabled={saved || exampleBusy || !chat?.session_id} onClick={()=>onSaveExample(m.seq)}>{saved ? t("journey.exampleSaved") : <><span aria-hidden="true">👍</span> {t("journey.helped")}</>}</button>
              {saved && <span className="helpful-hint">{t("journey.helpedHint")}</span>}
            </div>;
          })()}</>}</div>
        ))}
        {busy && (
          <div className="msg thinking" aria-live="polite">
            <span className="dots"><span /><span /><span /></span>
            <span className="hint">{t("chat.thinking")}</span>
          </div>
        )}
        <ConversationSuggestions suggestions={chat?.suggestions} busy={busy || ending || suggestionBusy} onAction={onSuggestion} />
        <div ref={endRef} />
      </div>

      <div className="chat-foot">
        <div className="chat-chips">
          {["chat.chip2", "learn.visualRequest"].map((k) => (
            <button key={k} className="chip" disabled={busy} onClick={() => send(t(k))}>{t(k)}</button>
          ))}
        </div>
        <div className="chat-input">
          <div className="pill">
            <textarea
              ref={taRef}
              rows={1}
              placeholder={t("learn.messagePlaceholder")}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKeyDown}
              disabled={busy}
              aria-label={t("chat.aria")}
            />
          </div>
          <VoiceInput key={concept+":"+(chat?.session_id||"")} disabled={busy||ending} onBusy={setVoiceBusy} onText={value=>{setText(previous=>previous ? previous.trimEnd()+" "+value : value);taRef.current?.focus();}} />
          <button className="send" onClick={() => send()} disabled={busy || voiceBusy || !text.trim()} aria-label={t("chat.send")}>
            {busy
              ? <span className="spinner" />
              : <svg width="13" height="13" viewBox="0 0 13 13"><path d="M1.5 6.5 H10 M7 3 L10.5 6.5 L7 10" stroke="#9CC8FF" strokeWidth="1.5" fill="none" /></svg>}
          </button>
        </div>
        {nextTopic && <button className="next-topic" disabled={busy || ending} onClick={nextTopic.go}>
          <span>{t("learn.nextTopicHint")}</span><b>{t("learn.nextTopic")}: {nextTopic.name} →</b>
        </button>}
        {sessionMenu && <details className="chat-session-menu"><summary>{t("learn.sessionMenu")}</summary><div className="chat-links">
          <button className="textlink" onClick={onEnd} disabled={busy || ending || !messages.length}
                  title={t("chat.endTitle")}>
            {ending ? t("chat.ending") : t("chat.end")}
          </button>
          <button className="textlink" onClick={onNew} disabled={busy || ending}
                  title={t("chat.newTitle")}>{t("chat.new")}</button>
        </div></details>}
      </div>
    </div>
  );
}
