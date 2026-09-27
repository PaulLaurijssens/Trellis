# trellis-lesson 1.1.0 — the shared lesson components

Every lesson links these three files, in this order, and nothing from the network:

```html
<link rel="stylesheet" href="assets/trellis-lesson/1.1.0/fonts.css">   <!-- embedded fonts; do not read it, it is large -->
<link rel="stylesheet" href="assets/trellis-lesson/1.1.0/lesson.css">
<script src="assets/trellis-lesson/1.1.0/sdk.js"></script>
<script src="lesson.js"></script>                                          <!-- your code, a classic script -->
```

At publish time Trellis inlines everything into one HTML file. The lesson then runs in a sandboxed
frame: **no network, no storage, no navigation, no forms, no inline `onclick=`**. Use `addEventListener`.

## Page skeleton (required parts are marked)

```html
<!doctype html>
<html lang="en">                                         <!-- REQUIRED: en or nl, same as manifest.language -->
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lesson title</title> …links above… </head>
<body>
<main class="dl-lesson">
  <header class="dl-header">
    <p class="dl-eyebrow">Topic · 10 min</p>
    <h1>Lesson title</h1>
    <p data-dl-objective>After this lesson you can …</p>   <!-- REQUIRED: the single outcome -->
  </header>

  <section data-dl-title="The idea">                       <!-- a step: knowledge first, short -->
    <p>…<sup class="dl-cite"><a data-dl-source="SOURCE_ID" data-dl-start="120">1</a></sup></p>
    <p class="dl-general">A claim that no stored source supports is marked like this.</p>
  </section>

  <section data-dl-activity="predict-1" data-dl-title="Predict">   <!-- REQUIRED: one per manifest activity, same id -->
    <div data-dl-mount></div>                                       <!-- helpers render here -->
    <p data-dl-hint hidden>First hint.</p>                          <!-- optional, revealed one by one by the Hint button -->
  </section>

  <section data-dl-title="Recap">
    <ul class="dl-sources">
      <li><a data-dl-source="SOURCE_ID" data-dl-primary>Read or watch this first: …</a></li>   <!-- REQUIRED when the manifest has sources -->
      <li><a data-dl-reference="REFERENCE_ID">Cheat sheet: …</a> · <a data-dl-lesson="LESSON_ID">Earlier lesson: …</a></li>
    </ul>
  </section>
</main>
</body></html>
```

Each direct `<section>` child of `main.dl-lesson` is one **step**. The SDK shows one step at a time
(phone and desktop), adds Back / Next / Hint, the progress text and the "Ask your mentor" reminder.
Do not build your own navigation. Keep a lesson to 3–6 steps.

## SDK (`window.TrellisLesson`)

| Call | Use |
|---|---|
| `quiz(id, {question, options:[{id,label}], multiple?, onFeedback?})` | Choice question. Trellis checks the answer **on the server**: do not put the answer in the page. Manifest check: `{"kind":"choice","expected":"b"}` or `set_equals` for `multiple`. |
| `predict(id, {question, options, reveal})` | The learner commits to a prediction, then `reveal` (a CSS selector to un-hide, or a function) shows what happens. Retrieval before explanation. |
| `activity(id, {getState, setState, onFeedback, onHint})` | A custom activity (SVG, canvas, anything). Returns `{changed(), submit(response), hint(), setFeedback(text)}`. Call `changed()` when the learner changes something (debounced, saved, restored on resume through `setState`). `submit(response)` returns a Promise with the server's feedback `{outcome: demonstrated|needs_practice|pending, message}`. |
| `slider(container, {label,min,max,step,value,unit,onInput})` | Range **plus** number box, so nothing is drag-only. Returns `{value, set(v)}`. |
| `plane(container, cfg)` | 2D plot in SVG, math coordinates. `cfg`: `{range: 4}` (square, −4…4) **or** `{x: [min,max], y: [min,max]}` for a function plot; optional `label`, `height`, `ticks:false`. Returns `{clear(), curve(fnOrPoints,cls), point(x,y,cls), vector(x,y,cls), segment([x,y],[x,y],cls), polygon(points,cls), label(x,y,text), x(), y(), svg, layer}`. **Points are arrays `[x, y]` of finite numbers**, never objects. Classes: `b` (amber), `ghost` (dashed, "before"). Wrong input throws a message that names the argument. |
| `el(tag, attrs, children)`, `svg(tag, attrs)` | Small DOM helpers. `attrs.text`, `attrs.class`, `attrs.onclick`. |
| `lang`, `t` | `'en'`/`'nl'` and the shell strings. |

