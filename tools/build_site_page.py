#!/usr/bin/env python3
"""Render README.md (long version) and docs/short.md (short version) as vivlos.dev/s640.

usage: build_site_page.py OUT_DIR
Writes OUT_DIR/index.html and copies the images the page uses into OUT_DIR/images/.
Links to other files in this repository point at GitHub. Needs python-markdown
(nix-shell -p 'python3.withPackages(p:[p.markdown])').
"""
import html, pathlib, re, shutil, sys
import markdown

REPO = "https://github.com/Afterlight0338/s640-fw-docs-claude"
STYLE_V, PAGE_V = 7, 2          # /style.css?v= (bump with the main site) and /s640/s640.css?v=
root = pathlib.Path(__file__).resolve().parent.parent
out = pathlib.Path(sys.argv[1])
(out / "images").mkdir(parents=True, exist_ok=True)


def fix_link(m):
    attr, url = m.group(1), m.group(2)
    if re.match(r"(https?:|mailto:|#|/)", url):
        return m.group(0)
    if url.startswith("images/") and attr == "src":
        shutil.copy(root / url, out / url)
        return f'{attr}="{url}"'
    kind = "tree" if (root / url).is_dir() else "blob"
    return f'{attr}="{REPO}/{kind}/main/{url}"'


def render(text, id_prefix=""):
    """Markdown to HTML, numbered h2s, repo links, wrapped tables. Returns (html, [(id, num, name)])."""
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "md_in_html"],
                           extension_configs={"toc": {"toc_depth": "2"}})
    body = md.convert(text)
    body = re.sub(r'(href|src)="([^"]+)"', fix_link, body)
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    body = body.replace("<img ", '<img loading="lazy" ')
    toc, n = [], 0

    def h2(m):
        nonlocal n
        hid, name = m.group(1), m.group(2)
        num = re.match(r"(\d+)\.\s+", name)
        if num:
            n, name = int(num.group(1)), name[num.end():]
        else:
            n += 1
        new_id = id_prefix + hid
        toc.append((new_id, n, name))
        return f'<h2 id="{new_id}"><span class="h-num">{n:02d}</span>{name}</h2>'

    body = re.sub(r'<h2 id="([^"]+)">(.*?)</h2>', h2, body)
    return body, toc


# ---- long version: README without the GitHub banner, the h1 and its Contents list
readme = (root / "README.md").read_text()
readme = re.sub(r"<!-- banner:start -->.*?<!-- banner:end -->\s*", "", readme, flags=re.S)
long_body, long_toc = render(readme)
title = re.search(r"<h1[^>]*>(.*?)</h1>", long_body, re.S).group(1)
long_body = re.sub(r"<h1[^>]*>.*?</h1>\s*", "", long_body, count=1, flags=re.S)
long_body = re.sub(r'<h2 id="contents">.*?</h2>\s*<ol>.*?</ol>\s*', "", long_body, count=1, flags=re.S)
long_toc = [t for t in long_toc if t[0] != "contents"]

# ---- short version
short_body, short_toc = render((root / "docs/short.md").read_text(), id_prefix="tldr-")


def toc_html(items):
    return "\n".join(f'<li><a href="#{i}"><span class="toc-num">{n:02d}</span>{name}</a></li>'
                     for i, n, name in items)


DISCLAIMER = """
<p><strong>This entire write-up was written by Claude Opus 5.5 on xHigh reasoning.</strong>
I did not check every byte of it, and I am <strong>not responsible for anything in here that
turns out to be wrong.</strong> Some of it probably is.</p>
<p>Flash something because a web page told you to, turn your tablet into a very expensive
coaster, and that is on you. Not me, not Claude, you.</p>
<p>Read the code yourself. Measure with your own multimeter. Check every address and every
command before you run it. Better yet, do the shi yourself and use this as a map, not a
manual.</p>
"""

