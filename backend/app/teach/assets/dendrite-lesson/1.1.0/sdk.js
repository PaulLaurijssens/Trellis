/* Dendrite lesson SDK 1.1.0 — the only way a lesson talks to Dendrite.
 *
 * A lesson runs in a sandboxed frame without network, storage or navigation. This SDK:
 *   - builds the lesson shell (one step at a time, progress, back/next, ask-the-mentor reminder),
 *   - does the handshake with the host and then talks over a private MessagePort,
 *   - saves/restores activity state, submits answers and shows the SERVER's feedback,
 *   - offers helpers: quiz, predict, slider, plane (2D SVG), el.
 * Nothing the lesson reports is trusted by Dendrite: answers are re-checked on the server. */
(function () {
  'use strict';
  var VERSION = '1.1.0';
  var lang = (document.documentElement.lang || 'en').slice(0, 2) === 'nl' ? 'nl' : 'en';
  var T = {
    en: { next: 'Next', back: 'Back', done: 'Finish', check: 'Check', hint: 'Hint', reset: 'Reset', ask: 'Ask your mentor',
          askNote: 'Anything unclear? Ask your mentor: the question goes with what you see here.', step: 'Step', of: 'of',
          commit: 'Lock in my prediction', reveal: 'Show what happens', pending: 'Saved. Your mentor checks this answer.',
          good: 'Correct.', retry: 'Not yet. Look again and try once more.', offline: 'Not connected: this answer is not checked yet.',
          choose: 'Choose an answer first.', sources: 'Sources', value: 'value' },
    nl: { next: 'Verder', back: 'Terug', done: 'Afronden', check: 'Controleer', hint: 'Hint', reset: 'Opnieuw', ask: 'Vraag je mentor',
          askNote: 'Iets onduidelijk? Vraag het je mentor: je vraag gaat mee met wat je hier ziet.', step: 'Stap', of: 'van',
          commit: 'Leg mijn voorspelling vast', reveal: 'Laat zien wat er gebeurt', pending: 'Opgeslagen. Je mentor beoordeelt dit antwoord.',
          good: 'Klopt.', retry: 'Nog niet. Kijk nog eens en probeer het opnieuw.', offline: 'Geen verbinding: dit antwoord is nog niet gecontroleerd.',
          choose: 'Kies eerst een antwoord.', sources: 'Bronnen', value: 'waarde' }
  }[lang];

  var port = null, hostReady = false, started = false, seq = 0, opCounter = 0;
  var activities = {}, order = [], steps = [], current = 0, pending = {}, savedState = {}, timers = {};
  var nav, backBtn, nextBtn, progress, hintBtn;

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'class') node.className = attrs[k];
      else if (k === 'text') node.textContent = attrs[k];
      else if (k.slice(0, 2) === 'on' && typeof attrs[k] === 'function') node.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) node.setAttribute(k, attrs[k] === true ? '' : attrs[k]);
    });
    [].concat(children || []).forEach(function (c) { if (c !== null && c !== undefined) node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return node;
  }
  function svg(tag, attrs) {
    var node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    return node;
  }

  function send(type, activityId, payload) {
    var msg = { v: 1, type: type, seq: ++seq, activity_id: activityId || null, payload: payload || {} };
    if (port) port.postMessage(msg);
    return msg;
  }

  function plain(value, depth) {            // only numbers, short strings, booleans, small lists/objects leave the frame
    depth = depth || 0;
    if (value === null || typeof value === 'number' || typeof value === 'boolean') return value;
    if (typeof value === 'string') return value.slice(0, 2000);
    if (depth > 2 || typeof value !== 'object') return null;
    if (Array.isArray(value)) return value.slice(0, 64).map(function (v) { return plain(v, depth + 1); });
    var out = {}; Object.keys(value).slice(0, 32).forEach(function (k) { out[k] = plain(value[k], depth + 1); }); return out;
  }

  function Activity(id, handlers) {
    this.id = id; this.handlers = handlers || {}; this.hints = 0;
    this.section = document.querySelector('[data-dl-activity="' + id + '"]');
    if (!this.section) throw new Error('DendriteLesson.activity: no <section data-dl-activity="' + id + '">');
    this.feedbackEl = this.section.querySelector('.dl-feedback') || this.section.appendChild(el('p', { class: 'dl-feedback', 'aria-live': 'polite' }));
  }
  Activity.prototype.state = function () { try { return plain(this.handlers.getState ? this.handlers.getState() : {}); } catch (e) { return {}; } };
  Activity.prototype.changed = function () {
    var self = this; clearTimeout(timers[this.id]);
    timers[this.id] = setTimeout(function () { send('activity.state_changed', self.id, { params: self.state(), step: current }); }, 500);
  };
  Activity.prototype.submit = function (response) {
    var self = this, opId = 'op' + Date.now().toString(36) + (++opCounter);
    this.showFeedback({ outcome: 'checking' });
    return new Promise(function (resolve) {
      var finish = function (fb) { delete pending[opId]; self.showFeedback(fb); if (self.handlers.onFeedback) self.handlers.onFeedback(fb); resolve(fb); };
      if (!port) return finish({ outcome: 'offline', message: T.offline });
      pending[opId] = finish;
      send('activity.answer_submitted', self.id, { response: plain(response), params: self.state(), hint_usage: { hints: self.hints }, client_op_id: opId });
      setTimeout(function () { if (pending[opId]) finish({ outcome: 'offline', message: T.offline }); }, 20000);
    });
  };
  Activity.prototype.hint = function () { this.hints += 1; send('activity.hint_requested', this.id, { level: this.hints }); this.showLocalHint(); };
  Activity.prototype.showLocalHint = function () {
    var list = this.section.querySelectorAll('[data-dl-hint]'); var i = Math.min(this.hints, list.length) - 1;
    if (i >= 0) list[i].hidden = false;
    if (this.handlers.onHint) this.handlers.onHint(this.hints);
  };
  Activity.prototype.showFeedback = function (fb) {
    var text = fb.message || ({ demonstrated: T.good, needs_practice: T.retry, pending: T.pending, offline: T.offline, checking: '…' }[fb.outcome] || '');
    this.feedbackEl.textContent = text; this.feedbackEl.setAttribute('data-outcome', fb.outcome || '');
  };
  Activity.prototype.setFeedback = function (text, outcome) { this.showFeedback({ outcome: outcome || 'info', message: text }); };

  function activity(id, handlers) { activities[id] = new Activity(id, handlers); if (savedState[id] && handlers && handlers.setState) { try { handlers.setState(savedState[id]); } catch (e) {} } return activities[id]; }

  /* ---- shell: one step at a time ---- */
  function show(index, silent) {
    current = Math.max(0, Math.min(steps.length - 1, index));
    steps.forEach(function (s, i) { s.hidden = i !== current; });
    var id = steps[current].getAttribute('data-dl-activity');
    backBtn.disabled = current === 0;
    nextBtn.textContent = current === steps.length - 1 ? T.done : T.next;
    progress.textContent = T.step + ' ' + (current + 1) + ' ' + T.of + ' ' + steps.length;
    hintBtn.hidden = !(id && steps[current].querySelector('[data-dl-hint]'));
    if (!silent) { window.scrollTo(0, 0); send('activity.state_changed', id, { params: id && activities[id] ? activities[id].state() : {}, step: current }); }
  }
  function currentActivityId() { return steps[current] ? steps[current].getAttribute('data-dl-activity') : null; }

  function buildShell() {
    var main = document.querySelector('main.dl-lesson') || document.body;
    steps = [].slice.call(main.querySelectorAll(':scope > section'));
    order = steps.map(function (s) { return s.getAttribute('data-dl-activity'); }).filter(Boolean);
    steps.forEach(function (s) { var title = s.getAttribute('data-dl-title'); if (title && !s.querySelector('h2')) s.insertBefore(el('h2', { text: title }), s.firstChild); });
    progress = el('span', { class: 'dl-progress' });
    backBtn = el('button', { type: 'button', class: 'dl-btn dl-btn-ghost', text: T.back, onclick: function () { show(current - 1); } });
    nextBtn = el('button', { type: 'button', class: 'dl-btn dl-btn-primary', text: T.next, onclick: function () {
      if (current === steps.length - 1) send('activity.state_changed', null, { params: {}, step: current, completed: true }); else show(current + 1); } });
    hintBtn = el('button', { type: 'button', class: 'dl-btn dl-btn-ghost', text: T.hint, hidden: true, onclick: function () { var a = activities[currentActivityId()]; if (a) a.hint(); } });
    var ask = document.querySelector('[data-dl-ask-mentor]') || el('button', { type: 'button', class: 'dl-btn dl-ask', 'data-dl-ask-mentor': true, text: T.ask });
    ask.addEventListener('click', function () { var id = currentActivityId(); send('mentor.question_requested', id, { params: id && activities[id] ? activities[id].state() : {}, step: current }); });
    nav = el('nav', { class: 'dl-nav', 'aria-label': 'lesson' }, [backBtn, progress, hintBtn, nextBtn]);
    main.appendChild(nav);
    if (!ask.parentNode) main.appendChild(el('aside', { class: 'dl-askbar' }, [el('p', { class: 'dl-note', text: T.askNote }), ask]));
    document.addEventListener('click', function (event) {
      var link = event.target.closest && event.target.closest('[data-dl-source],[data-dl-lesson],[data-dl-reference]');
      if (!link) return; event.preventDefault();
      if (link.hasAttribute('data-dl-source')) send('source.open_requested', currentActivityId(), { source_id: link.getAttribute('data-dl-source'), start_sec: Number(link.getAttribute('data-dl-start')) || null });
      else send('link.open_requested', currentActivityId(), { kind: link.hasAttribute('data-dl-lesson') ? 'lesson' : 'reference', id: link.getAttribute('data-dl-lesson') || link.getAttribute('data-dl-reference') });
    });
    show(0, true);
  }

  function onHostMessage(event) {
    var msg = event.data; if (!msg || msg.v !== 1) return;
    if (msg.type === 'host.feedback') { var done = pending[msg.client_op_id]; if (done) done(msg.payload || {}); }
    else if (msg.type === 'host.hint') { var a = activities[msg.activity_id]; if (a && msg.payload && msg.payload.text) a.setFeedback(msg.payload.text, 'hint'); }
    else if (msg.type === 'host.restore_state') restore(msg.payload || {});
  }
  function restore(init) {
    savedState = init.state || {};
    Object.keys(savedState).forEach(function (id) { var a = activities[id]; if (a && a.handlers.setState) { try { a.handlers.setState(savedState[id]); } catch (e) {} } });
    if (typeof init.step === 'number') show(init.step, true);
    else if (init.current_activity && order.indexOf(init.current_activity) >= 0) show(steps.findIndex(function (s) { return s.getAttribute('data-dl-activity') === init.current_activity; }), true);
    if (init.reduced_motion) document.documentElement.setAttribute('data-dl-reduced-motion', '');
  }

  function start() {
    if (started) return; started = true;
    buildShell();
    window.addEventListener('message', function (event) {
      if (hostReady || event.source !== window.parent) return;          // first init from our own parent only
      var msg = event.data; if (!msg || msg.v !== 1 || msg.type !== 'host.init' || !event.ports || !event.ports[0]) return;
      hostReady = true; port = event.ports[0]; port.onmessage = onHostMessage; restore(msg.payload || {});
    });
    if (window.parent && window.parent !== window) window.parent.postMessage({ v: 1, type: 'lesson.ready', seq: ++seq, payload: {}, sdk_version: VERSION, activities: order }, '*');
  }

  /* ---- helpers ---- */
  function mount(id) { var s = document.querySelector('[data-dl-activity="' + id + '"]'); return (s && s.querySelector('[data-dl-mount]')) || s; }

  function quiz(id, cfg) {                   // cfg: {question, options:[{id,label}], multiple}
    var chosen = [], root = mount(id), name = 'dl-' + id;
    var list = el('div', { class: 'dl-options', role: cfg.multiple ? 'group' : 'radiogroup' });
    cfg.options.forEach(function (o) {
      var input = el('input', { type: cfg.multiple ? 'checkbox' : 'radio', name: name, value: o.id, id: name + '-' + o.id });
      input.addEventListener('change', function () { chosen = [].slice.call(list.querySelectorAll('input:checked')).map(function (i) { return i.value; }); a.changed(); });
      list.appendChild(el('label', { class: 'dl-option', for: name + '-' + o.id }, [input, el('span', { text: o.label })]));
    });
    var btn = el('button', { type: 'button', class: 'dl-btn dl-btn-primary', text: T.check, onclick: function () {
      if (!chosen.length) return a.setFeedback(T.choose); a.submit(cfg.multiple ? chosen : chosen[0]); } });
    if (cfg.question) root.appendChild(el('p', { class: 'dl-question', text: cfg.question }));
    root.appendChild(list); root.appendChild(btn);
    var a = activity(id, { getState: function () { return { chosen: chosen }; },
      setState: function (s) { chosen = (s.chosen || []).slice(); list.querySelectorAll('input').forEach(function (i) { i.checked = chosen.indexOf(i.value) >= 0; }); },
      onFeedback: cfg.onFeedback });
    return a;
  }

  function predict(id, cfg) {                // cfg: {question, options:[{id,label}], reveal:'#selector' | function}
    var choice = null, committed = false, root = mount(id);
    var list = el('div', { class: 'dl-options', role: 'radiogroup' });
    cfg.options.forEach(function (o) {
      var input = el('input', { type: 'radio', name: 'dl-' + id, value: o.id, id: 'dl-' + id + '-' + o.id });
      input.addEventListener('change', function () { choice = o.id; a.changed(); });
      list.appendChild(el('label', { class: 'dl-option', for: 'dl-' + id + '-' + o.id }, [input, el('span', { text: o.label })]));
    });
    function reveal() { committed = true; btn.disabled = true; list.querySelectorAll('input').forEach(function (i) { i.disabled = true; });
      if (typeof cfg.reveal === 'function') cfg.reveal(choice); else if (cfg.reveal) { var t = document.querySelector(cfg.reveal); if (t) t.hidden = false; } }
    var btn = el('button', { type: 'button', class: 'dl-btn dl-btn-primary', text: T.commit, onclick: function () {
      if (!choice) return a.setFeedback(T.choose); a.submit(choice).then(reveal); } });
    if (cfg.question) root.appendChild(el('p', { class: 'dl-question', text: cfg.question }));
    root.appendChild(list); root.appendChild(btn);
    var a = activity(id, { getState: function () { return { choice: choice, committed: committed }; },
      setState: function (s) { choice = s.choice || null; list.querySelectorAll('input').forEach(function (i) { i.checked = i.value === choice; }); if (s.committed) reveal(); },
      onFeedback: cfg.onFeedback });
    return a;
  }

  function slider(container, cfg) {          // range + number box: never drag-only. cfg: {label,min,max,step,value,unit,onInput}
    if (!container || typeof container.appendChild !== 'function') fail('slider(container, cfg)', 'an element as first argument', container);
    cfg = cfg || {}; num(cfg.min, 'slider cfg.min'); num(cfg.max, 'slider cfg.max'); num(cfg.value, 'slider cfg.value');
    var id = 'dl-s' + Math.random().toString(36).slice(2, 8);
    var range = el('input', { type: 'range', id: id, min: cfg.min, max: cfg.max, step: cfg.step || 1, value: cfg.value, 'aria-label': cfg.label });
    var number = el('input', { type: 'number', class: 'dl-number', min: cfg.min, max: cfg.max, step: cfg.step || 1, value: cfg.value, 'aria-label': cfg.label + ' (' + T.value + ')' });
    function set(v, from) { v = Math.max(cfg.min, Math.min(cfg.max, Number(v))); if (isNaN(v)) return; if (from !== range) range.value = v; if (from !== number) number.value = v; if (cfg.onInput) cfg.onInput(v); }
    range.addEventListener('input', function () { set(range.value, range); });
    number.addEventListener('change', function () { set(number.value, number); });
    container.appendChild(el('div', { class: 'dl-slider' }, [el('label', { for: id, text: cfg.label }), range, number, cfg.unit ? el('span', { class: 'dl-unit', text: cfg.unit }) : null]));
    return { get value() { return Number(range.value); }, set: function (v) { set(v); } };
  }

  /* ---- plane: 2D plot in SVG, math coordinates. Every input is checked: a wrong shape throws a
     message that says what was expected, instead of drawing NaN. ---- */
  function fail(where, expected, got) { var shown; try { shown = JSON.stringify(got); } catch (e) { shown = String(got); } throw new Error('DendriteLesson.' + where + ': expected ' + expected + ', got ' + String(shown).slice(0, 120)); }
  function num(v, where) { if (typeof v !== 'number' || !isFinite(v)) fail(where, 'a finite number', v); return v; }
  function pair(v, where) { if (!Array.isArray(v) || v.length !== 2) fail(where, '[min, max] or [x, y] as two numbers', v); return [num(v[0], where), num(v[1], where)]; }
  function niceStep(span) { var raw = span / 8, pow = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), f = raw / pow; return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * pow; }

  function plane(container, cfg) {           // cfg: {range: 4} (square, -4..4) OR {x: [min,max], y: [min,max]}; + label, height, ticks
    cfg = cfg || {};
    if (!container || typeof container.appendChild !== 'function') fail('plane(container, cfg)', 'an element as first argument (document.getElementById(...), after DOMContentLoaded)', container);
    var xr, yr;
    if (cfg.x !== undefined || cfg.y !== undefined) { xr = pair(cfg.x !== undefined ? cfg.x : cfg.y, 'plane cfg.x'); yr = pair(cfg.y !== undefined ? cfg.y : cfg.x, 'plane cfg.y'); }
    else if (Array.isArray(cfg.range)) { xr = pair(cfg.range, 'plane cfg.range'); yr = xr.slice(); }
    else { var R = num(cfg.range === undefined ? 4 : cfg.range, 'plane cfg.range'); xr = [-R, R]; yr = [-R, R]; }
    if (!(xr[1] > xr[0]) || !(yr[1] > yr[0])) fail('plane', 'max greater than min for x and y', { x: xr, y: yr });
    var square = (xr[1] - xr[0]) === (yr[1] - yr[0]), W = 320, H = cfg.height ? num(cfg.height, 'plane cfg.height') : (square ? 320 : 220), pad = 6;
    var X = function (x) { return pad + (num(x, 'plane x coordinate') - xr[0]) / (xr[1] - xr[0]) * (W - 2 * pad); };
    var Y = function (y) { return H - pad - (num(y, 'plane y coordinate') - yr[0]) / (yr[1] - yr[0]) * (H - 2 * pad); };
    var root = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'dl-plane', role: 'img', 'aria-label': cfg.label || 'coordinate plane' });
    var grid = svg('g', { class: 'dl-plane-grid' }), layer = svg('g', {});
    var sx = niceStep(xr[1] - xr[0]), sy = niceStep(yr[1] - yr[0]), v, t;
    for (v = Math.ceil(xr[0] / sx) * sx; v <= xr[1] + 1e-9; v += sx) {
      grid.appendChild(svg('line', { x1: X(v), y1: pad, x2: X(v), y2: H - pad, class: Math.abs(v) < 1e-9 ? 'axis' : '' }));
      if (cfg.ticks !== false) { t = svg('text', { x: X(v), y: H - pad - 3, class: 'dl-tick', 'text-anchor': 'middle' }); t.textContent = String(Math.round(v * 1000) / 1000); grid.appendChild(t); }
    }
    for (v = Math.ceil(yr[0] / sy) * sy; v <= yr[1] + 1e-9; v += sy) {
      grid.appendChild(svg('line', { x1: pad, y1: Y(v), x2: W - pad, y2: Y(v), class: Math.abs(v) < 1e-9 ? 'axis' : '' }));
      if (cfg.ticks !== false && Math.abs(v) > 1e-9) { t = svg('text', { x: pad + 3, y: Y(v) - 3, class: 'dl-tick' }); t.textContent = String(Math.round(v * 1000) / 1000); grid.appendChild(t); }
    }
    root.appendChild(grid); root.appendChild(layer); container.appendChild(root);
    function pts(points, where) { if (!Array.isArray(points) || !points.length) fail(where, 'a list of points [[x, y], [x, y], ...]', points);
      return points.map(function (pt, i) { var q = pair(pt, where + ' point ' + i); return X(q[0]) + ',' + Y(q[1]); }).join(' '); }
    var api = { svg: root, layer: layer, x: X, y: Y, xRange: xr, yRange: yr,
      clear: function () { while (layer.firstChild) layer.removeChild(layer.firstChild); },
      vector: function (x, y, cls) { var l = svg('line', { x1: X(0), y1: Y(0), x2: X(x), y2: Y(y), class: 'dl-vector ' + (cls || '') }); var d = svg('circle', { cx: X(x), cy: Y(y), r: 4, class: 'dl-vector-tip ' + (cls || '') }); layer.appendChild(l); layer.appendChild(d); return l; },
      segment: function (a, b, cls) { a = pair(a, 'plane.segment a'); b = pair(b, 'plane.segment b'); var l = svg('line', { x1: X(a[0]), y1: Y(a[1]), x2: X(b[0]), y2: Y(b[1]), class: 'dl-segment ' + (cls || '') }); layer.appendChild(l); return l; },
      point: function (x, y, cls) { var d = svg('circle', { cx: X(x), cy: Y(y), r: 5, class: 'dl-point ' + (cls || '') }); layer.appendChild(d); return d; },
      polygon: function (points, cls) { var p = svg('polygon', { points: pts(points, 'plane.polygon'), class: 'dl-shape ' + (cls || '') }); layer.appendChild(p); return p; },
      // curve(fn) samples y = fn(x) over the x range; curve([[x,y],...]) draws the given points. Values outside the y range are clipped.
      curve: function (source, cls) {
        var points = source;
        if (typeof source === 'function') { points = []; for (var i = 0; i <= 160; i++) { var x = xr[0] + (xr[1] - xr[0]) * i / 160, y = source(x);
          if (typeof y !== 'number' || !isFinite(y)) fail('plane.curve(fn)', 'fn(x) to return a finite number for x = ' + x, y);
          points.push([x, Math.max(yr[0], Math.min(yr[1], y))]); } }
        var c = svg('polyline', { points: pts(points, 'plane.curve'), class: 'dl-curve ' + (cls || '') }); layer.appendChild(c); return c; },
      label: function (x, y, text, cls) { var t2 = svg('text', { x: X(x) + 6, y: Y(y) - 6, class: 'dl-plane-label ' + (cls || '') }); t2.textContent = String(text); layer.appendChild(t2); return t2; } };
    return api;
  }

  window.DendriteLesson = { version: VERSION, lang: lang, start: start, activity: activity, quiz: quiz, predict: predict, slider: slider,
    plane: plane, el: el, svg: svg, goTo: function (i) { show(i); }, t: T };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(start, 0); }); else setTimeout(start, 0);
})();
