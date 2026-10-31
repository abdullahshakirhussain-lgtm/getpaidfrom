// Get Paid From: in-browser search over search.json, and opening the tile/line named in the URL hash.
(function () {
  var root = document.currentScript.getAttribute('data-root') || '';
  var lang = document.documentElement.lang || 'en';
  var STOP_EN = 'can i we get paid pay from in into use using does do work works working with receive money how to my the a an is for of and or available me it';
  var data = null, loading = null, stop = null, topics = null;

  function load() {
    if (data) return Promise.resolve(data);
    if (!loading) loading = fetch(root + 'search.json').then(function (r) { return r.json(); }).then(function (d) {
      stop = {}; (STOP_EN + ' ' + d.stop.join(' ')).split(' ').forEach(function (w) { if (w) stop[norm(w)] = 1; });
      // topic words may be several words long ("impuesto sobre la renta"); longest first so they win over their parts
      topics = Object.keys(d.topics).map(function (w) { return [norm(w), d.topics[w]]; }).sort(function (a, b) { return b[0].length - a[0].length; });
      data = d; return d;
    });
    return loading;
  }
  function norm(s) {
    // Latin accents and Arabic vowel marks are dropped so "peru" finds "Perú"; other scripts keep their letters
    return s.toLowerCase().normalize('NFKD').replace(/[̀-ًͯ-ٰٟ]/g, '').replace(/[^\p{L}\p{N}\p{M} ]+/gu, ' ').replace(/\s+/g, ' ').trim();
  }
  function fill(tpl, kw) { return tpl.replace(/\{(\w+)\}/g, function (m, k) { return kw[k]; }); }
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }

  function parse(q, d) {
    var text = ' ' + norm(q) + ' ', platform = null, topic = null;
    Object.keys(d.platforms).forEach(function (slug) {
      var names = [norm(d.platforms[slug]), slug.replace('-', ' '), slug.split('-')[0]];
      names.forEach(function (n) {
        if (!platform && text.indexOf(' ' + n + ' ') !== -1) { platform = slug; text = text.replace(' ' + n + ' ', ' '); }
      });
    });
    topics.forEach(function (w) {
      if (text.indexOf(' ' + w[0] + ' ') !== -1) {
        // the first (longest) match names the topic; other topic words ("impuesto ... renta") are dropped too
        if (!topic) topic = w;
        text = text.replace(' ' + w[0] + ' ', ' ');
      }
    });
    var rest = text.split(' ').filter(function (w) { return w && !stop[w]; }).join(' ');
    function match(r) {
      var found = [];
      d.countries.forEach(function (c) {
        var k = norm(c.k), n = norm(c.n), score = 0;
        if (n === r) score = 3; else if (n.indexOf(r) === 0 || (' ' + k).indexOf(' ' + r) !== -1) score = 2; else if (k.indexOf(r) !== -1) score = 1;
        if (score) found.push([score, c]);
      });
      return found;
    }
    var countries = rest ? match(rest) : [];
    if (!countries.length && rest.indexOf(' ') !== -1) {
      // a leftover word we don't know ("sobre peru"): try the words on their own, last first
      rest.split(' ').reverse().some(function (w) { countries = w.length > 2 ? match(w) : []; return countries.length; });
    }
    countries.sort(function (a, b) { return b[0] - a[0] || a[1].n.localeCompare(b[1].n, lang); });
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
        out.push({href: root + c.s + '/#' + p.platform, html: '<b>' + esc(fill(d.ui.s_in, {thing: d.platforms[p.platform], country: c.n})) + '</b> ' + chip(d, t[0]) + '<span class="r">' + esc(t[1]) + '</span>'});
      });
    } else if (p.topic && cs.length) {
      cs.forEach(function (c) {
        var a = p.topic[1], line = c.a[a];
        var label = p.topic[0] === 'upwork' ? 'Upwork' : d.labels[a];
        out.push({href: root + c.s + '/#' + a, html: '<b>' + esc(fill(d.ui.s_in, {thing: label, country: c.n})) + '</b><span class="r">' + esc(line || d.ui.s_see_details) + '</span>'});
      });
    } else if (cs.length) {
      cs.forEach(function (c) {
        var mini = ['paypal', 'payoneer', 'wise'].map(function (k) { return esc(d.platforms[k]) + ' ' + chip(d, c.t[k][0]); }).join(' ');
        out.push({href: root + c.s + '/', html: '<b>' + esc(c.n) + '</b><span class="r">' + mini + '</span>'});
      });
    }
    if (p.topic && p.topic[0] === 'upwork' && !p.rest) {
      out.unshift({href: root + 'upwork/', html: '<b>' + esc(d.ui.s_upwork) + '</b><span class="r">' + esc(d.ui.s_upwork_sub) + '</span>'});
    }
    if (p.platform && !p.rest) {
      out.unshift({href: root + p.platform + '/', html: '<b>' + esc(fill(d.ui.s_where_work, {service: d.platforms[p.platform]})) + '</b><span class="r">' + esc(d.ui.s_every_country) + '</span>'});
    }
    if (!out.length && norm(q)) out.push({href: null, html: '<span class="r">' + esc(d.ui.s_no_match) + '</span>'});
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
            msg.textContent = form.getAttribute('data-ok');
            form.querySelector('input[type=email]').value = '';
          } else {
            msg.textContent = form.getAttribute('data-err');
          }
        })
        .catch(function () { msg.textContent = form.getAttribute('data-net'); })
        .then(function () { btn.disabled = false; });
    });
  });

  // suggest the reader's own language once, if this page exists in it (choice remembered in this browser only)
  (function () {
    var pick = document.querySelector('.lang-pick');
    if (!pick || !navigator.languages) return;
    var dismissed = null;
    try { dismissed = localStorage.getItem('gpf-lang'); } catch (e) { return; }
    if (dismissed) return;
    var wanted = navigator.languages.map(function (l) { return l.slice(0, 2).toLowerCase(); });
    for (var i = 0; i < wanted.length; i++) {
      if (wanted[i] === lang) return;  // the reader already prefers this page's language
      var link = pick.querySelector('a[hreflang="' + wanted[i] + '"]');
      if (!link) continue;
      var bar = document.createElement('div');
      bar.className = 'suggest';
      var a = document.createElement('a');
      a.href = link.getAttribute('href'); a.lang = wanted[i]; a.dir = link.dir; a.textContent = link.getAttribute('data-suggest');
      var close = document.createElement('button');
      close.type = 'button'; close.setAttribute('aria-label', pick.getAttribute('data-close')); close.textContent = '×';
      function remember() { try { localStorage.setItem('gpf-lang', '1'); } catch (e) { /* private mode: just hide */ } }
      close.addEventListener('click', function () { remember(); bar.remove(); });
      a.addEventListener('click', remember);
      bar.appendChild(a); bar.appendChild(close);
      var skip = document.querySelector('.skip');
      if (skip) skip.after(bar); else document.body.prepend(bar);
      return;
    }
  })();

  // paid Country Pack: send the license key to our Worker, which checks it with Gumroad and returns the pack text.
  // The browser remembers the key (no cookie), so the pack opens by itself next time.
  (function () {
    var form = document.querySelector('[data-pack]');
    if (!form) return;
    var body = document.querySelector('[data-pack-body]'), msg = form.querySelector('[data-pack-msg]');
    var input = form.querySelector('input'), button = form.querySelector('button');
    var name = 'gpf-pack-' + form.dataset.pack;
    function saved() { try { return localStorage.getItem(name); } catch (e) { return null; } }
    function keep(k) { try { if (k) localStorage.setItem(name, k); else localStorage.removeItem(name); } catch (e) { /* private window */ } }
    function open(html) {
      body.querySelector('[data-pack-text]').innerHTML = html;
      body.hidden = false;
      document.querySelectorAll('[data-pack-sales]').forEach(function (el) { el.hidden = true; });
    }
    function unlock(key, fresh) {
      button.disabled = true;
      return fetch(form.getAttribute('action'), {
        method: 'POST', headers: {'content-type': 'application/json'},
        body: JSON.stringify({country: form.dataset.pack, key: key, fresh: fresh})
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (d.ok) { keep(key); open(d.html); return; }
        if (d.code !== 'unavailable') keep(null);
        msg.textContent = d.error;
      }).catch(function () { msg.textContent = form.dataset.net; }).then(function () { button.disabled = false; });
    }
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      msg.textContent = '';
      unlock(input.value.trim(), true);
    });
    document.querySelector('[data-pack-forget]').addEventListener('click', function () { keep(null); location.reload(); });
    var key = saved();
    if (key) unlock(key, false);
  })();

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
