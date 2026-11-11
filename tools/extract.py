#!/usr/bin/env python3
"""One-time: pull clean content out of the WordPress copy in site/ into content/pages.json.

Keeps each page's URL, SEO tags, structured data, headings, text, images and links,
and drops the WordPress/Oxygen layout, plugins and widgets.
"""
import os, re, json, glob, html
from bs4 import BeautifulSoup, NavigableString, Comment

SRC = "site"
OUT = "content"
APPLY = "https://goluminate.tidalwave.ai/signup/brandon.crysler/D831E6THA3VLDR8GHACG"

KEEP = {"h2", "h3", "h4", "h5", "p", "ul", "ol", "li", "a", "strong", "b", "em", "i", "img",
        "table", "thead", "tbody", "tr", "th", "td", "blockquote", "br", "figure", "figcaption"}
DROP = {"script", "style", "noscript", "svg", "form", "iframe", "button", "input", "select", "textarea", "nav", "header", "footer"}

def img_src(el):
    for k in ("data-src", "src"):
        v = el.get(k, "")
        if v and not v.startswith("data:"):
            return v
    return ""

def clean_fragment(node):
    """Return sanitized HTML for a node's content."""
    node = BeautifulSoup(str(node), "lxml")
    for c in node.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in node.find_all(DROP):
        t.decompose()
    for t in node.find_all(class_=re.compile(r"^(?:elfsight.*|oxy-modal.*|extras-toc.*|toc|adj-post.*|post-meta|share.*)$")):
        t.decompose()
    for t in node.find_all("h1"):
        t.name = "h2"
    for t in node.find_all("h6"):
        t.name = "h5"
    for t in list(node.find_all(True)):
        if t.name in ("html", "body"):
            continue
        if t.name not in KEEP:
            t.unwrap()
            continue
        attrs = {}
        if t.name == "a":
            href = t.get("href", "")
            if not href or href.startswith("#"):
                t.unwrap(); continue
            attrs["href"] = href
            cls = " ".join(t.get("class", []))
            if "link-button" in cls or "btn" in cls:
                attrs["class"] = "btn"
            if href.startswith("http") and "southernhl.com" not in href:
                attrs["target"] = "_blank"; attrs["rel"] = "noopener"
        elif t.name == "img":
            src = img_src(t)
            if not src:
                t.decompose(); continue
            attrs = {"src": src, "alt": t.get("alt", ""), "loading": "lazy"}
            for k in ("width", "height"):
                if t.get(k): attrs[k] = t.get(k)
        elif t.name in ("td", "th") and t.get("colspan"):
            attrs["colspan"] = t.get("colspan")
        t.attrs = attrs
    body = node.body or node
    out = "".join(str(c) for c in body.contents)
    out = re.sub(r"<p>\s*(?:&nbsp;| |<br/?>|\s)*</p>", "", out)
    out = re.sub(r"(<br/?>\s*){2,}", "<br/>", out)
    out = re.sub(r"\n\s*\n+", "\n", out)
    return out.strip()

def text(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""

def seo(soup):
    head = soup.head
    d = {"title": text(head.title) if head.title else ""}
    m = head.find("meta", attrs={"name": "description"})
    d["description"] = m["content"] if m else ""
    c = head.find("link", rel="canonical")
    d["canonical"] = c["href"] if c else ""
    r = head.find("meta", attrs={"name": "robots"})
    d["robots"] = r["content"] if r else ""
    d["meta"] = [str(x) for x in head.find_all("meta", attrs={"property": re.compile(r"^(og:|article:)")})] + \
                [str(x) for x in head.find_all("meta", attrs={"name": re.compile(r"^twitter:")})]
    d["jsonld"] = [x.string for x in head.find_all("script", type="application/ld+json") if x.string]
    og = head.find("meta", attrs={"property": "og:image"})
    d["image"] = og["content"].replace("https://southernhl.com", "") if og else ""
    return d

def main_sections(soup):
    body = soup.body
    inner = body.find(class_="ct-inner-content")
    secs = inner.find_all("section", recursive=False) if inner else body.find_all("section", recursive=False)
    return [s for s in secs if not set(s.get("class", [])) & {"reviews-section", "footer", "copyright-section"}]

def hero_info(sec):
    h = {"h1": "", "eyebrow": "", "lead": "", "image": "", "buttons": []}
    h1 = sec.find("h1")
    h["h1"] = text(h1)
    # small label above H1
    for el in sec.find_all(["div", "p", "span"], class_=re.compile("ct-text-block")):
        t = text(el)
        if t and t != h["h1"] and len(t) < 60 and not h["eyebrow"] and (not h1 or el.sourceline is None or True):
            if el.find_next("h1") is h1:
                h["eyebrow"] = t; break
    ps = [text(p) for p in sec.find_all(["p", "div"], class_=re.compile("ct-text-block")) if len(text(p)) > 60]
    h["lead"] = ps[0] if ps else ""
    img = sec.find("img")
    if img: h["image"] = img_src(img)
    for a in sec.find_all("a"):
        if a.get("href", "").startswith("#") or not text(a): continue
        h["buttons"].append({"text": text(a), "href": a["href"]})
    return h

pages = []
for path in sorted(glob.glob(os.path.join(SRC, "**", "index.html"), recursive=True)):
    rel = "/" + os.path.relpath(os.path.dirname(path), SRC).replace("\\", "/") + "/"
    rel = rel.replace("/./", "/")
    if rel.startswith("/wp-") or "/wp-content/" in rel:
        continue
    soup = BeautifulSoup(open(path, encoding="utf-8", errors="ignore").read(), "lxml")
    if not soup.head:
        continue
    p = {"url": rel, **seo(soup)}
    blog = soup.find(class_="blog-single-text")
    if blog:
        p["kind"] = "post"
        p["h1"] = text(soup.find("h1"))
        p["body"] = clean_fragment(blog)
        for j in p["jsonld"]:
            m = re.search(r'"datePublished":"([^"]+)"', j);
            if m: p["date"] = m.group(1)[:10]
            m = re.search(r'"dateModified":"([^"]+)"', j)
            if m: p["modified"] = m.group(1)[:10]
            m = re.search(r'"articleSection":"([^"]+)"', j)
            if m: p["category"] = m.group(1).split(",")[0]
        pages.append(p); continue
    secs = main_sections(soup)
    if rel.startswith("/loans/") and rel != "/loans/":
        p["kind"] = "loan"
    elif rel.startswith("/service-areas/"):
        p["kind"] = "area"
    elif rel.startswith("/category/"):
        p["kind"] = "category"
    else:
        p["kind"] = {"/": "home", "/blog/": "blog", "/loans/": "loans", "/contact/": "contact"}.get(rel, "page")
    if secs and (secs[0].find("h1") is not None):
        p["hero"] = hero_info(secs[0])
        rest = secs[1:]
    else:
        p["hero"] = {"h1": text(soup.find("h1")), "eyebrow": "", "lead": "", "image": "", "buttons": []}
        rest = secs
    p["h1"] = p["hero"]["h1"] or p["title"].split(" - ")[0]
    p["sections"] = [s for s in (clean_fragment(s) for s in rest) if len(re.sub("<[^>]+>", "", s).strip()) > 20 or "<img" in s]
    pages.append(p)

os.makedirs(OUT, exist_ok=True)
json.dump(pages, open(os.path.join(OUT, "pages.json"), "w"), indent=1, ensure_ascii=False)
from collections import Counter
print(len(pages), "pages", Counter(p["kind"] for p in pages))
