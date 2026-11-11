#!/usr/bin/env python3
"""Edits applied to the static copy after every WordPress copy (tools/mirror.py).

Keeps Vercel-only changes from being undone when the site is re-copied.
Currently: removes all Homes for Heroes content (Brandon is leaving the program).
Hometown Heroes (Florida's down payment program) is a different program and is kept.
"""
import os, re, shutil, glob

SITE = os.path.abspath("site")
H4H_POST = "homes-for-heroes-a-program-that-benefits-homebuyers-with-discounts-and-savings"
REDIRECT_TO = "/home-loans-for-first-responders/"

def read(p):
    with open(p, encoding="utf-8", errors="ignore") as f:
        return f.read()

def write(p, t):
    with open(p, "w", encoding="utf-8") as f:
        f.write(t)

def remove_element(t, start_idx, tag):
    """Remove the element whose opening tag starts at start_idx, balancing nested tags of the same name."""
    depth, i = 0, start_idx
    pat = re.compile(r"<(/?)%s\b[^>]*>" % tag, re.I)
    for m in pat.finditer(t, start_idx):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return t[:start_idx] + t[m.end():]
    return t

def remove_heading_section(t, heading_re, level_stop):
    """Remove a heading and everything after it up to the next heading (h2..level_stop) or end of the content span."""
    m = re.search(heading_re, t, re.I)
    if not m:
        return t
    rest = t[m.end():]
    nxt = re.search(r"<h[2-%d][\s>]|</span>\s*</div>" % level_stop, rest, re.I)
    end = m.end() + (nxt.start() if nxt else 0)
    return t[:m.start()] + t[end:]

changed = []

for path in glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True):
    t = read(path)
    if not re.search(r"(?i)homes\s*for\s*heroes|homesforheroes|" + H4H_POST, t):
        continue
    o = t
    # Home page banner section (the Oxygen section with the Homes for Heroes banner image)
    for m in list(re.finditer(r'<section\b[^>]*>', t))[::-1]:
        seg_end = t.find("</section>", m.end())
        seg = t[m.end():seg_end] if seg_end != -1 else ""
        if "Homes-for-Heroes-Services" in seg and "<section" not in seg and "wp-block" not in seg:
            t = remove_element(t, m.start(), "section")
    # Blog article sections
    t = remove_heading_section(t, r'<h2 class="wp-block-heading">\s*Homes for Heroes\s*</h2>', 2)
    t = remove_heading_section(t, r'<h3 class="wp-block-heading">\s*Homes for Heroes\s*</h3>', 3)
    # Paragraphs that mention the program
    t = re.sub(r'<p class="wp-block-paragraph">(?:(?!</p>).)*?Homes? for Heroes(?:(?!</p>).)*?</p>', "", t, flags=re.S | re.I)
    # Previous/next post links pointing at the removed article
    t = re.sub(r'<a\b[^>]*href="/%s/"[^>]*>.*?</a>' % H4H_POST, "", t, flags=re.S)
    # Any remaining links to the affiliate site: keep the text, drop the link
    t = re.sub(r'<a\b[^>]*homesforheroes\.com[^>]*>(.*?)</a>', r"\1", t, flags=re.S)
    if t != o:
        write(path, t)
        changed.append(os.path.relpath(path, SITE))

# Remove the dedicated article and its images
shutil.rmtree(os.path.join(SITE, H4H_POST), ignore_errors=True)
for img in glob.glob(os.path.join(SITE, "wp-content", "uploads", "**", "Homes-for-Heroes*"), recursive=True):
    os.remove(img)

# Drop it from the sitemaps (the article and the banner image)
for sm in glob.glob(os.path.join(SITE, "*sitemap*.xml")):
    s = read(sm)
    s2 = re.sub(r"<url>(?:(?!</url>).)*?%s(?:(?!</url>).)*?</url>\s*" % H4H_POST, "", s, flags=re.S)
    s2 = re.sub(r"<image:image>\s*<image:loc>[^<]*Homes-for-Heroes[^<]*</image:loc>\s*</image:image>\s*", "", s2)
    if s2 != s:
        write(sm, s2)
        changed.append(os.path.basename(sm))

print("cleanup changed:", ", ".join(changed) or "nothing")
