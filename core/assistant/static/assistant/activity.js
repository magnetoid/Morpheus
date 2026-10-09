/* What Linda is doing while she works, built from the chat stream's events
   (core/assistant/runtime.py):

     step               one tool call, sent when it starts and again when it ends
     plan               her plan after each update (the todo tool's full list)
     tool_call_started  what a store tool was asked   } from the rows the MCP
     tool_call_finished what it answered              } edge records
     progress           a heartbeat every few seconds

   One block per turn: a status line saying what she is doing now, her plan as a
   checklist, and each step with its time. When the answer arrives the block
   folds into "Worked for 42s · 6 steps", which opens again on click. Shared by
   the Linda page and the floating widget. Text goes in with textContent only. */
(function () {
  'use strict';
  if (window.LindaActivity) return;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }
  function clock(seconds) {
    var s = Math.max(0, Math.round(seconds));
    if (s < 60) return s + 's';
    var rest = s % 60;
    return Math.floor(s / 60) + 'm ' + (rest < 10 ? '0' : '') + rest + 's';
  }
  function duration(ms) {
    if (ms == null || isNaN(ms)) return '';
    return ms < 1000 ? '<1s' : (ms < 10000 ? (ms / 1000).toFixed(1) : Math.round(ms / 1000)) + 's';
  }
  function pretty(value) {
    if (typeof value === 'string') return value;
    try { return JSON.stringify(value, null, 2); } catch (_) { return String(value); }
  }
  function humanise(name) {
    var words = String(name || '').replace(/[._]+/g, ' ').trim();
    return words ? words.charAt(0).toUpperCase() + words.slice(1) : 'A step';
  }
  var CHEVRON = '<svg class="lt-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M6 4l4 4-4 4"/></svg>';

  function start(log, options) {
    var opts = options || {};
    var startedAt = Date.now();
    var root = el('div', 'lt' + (opts.compact ? ' lt--compact' : ''));
    root.dataset.state = 'working';
    root.dataset.open = 'true';

    var head = el('button', 'lt-head');
    head.type = 'button';
    head.setAttribute('aria-expanded', 'true');
    var avatar = el('span', 'lt-avatar');
    var img = el('img');
    img.src = opts.avatar || '';
    img.alt = '';
    avatar.appendChild(img);
    var now = el('span', 'lt-now', 'Thinking…');
    now.setAttribute('role', 'status');
    var time = el('span', 'lt-time', '0s');
    time.setAttribute('aria-hidden', 'true');
    head.appendChild(avatar);
    head.appendChild(now);
    head.appendChild(time);
    head.insertAdjacentHTML('beforeend', CHEVRON);

    var body = el('div', 'lt-body');
    var plan = el('ol', 'lt-plan');
    plan.hidden = true;
    plan.setAttribute('aria-label', 'Plan');
    var steps = el('ol', 'lt-steps');
    steps.setAttribute('aria-label', 'Steps');
    body.appendChild(plan);
    body.appendChild(steps);
    root.appendChild(head);
    root.appendChild(body);
    log.appendChild(root);

    var rows = {};
    var argsByTool = {};
    var count = 0;
    var finished = false;
    var timer = setInterval(function () {
      time.textContent = clock((Date.now() - startedAt) / 1000);
    }, 1000);

    function scroll() { log.scrollTop = log.scrollHeight; }
    function say(text) { if (now.textContent !== text) now.textContent = text; }
    function running() { return steps.querySelectorAll('.lt-step[data-state="running"]').length; }

    function addRow(id) {
      var li = el('li', 'lt-step');
      var row = el('div', 'lt-step-row');
      row.appendChild(el('span', 'lt-mark'));
      row.appendChild(el('span', 'lt-label'));
      row.appendChild(el('span', 'lt-detail'));
      row.appendChild(el('span', 'lt-ms'));
      li.appendChild(row);
      steps.appendChild(li);
      rows[id] = li;
      count += 1;
      return li;
    }

    function onStep(ev) {
      var li = rows[ev.id] || addRow(ev.id);
      li.dataset.state = ev.state;
      if (ev.store_tool) li.dataset.storeTool = ev.store_tool;
      var label = ev.state === 'running' ? ev.label : (ev.done_label || ev.label);
      li.querySelector('.lt-label').textContent = label || humanise(ev.tool);
      li.querySelector('.lt-detail').textContent = ev.detail || '';
      li.querySelector('.lt-ms').textContent = ev.state === 'running' ? '' : duration(ev.ms);
      if (ev.state === 'running') {
        var doing = ev.label || humanise(ev.tool);
        say(ev.tool === 'web_search' && ev.detail ? doing + ' for “' + ev.detail + '”' : doing + '…');
      } else if (!running()) {
        say('Thinking…');
      }
      scroll();
    }

    function onPlan(ev) {
      var items = ev.items || [];
      plan.textContent = '';
      items.forEach(function (item) {
        var li = el('li', null, item.text);
        li.dataset.status = item.status || 'pending';
        plan.appendChild(li);
      });
      plan.hidden = !items.length;
      scroll();
    }

    // A store tool's question and answer, folded into the step that ran it. An
    // engine that reports no steps still gets one line per store tool.
    function onToolFinished(ev) {
      var li = null;
      var candidates = steps.querySelectorAll('.lt-step');
      for (var i = 0; i < candidates.length; i += 1) {
        var c = candidates[i];
        if (c.dataset.storeTool === ev.name && !c.dataset.hasData) { li = c; break; }
      }
      if (!li) {
        li = addRow('tool-' + count);
        li.dataset.storeTool = ev.name;
        li.dataset.state = ev.error ? 'error' : 'done';
        li.querySelector('.lt-label').textContent = humanise(ev.name);
      }
      li.dataset.hasData = '1';
      if (ev.error) li.dataset.state = 'error';
      var more = el('button', 'lt-more', 'details');
      more.type = 'button';
      more.setAttribute('aria-expanded', 'false');
      var data = el('pre', 'lt-data');
      data.hidden = true;
      var asked = argsByTool[ev.name];
      delete argsByTool[ev.name];
      data.textContent = (asked && Object.keys(asked).length ? 'Asked: ' + pretty(asked) + '\n\n' : '')
        + (ev.error ? 'Error: ' + ev.error : 'Answer: ' + pretty(ev.output));
      more.addEventListener('click', function (e) {
        e.stopPropagation();
        data.hidden = !data.hidden;
        more.setAttribute('aria-expanded', String(!data.hidden));
      });
      li.querySelector('.lt-step-row').appendChild(more);
      li.appendChild(data);
    }

    function setOpen(open) {
      root.dataset.open = open ? 'true' : 'false';
      head.setAttribute('aria-expanded', String(open));
    }
    head.addEventListener('click', function () {
      if (finished && (count || !plan.hidden)) setOpen(root.dataset.open !== 'true');
    });

    function finish(outcome) {
      if (finished) return;
      finished = true;
      clearInterval(timer);
      var seconds = (Date.now() - startedAt) / 1000;
      steps.querySelectorAll('.lt-step[data-state="running"]').forEach(function (li) {
        li.dataset.state = outcome === 'error' ? 'error' : 'done';
      });
      root.dataset.state = outcome === 'error' ? 'error' : 'done';
      time.textContent = '';
      if (outcome === 'error') {
        say('Stopped after ' + clock(seconds));
      } else if (count) {
        say('Worked for ' + clock(seconds) + ' · ' + count + (count === 1 ? ' step' : ' steps'));
      } else {
        say('Answered in ' + clock(seconds));
      }
      setOpen(false);
      if (!count && plan.hidden) head.querySelector('.lt-chevron').style.display = 'none';
    }

    return {
      element: root,
      finish: finish,
      event: function (ev) {
        if (!ev || finished) return;
        if (ev.type === 'step') onStep(ev);
        else if (ev.type === 'plan') onPlan(ev);
        else if (ev.type === 'tool_call_started') argsByTool[ev.name] = ev.arguments || {};
        else if (ev.type === 'tool_call_finished') onToolFinished(ev);
      },
    };
  }

  window.LindaActivity = { start: start };
})();
