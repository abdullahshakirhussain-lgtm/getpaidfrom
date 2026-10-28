// Get Paid From: in-browser search over search.json, and opening the tile/line named in the URL hash.
(function () {
  var root = document.currentScript.getAttribute('data-root') || '';
  var STOP = /\b(can|i|we|get|paid|pay|from|in|into|use|using|does|do|work|works|working|with|receive|money|how|to|my|the|a|an|is|for|of|and|or|available|me|it)\b/g;
  var data = null, loading = null;

  function load() {
    if (data) return Promise.resolve(data);
    if (!loading) loading = fetch(root + 'search.json').then(function (r) { return r.json(); }).then(function (d) { data = d; return d; });
    return loading;
  }
  function norm(s) {
    return s.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
  }
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }

  function parse(q, d) {
    var text = ' ' + norm(q) + ' ', platform = null, topic = null;
    Object.keys(d.platforms).forEach(function (slug) {
      var names = [norm(d.platforms[slug]), slug.replace('-', ' '), slug.split('-')[0]];
      names.forEach(function (n) {
        if (!platform && text.indexOf(' ' + n + ' ') !== -1) { platform = slug; text = text.replace(' ' + n + ' ', ' '); }
      });
    });
    Object.keys(d.topics).forEach(function (w) {
      if (!topic && text.indexOf(' ' + w + ' ') !== -1) { topic = w; text = text.replace(' ' + w + ' ', ' '); }
    });
    var rest = text.replace(STOP, ' ').replace(/\s+/g, ' ').trim();
    var countries = [];
    if (rest) {
      d.countries.forEach(function (c) {
        var k = norm(c.k), n = norm(c.n), score = 0;
        if (n === rest) score = 3; else if (n.indexOf(rest) === 0 || (' ' + k).indexOf(' ' + rest) !== -1) score = 2; else if (k.indexOf(rest) !== -1) score = 1;
        if (score) countries.push([score, c]);
      });
      countries.sort(function (a, b) { return b[0] - a[0] || a[1].n.localeCompare(b[1].n); });
    }
    return {platform: platform, topic: topic, countries: countries.map(function (x) { return x[1]; }), rest: rest};
  }

  function chip(d, status) {
    var s = d.status[status];
    return '<span class="st ' + s[1] + '"><i aria-hidden="true"></i>' + esc(s[0]) + '</span>';
  }

  function results(q, d) {
    var p = parse(q, d), out = [];
    var cs = p.countries.slice(0, 5);
    if (p.platform && cs.length) {
      cs.forEach(function (c) {
        var t = c.t[p.platform];
        out.push({href: root + c.s + '/#' + p.platform, html: '<b>' + esc(d.platforms[p.platform]) + ' in ' + esc(c.n) + '</b> ' + chip(d, t[0]) + '<span class="r">' + esc(t[1]) + '</span>'});
      });
    } else if (p.topic && cs.length) {
      cs.forEach(function (c) {
        var a = d.topics[p.topic], line = c.a[a];
        var label = p.topic === 'upwork' ? 'Upwork' : a === 'ways' ? 'Legal ways to get paid' : p.topic.length <= 3 ? p.topic.toUpperCase() : p.topic;
        out.push({href: root + c.s + '/#' + a, html: '<b>' + esc(label) + ' in ' + esc(c.n) + '</b><span class="r">' + esc(line || 'See the details on the country page.') + '</span>'});
      });
    } else if (cs.length) {
      cs.forEach(function (c) {
        var mini = ['paypal', 'payoneer', 'wise'].map(function (k) { return esc(d.platforms[k]) + ' ' + chip(d, c.t[k][0]); }).join(' ');
        out.push({href: root + c.s + '/', html: '<b>' + esc(c.n) + '</b><span class="r">' + mini + '</span>'});
      });
    }
    if (p.topic === 'upwork' && !p.rest) {
      out.unshift({href: root + 'upwork/', html: '<b>Getting paid from Upwork</b><span class="r">Where it’s open, and how to receive the money</span>'});
    }
    if (p.platform && !p.rest) {
      out.unshift({href: root + p.platform + '/', html: '<b>Where does ' + esc(d.platforms[p.platform]) + ' work?</b><span class="r">Every country, with reasons</span>'});
    }
    if (!out.length && norm(q)) out.push({href: null, html: '<span class="r">No match yet. Try a country name, like “Kenya”, or a platform, like “Wise”.</span>'});
    return out;
  }

  document.querySelectorAll('[data-search]').forEach(function (box) {
    var input = box.querySelector('input'), list = box.querySelector('.results'), items = [], active = -1;
    function render() {
      load().then(function (d) {
        items = results(input.value, d); active = items.length && items[0].href ? 0 : -1;
        list.innerHTML = items.map(function (it, i) {
          return it.href ? '<a role="option" class="res' + (i === active ? ' on' : '') + '" href="' + it.href + '">' + it.html + '</a>' : '<span class="res none">' + it.html + '</span>';
        }).join('');
        list.hidden = !input.value.trim();
      });
    }
    input.addEventListener('input', render);
    input.addEventListener('focus', function () { load(); if (input.value.trim()) render(); });
    input.addEventListener('keydown', function (e) {
      var links = list.querySelectorAll('a.res');
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); if (!links.length) return;
        active = (active + (e.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
        links.forEach(function (a, i) { a.classList.toggle('on', i === active); });
      } else if (e.key === 'Enter' && links[active]) { location.href = links[active].getAttribute('href'); }
      else if (e.key === 'Escape') { list.hidden = true; }
    });
    document.addEventListener('click', function (e) { if (!box.contains(e.target)) list.hidden = true; });
  });
  document.querySelectorAll('[data-try]').forEach(function (b) {
    b.addEventListener('click', function (e) {
      e.preventDefault();
      var input = document.querySelector('.home-search input'); input.value = b.getAttribute('data-try');
      input.dispatchEvent(new Event('input')); input.focus();
    });
  });

  // email alerts: post to our own Worker (worker/index.js); without JS the form posts normally
  document.querySelectorAll('form[data-alerts]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var msg = form.querySelector('[data-alerts-msg]'), btn = form.querySelector('button');
      var data = {}; new FormData(form).forEach(function (v, k) { data[k] = v; });
      btn.disabled = true;
      fetch(form.getAttribute('action'), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)})
        .then(function (r) { return r.json().catch(function () { return {ok: false}; }); })
        .then(function (d) {
          if (d.ok) {
            msg.textContent = form.hasAttribute('data-unsub') ? 'Done. Your address and countries are deleted.' : 'Done. We’ll email you when this page changes.';
            form.querySelector('input[type=email]').value = '';
          } else {
            msg.textContent = d.error || 'That didn’t work. Check the address and try again.';
          }
        })
        .catch(function () { msg.textContent = 'Couldn’t reach the server. Try again later.'; })
        .then(function () { btn.disabled = false; });
    });
  });

  // rows in the options table open to show their sources
  function toggleRow(row, open) {
    var extra = row.nextElementSibling;
    if (open === undefined) open = extra.hidden;
    extra.hidden = !open; row.setAttribute('aria-expanded', String(open));
  }
  document.querySelectorAll('.options .row').forEach(function (row) {
    row.addEventListener('click', function (e) { if (!e.target.closest('a')) toggleRow(row); });
    row.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleRow(row); } });
  });

  function openHash() {
    var id = decodeURIComponent(location.hash.slice(1)); if (!id) return;
    var el = document.getElementById(id); if (!el) return;
    if (el.classList.contains('row')) toggleRow(el, true);
    var det = el.querySelector('details'); if (det) det.open = true;
    el.classList.add('flash'); setTimeout(function () { el.classList.remove('flash'); }, 1800);
  }
  window.addEventListener('hashchange', openHash); openHash();
})();