page = f"""<!DOCTYPE html>
<html lang="en" data-tab="projects">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Veikk S640 firmware notes, vivlos.dev</title>
  <meta name="description" content="Unbricking a Veikk S640 over SWD with a Pi Pico, how its firmware scans the pen, and removing the cursor smoothing. Every byte and measurement.">
  <meta name="theme-color" content="#080b12">
  <link rel="icon" type="image/webp" href="/assets/vivlos/racing.webp">
  <meta property="og:title" content="Veikk S640 firmware notes">
  <meta property="og:description" content="SWD unbrick, firmware internals and the zero-smoothing patch for the Veikk S640.">
  <meta property="og:url" content="https://vivlos.dev/s640/">
  <!-- Generated from README.md and docs/short.md by tools/build_site_page.py in {REPO}.
       Edit the source there. Uses the main stylesheet's tokens, fonts and switch:
       bump ?v= together with index.html -->
  <link rel="stylesheet" href="/style.css?v={STYLE_V}">
  <link rel="stylesheet" href="/s640/s640.css?v={PAGE_V}">
  <script>
    /* Runs before the body paints: gate state, short/long view, the site-wide motion choice.
       Storage can be blocked (private windows); everything falls back to the defaults. */
    (function () {{
      var h = document.documentElement;
      function get(k) {{ try {{ return localStorage.getItem(k); }} catch (e) {{ return null; }} }}
      var m = get('vivlos-motion');
      h.dataset.motion = m ? m : (matchMedia('(prefers-reduced-motion: reduce)').matches ? 'off' : 'on');
      if (get('vivlos-s640-ack') !== 'yes') h.classList.add('gated');
      var hs = location.hash;  /* a link into one version opens that version */
      h.dataset.view = /^#(allat|tldr-)/.test(hs) ? 'short'
        : /^#\\d/.test(hs) ? 'long' : (get('vivlos-s640-view') === 'short' ? 'short' : 'long');
    }})();
  </script>
</head>
<body>

  <section class="gate" role="dialog" aria-modal="true" aria-labelledby="gate-title">
    <div class="gate-text">
      <span class="gate-kicker">read this first</span>
      <h1 id="gate-title">You're on your own.</h1>
      {DISCLAIMER}
      <p class="gate-warned">You have been warned.</p>
      <div class="gate-actions">
        <button type="button" class="gate-accept" id="gate-accept">I get it, let me in</button>
        <a class="gate-leave" href="/">nah, take me back</a>
      </div>
      <span class="gate-note">remembered in this browser</span>
    </div>
    <img class="gate-art" src="/assets/vivlos/racing.webp" alt="Vivlos, not responsible either">
  </section>

  <div class="doc-canvas">
    <div class="top-status-bar">
      <a href="/#projects" class="status-home">vivlos.dev / s640</a>
      <span><span class="mono-dim">unit</span> Veikk S640</span>
      <span><span class="mono-dim">firmware</span> S640-251022 + nosmooth-nohold</span>
      <button type="button" class="motion-switch" id="allat-switch" role="switch" aria-checked="false">
        <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        i aint reading allat
      </button>
    </div>

    <header class="doc-head">
      <div class="doc-head-text">
        <span class="doc-kicker"><span class="view-long">project notes, the long version</span><span class="view-short">the short version: what to do, what not to do</span></span>
        <h1>{title}</h1>
        <p class="doc-meta">Written 2026-10-06 &middot; scripts, data and listings on <a href="{REPO}">GitHub</a></p>
        <dl class="doc-stats">
          <div><dt>report rate</dt><dd>250 Hz <span>scan-limited</span></dd></div>
          <div><dt>lag removed</dt><dd>&asymp;14 ms <span>8-sample average</span></dd></div>
          <div><dt>still jitter, nosmooth-nohold</dt><dd>&asymp;0.03 mm <span>raw sensor noise</span></dd></div>
          <div><dt>status</dt><dd>alive <span>unbricked over SWD</span></dd></div>
        </dl>
      </div>
      <img class="doc-art" src="/assets/vivlos/racing.webp" alt="">
    </header>

    <noscript>
      <div class="doc-noscript"><strong>Disclaimer.</strong> {DISCLAIMER} <strong>You have been warned.</strong></div>
    </noscript>

    <nav class="doc-toc" aria-label="Contents">
      <details open>
        <summary>Contents</summary>
        <ol class="view-long">
{toc_html(long_toc)}
        </ol>
        <ol class="view-short">
{toc_html(short_toc)}
        </ol>
      </details>
    </nav>

    <main class="doc-body">
      <article class="view-long">
{long_body}
      </article>
      <article class="view-short">
{short_body}
        <p class="short-more">That's the short version. Flip the switch at the top for the
        full write-up: how the firmware works, the proof for every claim, the failed experiments
        and every byte.</p>
      </article>
      <footer class="doc-foot">
        <a href="#top">back to top</a>
        <span>vivlos.dev &middot; written 2026-10-06 &middot; <a href="{REPO}">source</a></span>
      </footer>
    </main>
  </div>

  <script>
    (function () {{
      var h = document.documentElement;
      function set(k, v) {{ try {{ localStorage.setItem(k, v); }} catch (e) {{ /* storage blocked */ }} }}

      // gate
      var accept = document.getElementById('gate-accept');
      if (h.classList.contains('gated')) accept.focus();
      accept.addEventListener('click', function () {{
        set('vivlos-s640-ack', 'yes');
        h.classList.remove('gated');
        window.scrollTo(0, 0);
      }});

      // short / long switch
      var sw = document.getElementById('allat-switch');
      function show(view, scroll) {{
        h.dataset.view = view;
        sw.setAttribute('aria-checked', view === 'short' ? 'true' : 'false');
        if (scroll) window.scrollTo(0, 0);
        spy();
      }}
      sw.addEventListener('click', function () {{
        var next = h.dataset.view === 'short' ? 'long' : 'short';
        set('vivlos-s640-view', next);
        show(next, true);
      }});

      // contents rail: mark the section being read
      var links = {{}};
      document.querySelectorAll('.doc-toc a').forEach(function (a) {{ links[a.getAttribute('href').slice(1)] = a; }});
      var current = null, io = null;
      function spy() {{
        if (!('IntersectionObserver' in window)) return;
        if (io) io.disconnect();
        var heads = document.querySelectorAll(h.dataset.view === 'short' ? '.view-short h2' : '.view-long h2');
        io = new IntersectionObserver(function (entries) {{
          entries.forEach(function (e) {{
            if (!e.isIntersecting) return;
            if (current) current.classList.remove('is-current');
            current = links[e.target.id];
            if (current) current.classList.add('is-current');
          }});
        }}, {{ rootMargin: '0px 0px -75% 0px' }});
        heads.forEach(function (el) {{ io.observe(el); }});
      }}
      show(h.dataset.view, false);

      // copy buttons on short code blocks (commands, not the long listings)
      document.querySelectorAll('.doc-body pre').forEach(function (pre) {{
        if (pre.textContent.split('\\n').length > 30 || !navigator.clipboard) return;
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'copy-btn'; b.textContent = 'copy';
        b.addEventListener('click', function () {{
          navigator.clipboard.writeText(pre.textContent.replace(/\\n$/, '')).then(function () {{
            b.textContent = 'copied'; setTimeout(function () {{ b.textContent = 'copy'; }}, 1400);
          }});
        }});
        var wrap = document.createElement('div');  /* outside the scrolling pre, so it stays put */
        wrap.className = 'code-wrap';
        pre.parentNode.insertBefore(wrap, pre);
        wrap.appendChild(pre);
        wrap.appendChild(b);
      }});
    }})();
  </script>
</body>
</html>
"""
page = page.replace('<body>', '<body id="top">', 1)
(out / "index.html").write_text(page)
print(f"wrote {out / 'index.html'} ({len(page)} bytes)")
