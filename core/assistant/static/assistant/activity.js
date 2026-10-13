/* What Linda is doing while she works, built from the chat stream's events
   (core/assistant/runtime.py):

     step               one tool call, sent when it starts and again when it ends
     plan               her plan after each update (the todo tool's full list)
     say                what she wrote before her next tool calls
     usage              tokens used so far this turn
     retry              a model call failed (HTTP status) and whether she tries again
     tool_call_started  what a store tool was asked   } from the rows the MCP
     tool_call_finished what it answered              } edge records
     progress           a heartbeat every few seconds

   One block per turn: a status line saying what she is doing now, her plan as a
   checklist, her words and each step with its time. When the answer arrives the
   block folds into "Worked for 42s · 6 steps · 12k tokens", which opens again on
   click. Two cards may follow the answer: her question with answer buttons
   (assistant.ask), and Approve / Decline for a change the store held for the
   merchant's yes, built from the refused call itself, never from her words.
   A click calls options.reply(text, {answer}); an answer is marked so it never
   approves a change (core/assistant/gates.py). Shared by the Linda page and the
   floating widget. Text goes in with textContent only. */
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
    var tokens = el('span', 'lt-tokens');
    tokens.hidden = true;
    head.appendChild(avatar);
    head.appendChild(now);
    head.appendChild(tokens);
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
    var tokenTotal = 0;
    var question = null;
    var approvals = [];
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
      if (ev.store_tool) li.dataset.storeTool = ev.store_tool;
      // A change the store held for the merchant's yes is waiting, not failed.
      if (li.dataset.waiting && ev.state !== 'running') {
        li.querySelector('.lt-ms').textContent = duration(ev.ms);
        if (!running()) say('Thinking…');
        return;
      }
      li.dataset.state = ev.state;
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

    // Her words before the next tool calls, as a line between the steps.
    function onSay(ev) {
      var li = el('li', 'lt-say', ev.text || '');
      steps.appendChild(li);
      var line = String(ev.text || '').replace(/\s+/g, ' ');
      if (line) say(line.length > 90 ? line.slice(0, 89) + '…' : line);
      scroll();
    }

    function compact(n) {
      if (n < 1000) return String(n);
      return (n < 10000 ? (n / 1000).toFixed(1) : Math.round(n / 1000)) + 'k';
    }
    function onUsage(ev) {
      tokenTotal = ev.tokens || 0;
      if (!tokenTotal) return;
      tokens.hidden = false;
      tokens.textContent = compact(tokenTotal) + ' tokens';
    }

    function onRetry(ev) {
      var li = addRow('retry-' + count);
      li.dataset.state = 'error';
      li.querySelector('.lt-label').textContent = 'The AI provider did not answer';
      li.querySelector('.lt-detail').textContent = (ev.status ? 'HTTP ' + ev.status : '')
        + (ev.retrying ? (ev.status ? ' · ' : '') + 'trying again' : '');
      say(ev.retrying ? 'The AI provider did not answer, trying again…' : 'The AI provider did not answer');
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
      noteCard(ev, li);
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

    // What follows the answer: her question, and changes waiting for a yes.
    function noteCard(ev, li) {
      if (ev.name === 'assistant.ask' && !ev.error && ev.output && typeof ev.output === 'object'
          && typeof ev.output.question === 'string') {
        question = {
          text: ev.output.question,
          choices: Array.isArray(ev.output.choices) ? ev.output.choices.slice(0, 4) : [],
        };
        return;
      }
      if (typeof ev.error === 'string' && ev.error.indexOf('approval_required') === 0) {
        var args = argsByTool[ev.name] || {};
        var key = ev.name + JSON.stringify(args);
        for (var i = 0; i < approvals.length; i += 1) if (approvals[i].key === key) return;
        if (approvals.length >= 3) return;
        var label = li.querySelector('.lt-label').textContent || humanise(ev.name);
        var detail = li.querySelector('.lt-detail').textContent;
        approvals.push({key: key, label: label.replace(/^Updat(?:ing|ed) /, 'Update ')
          + (detail ? ': ' + detail : ''), args: args});
        li.dataset.waiting = '1';
        li.dataset.state = 'waiting';
        li.querySelector('.lt-label').textContent = 'Waiting for your approval';
      }
    }

    var HIDDEN_ARGS = {confirmed: 1, hard_gate_ack: 1, echo: 1};
    function argLines(args) {
      var out = [];
      Object.keys(args || {}).forEach(function (k) {
        if (HIDDEN_ARGS[k] || out.length >= 8) return;
        var v = args[k];
        var text = (v !== null && typeof v === 'object') ? JSON.stringify(v) : String(v);
        out.push([humanise(k), text.length > 200 ? text.slice(0, 199) + '…' : text]);
      });
      return out;
    }

    function card(cls, title) {
      var box = el('div', 'lq ' + cls);
      box.appendChild(el('p', 'lq-title', title));
      return box;
    }
    function buttons(box, items) {
      var row = el('div', 'lq-actions');
      items.forEach(function (it) {
        var b = el('button', 'lq-btn' + (it.primary ? ' lq-btn--primary' : ''), it.label);
        b.type = 'button';
        b.addEventListener('click', function () {
          box.querySelectorAll('button').forEach(function (x) { x.disabled = true; });
          b.dataset.chosen = 'true';
          it.run();
        });
        row.appendChild(b);
      });
      box.appendChild(row);
    }

    function showCards() {
      var reply = opts.reply;
      if (typeof reply !== 'function') return;
      approvals.forEach(function (a) {
        var box = card('lq--approve', 'Linda wants to make this change');
        box.appendChild(el('p', 'lq-what', a.label));
        var lines = argLines(a.args);
        if (lines.length) {
          var dl = el('dl', 'lq-args');
          lines.forEach(function (pair) {
            dl.appendChild(el('dt', null, pair[0]));
            dl.appendChild(el('dd', null, pair[1]));
          });
          box.appendChild(dl);
        }
        buttons(box, [
          // Plain words: the consent kernel lets any negation win, and a label
          // such as "cancel" would turn an approval into a refusal.
          {label: 'Approve', primary: true, run: function () { reply('Yes, go ahead.', {}); }},
          {label: 'Decline', run: function () { reply("No, don't make that change.", {}); }},
        ]);
        log.appendChild(box);
      });
      if (question) {
        var q = card('lq--ask', question.text);
        var items = question.choices.map(function (c) {
          return {label: c, run: function () { reply(c, {answer: true}); }};
        });
        items.push({label: 'Something else…', run: function () {
          q.querySelectorAll('button').forEach(function (x) { x.disabled = false; });
          if (typeof opts.focus === 'function') opts.focus();
        }});
        buttons(q, items);
        log.appendChild(q);
      }
      if (approvals.length || question) scroll();
    }

    function setOpen(open) {
      root.dataset.open = open ? 'true' : 'false';
      head.setAttribute('aria-expanded', String(open));
    }
    head.addEventListener('click', function () {
      if (finished && (steps.children.length || !plan.hidden)) setOpen(root.dataset.open !== 'true');
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
      if (!count && plan.hidden && !steps.children.length) head.querySelector('.lt-chevron').style.display = 'none';
      if (outcome !== 'error') showCards();
    }

    return {
      element: root,
      finish: finish,
      event: function (ev) {
        if (!ev || finished) return;
        if (ev.type === 'step') onStep(ev);
        else if (ev.type === 'plan') onPlan(ev);
        else if (ev.type === 'say') onSay(ev);
        else if (ev.type === 'usage') onUsage(ev);
        else if (ev.type === 'retry') onRetry(ev);
        else if (ev.type === 'tool_call_started') argsByTool[ev.name] = ev.arguments || {};
        else if (ev.type === 'tool_call_finished') onToolFinished(ev);
      },
    };
  }

  window.LindaActivity = { start: start };
})();