Function plot, redrawn from two sliders (the usual shape of a "manipulate" activity):

```js
var s = { mu: 0, sigma: 1 }, controls = document.getElementById('controls');
var plot = TrellisLesson.plane(document.getElementById('plot'), { x: [-5, 5], y: [0, 1], label: 'bell curve' });
function draw() { plot.clear();
  plot.curve(function (x) { return Math.exp(-Math.pow(x - s.mu, 2) / (2 * s.sigma * s.sigma)); });
  plot.segment([s.mu, 0], [s.mu, 1], 'ghost'); plot.label(s.mu, 0.9, 'μ'); }
var act = TrellisLesson.activity('explore-1', { getState: function () { return s; },
  setState: function (v) { if (typeof v.mu === 'number') s.mu = v.mu; if (typeof v.sigma === 'number') s.sigma = v.sigma; draw(); } });
TrellisLesson.slider(controls, { label: 'μ (centre)', min: -3, max: 3, step: 0.5, value: s.mu, onInput: function (v) { s.mu = v; draw(); act.changed(); } });
TrellisLesson.slider(controls, { label: 'σ (width)', min: 0.5, max: 3, step: 0.5, value: s.sigma, onInput: function (v) { s.sigma = v; draw(); act.changed(); } });
draw();
```

Run your code inside `document.addEventListener('DOMContentLoaded', …)`, keep divisors away from 0
(slider `min` above 0 for a width), and read a saved state defensively: `setState` may get `{}`.

Only numbers, short strings, booleans and small lists/objects of them may be in state, params and
responses. Declare every state field of an activity in the manifest (`state_fields`); undeclared
fields are dropped. Deterministic interaction (sliders, drawing) runs in the page with no model call.

Links: `data-dl-source="<source id>"` (+ optional `data-dl-start` seconds), `data-dl-lesson`,
`data-dl-reference`. Trellis opens them; never use `href="http…"`.

## CSS you can rely on

**Lessons are dark, like Trellis.** Never set a white or light background and never hard-code text
colours: the validator measures the contrast of every step and rejects unreadable text. Use the
tokens (`var(--card)`, `var(--figure)`, `var(--code-bg)`, `var(--text)`), and these classes:

`.dl-card`, `.dl-figure` (+ `figcaption`), `.dl-illustrative` (put it on a figure whose numbers are
made up: it adds the "illustrative values" badge), `.dl-grid2` (two columns on wide screens),
`.dl-matrix` (set `element.style.gridTemplateColumns` from JS) with `.dl-cell` children (`.hl` blue,
`.hl-b` amber highlight), `.dl-input` (44 px number/text input, e.g. an editable matrix cell),
`.dl-btn .dl-btn-primary .dl-btn-ghost`, `.dl-options .dl-option`, `.dl-question`, `.dl-feedback`,
`.dl-mono`, `table`. Tokens: `--learning` (blue), `--mentor` (amber), `--learned` (green),
`--danger`, `--text*`, `--line*`, `--font-mentor` (serif prose), `--font-ui`, `--font-mono`.
Touch targets are at least 44 px. Do not restyle `body`, fonts or the shell.

## manifest.json (write it next to index.html)

```json
{"title":"…","outcome":"After this lesson you can …","language":"en","duration_min":10,"illustrative_values":true,
 "assets":["trellis-lesson@1.1.0"],
 "sources":[{"source_id":"…","primary":true,"start_sec":120}],
 "activities":[
  {"id":"predict-1","type":"predict","title":"Predict","prompt":"What happens to the square?","concept_ids":["…"],
   "state_fields":["choice","committed"],"events":["activity.state_changed","activity.answer_submitted"],
   "check":{"kind":"choice","expected":"b"}},
  {"id":"explore-1","type":"manipulate","title":"Explore","state_fields":["a","b","c","d"],
   "events":["activity.state_changed"],"check":{"kind":"none"}},
  {"id":"explain-1","type":"explain","title":"In your words","state_fields":["text"],
   "events":["activity.answer_submitted"],"check":{"kind":"rubric","rubric":"Mentions that the columns are where the basis vectors land."}}]}
```

Check kinds: `choice`, `set_equals`, `ordering`, `numeric_close` (+`tolerance`), `matrix_close`
(+`tolerance`), `rubric` (the mentor assesses, with uncertainty), `none` (exploration; never evidence).
The `check` stays on the server and is never sent to the browser.
