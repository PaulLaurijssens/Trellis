document.addEventListener('DOMContentLoaded', function () {
  var DL = window.DendriteLesson;
  DL.predict('predict-1', { question: 'The matrix has columns (2,0) and (0,1). What happens to the unit square?',
    options: [{ id: 'a', label: 'It becomes twice as tall' }, { id: 'b', label: 'It becomes twice as wide' }, { id: 'c', label: 'It turns a quarter turn' }] });
  var m = { a: 2, b: 0, c: 0, d: 1 }, sliders = {};
  var plane = DL.plane(document.getElementById('plane'), { range: 4, label: 'unit square under the matrix' });
  function draw() {
    plane.clear(); plane.polygon([[0, 0], [1, 0], [1, 1], [0, 1]], 'ghost');
    plane.polygon([[0, 0], [m.a, m.c], [m.a + m.b, m.c + m.d], [m.b, m.d]]); plane.vector(m.a, m.c); plane.vector(m.b, m.d, 'b');
  }
  var act = DL.activity('explore-1', { getState: function () { return m; },
    setState: function (s) { ['a', 'b', 'c', 'd'].forEach(function (k) { if (typeof s[k] === 'number') { m[k] = s[k]; sliders[k].set(s[k]); } }); draw(); } });
  ['a', 'b', 'c', 'd'].forEach(function (k) {
    sliders[k] = DL.slider(document.getElementById('controls'), { label: k, min: -3, max: 3, step: 0.5, value: m[k], onInput: function (v) { m[k] = v; draw(); act.changed(); } });
  });
  draw();
});
