#!/usr/bin/env python3
"""Render README.md as the vivlos.dev/s640 page.

usage: build_site_page.py OUT_DIR
Writes OUT_DIR/index.html and copies the images the page uses into OUT_DIR/images/.
Links to other files in this repository point at GitHub. Needs python-markdown
(nix-shell -p 'python3.withPackages(p:[p.markdown])').
"""
import html, pathlib, re, shutil, sys
import markdown

REPO = "https://github.com/Afterlight0338/s640-fw-docs-claude"
root = pathlib.Path(__file__).resolve().parent.parent
out = pathlib.Path(sys.argv[1])
(out / "images").mkdir(parents=True, exist_ok=True)

src = (root / "README.md").read_text()
md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "md_in_html"],
                       extension_configs={"toc": {"toc_depth": "2"}})
body = md.convert(src)

# The h1 and its intro go into the page header; the "Contents" list becomes the side rail.
title = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S).group(1)
body = re.sub(r"<h1[^>]*>.*?</h1>\s*", "", body, count=1, flags=re.S)
body = re.sub(r'<h2 id="contents">Contents</h2>\s*<ol>.*?</ol>\s*', "", body, count=1, flags=re.S)


def fix_link(m):
    attr, url = m.group(1), m.group(2)
    if re.match(r"(https?:|mailto:|#)", url):
        return m.group(0)
    if url.startswith("images/") and attr == "src":
        shutil.copy(root / url, out / url)
        return f'{attr}="{url}"'
    kind = "tree" if (root / url).is_dir() else "blob"
    return f'{attr}="{REPO}/{kind}/main/{url}"'


body = re.sub(r'(href|src)="([^"]+)"', fix_link, body)
body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
body = body.replace("<img ", '<img loading="lazy" ')

tokens = md.toc_tokens
if len(tokens) == 1 and tokens[0]["level"] == 1:  # every h2 is nested under the h1
    tokens = tokens[0]["children"]
toc = "\n".join(
    f'<li><a href="#{t["id"]}">{t["name"]}</a></li>' for t in tokens if t["id"] != "contents")

page = f"""<!DOCTYPE html>
<html lang="en" data-tab="projects">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Veikk S640 firmware notes, vivlos.dev</title>
  <meta name="description" content="Unbricking a Veikk S640 over SWD with a Pi Pico, how its firmware scans the pen, and removing the cursor smoothing. Every byte and measurement.">
  <meta name="theme-color" content="#080b12">
  <link rel="icon" type="image/webp" href="/assets/vivlos/casual.webp">
  <meta property="og:title" content="Veikk S640 firmware notes">
  <meta property="og:description" content="SWD unbrick, firmware internals and the zero-smoothing patch for the Veikk S640.">
  <meta property="og:url" content="https://vivlos.dev/s640/">
  <!-- Generated from README.md by tools/build_site_page.py in {REPO}. Edit the source there.
       Uses the main stylesheet's tokens and fonts: bump ?v= together with index.html -->
  <link rel="stylesheet" href="/style.css?v=7">
  <link rel="stylesheet" href="/s640/s640.css?v=1">
</head>
<body>
  <div class="doc-canvas">
    <header class="doc-head">
      <a class="doc-back" href="/#projects">vivlos.dev / projects</a>
      <h1>{title}</h1>
      <p class="doc-meta">Written 2026-10-06 &middot; source, scripts and data on
        <a href="{REPO}">GitHub</a></p>
    </header>
    <nav class="doc-toc" aria-label="Contents">
      <details open>
        <summary>Contents</summary>
        <ol>
{toc}
        </ol>
      </details>
    </nav>
    <main class="doc-body">
{body}
    </main>
  </div>
</body>
</html>
"""
(out / "index.html").write_text(page)
print(f"wrote {out / 'index.html'} ({len(page)} bytes)")
