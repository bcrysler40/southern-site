#!/usr/bin/env python3
"""Build the redesigned southernhl.com into ./site from content/*.json and src/.

Run:  python3 tools/build_site.py
Edit page text in content/pages.json (or ask Claude), the look in src/styles.css,
and the shared pieces (header, footer, homepage) in this file.
"""
import os, re, json, html, shutil, hashlib, glob, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site")
UPLOADS_SRC = os.path.join(ROOT, "uploads")          # wp-content/uploads kept from WordPress
DOMAIN = "https://southernhl.com"

PHONE, PHONE_TEL = "352-622-1521", "+13526221521"
EMAIL = "bc@southernhl.co"
ADDRESS = ("2050 E Silver Springs Blvd", "Ocala, FL 34470")
APPLY = "https://goluminate.tidalwave.ai/signup/brandon.crysler/D831E6THA3VLDR8GHACG"
NMLS = "162096"
HS_PORTAL, HS_FORM, HS_REGION = "242109586", "f7c9da26-9530-4f31-92b1-4db11e576281", "na2"
ELFSIGHT = "elfsight-app-f2051ee6-0c7b-461c-9366-2b071b010398"
# Google Business Profile (Southern Home Loans | Luminate Bank, 2050 E Silver Springs Blvd)
GOOGLE_PLACE_ID = "ChIJ9_Vzv7Qs5ogRE5TljgYHvHw"
GOOGLE_REVIEWS = f"https://search.google.com/local/reviews?placeid={GOOGLE_PLACE_ID}"
GOOGLE_MAPS = f"https://www.google.com/maps/place/?q=place_id:{GOOGLE_PLACE_ID}"
GOOGLE_WRITE_REVIEW = f"https://search.google.com/local/writereview?placeid={GOOGLE_PLACE_ID}"
# Builder Advantage advertised rate - the APR must appear wherever the rate does (Reg Z 1026.24(c))
BUILDER_RATE, BUILDER_APR = "4.99%", "5.838%"
BUILDER_NOTE = (f"*Builder Advantage: {BUILDER_RATE} interest rate, {BUILDER_APR} Annual Percentage Rate (APR), "
    "on a fixed-rate FHA purchase loan available only through a builder forward commitment on select new homes, "
    "for qualified buyers who close within the commitment period. Rates, terms and availability are subject to change "
    "without notice. Not all applicants will qualify. "
    '<a href="/loans/builder-advantage-program/">See program terms and a payment example</a>.')
META_PIXEL, GOOGLE_ADS = "1267196966680196", "AW-957845406"
SOCIAL = [("Facebook", "https://www.facebook.com/TeamSHL"), ("Instagram", "https://www.instagram.com/southernhl/"),
          ("LinkedIn", "https://www.linkedin.com/in/bcrysler/")]
LOGO = "/wp-content/uploads/2025/07/LOGO-SHL.png"
BRANDON = "/wp-content/uploads/2023/05/Brandon.jpg"
HERO = "/wp-content/uploads/2022/05/Homepage-Hero.jpg"

PAGES = json.load(open(os.path.join(ROOT, "content", "pages.json")))
LOANS = json.load(open(os.path.join(ROOT, "content", "loans.json")))
BY_URL = {p["url"]: p for p in PAGES}
SEO = json.load(open(os.path.join(ROOT, "content", "seo.json")))
AREAS = [("Ocala", "/service-areas/ocala/"), ("Gainesville", "/service-areas/gainesville/"), ("Crystal River", "/service-areas/crystal-river/"),
         ("Inverness", "/service-areas/inverness/"), ("Spring Hill", "/service-areas/spring-hill/"), ("Hernando", "/service-areas/hernando/"),
         ("Levy County", "/service-areas/levy-county/"), ("All of Florida", "/service-areas/mortgages-and-fha-loans-in-florida/")]

def _meta_set(meta, key, value):
    """Replace the content of an og:/twitter: tag (Yoast/RankMath output) or add it."""
    pat = re.compile(r'<meta content="[^"]*" (?:property|name)="' + re.escape(key) + '"/>')
    tag_attr = "property" if key.startswith(("og:", "article:")) else "name"
    new = f'<meta content="{esc(value)}" {tag_attr}="{key}"/>'
    for i, m in enumerate(meta):
        if pat.fullmatch(m.strip()):
            meta[i] = new; return
    meta.append(new)

def apply_seo(p):
    """Layer content/seo.json (titles, descriptions, FAQs) and schema fixes onto a page."""
    o = SEO["pages"].get(p["url"], {})
    if o.get("title"): p["title"] = o["title"]
    if o.get("description"): p["description"] = o["description"]
    meta = [m for m in p.get("meta", []) if not re.search(r'name="twitter:(label|data)\d"', m)]   # "Written by cody" leftovers
    meta = [re.sub(r'content="@https://twitter.com/SouthernHL"', 'content="@SouthernHL"', m) for m in meta]
    url = p.get("canonical") or DOMAIN + p["url"]
    for k, v in (("og:title", p.get("title")), ("twitter:title", p.get("title")), ("og:description", p.get("description")),
                 ("twitter:description", p.get("description")), ("og:url", url)):
        if v: _meta_set(meta, k, v)
    if not any('og:image"' in m for m in meta):
        _meta_set(meta, "og:image", DOMAIN + (p.get("image") or HERO)); _meta_set(meta, "twitter:card", "summary_large_image")
    p["meta"] = meta
    lds = []
    for j in p.get("jsonld", []):
        j = (j.replace('"https://southernhl.com/author/cody/"', '"https://southernhl.com/about/#brandon"')
              .replace('"name":"cody"', '"name":"Brandon Crysler"').replace('"caption":"cody"', '"caption":"Brandon Crysler"'))
        j = re.sub(r'"https://southernhl.com/wp-content/litespeed/avatar/[^"]*"', '"' + DOMAIN + BRANDON + '"', j)
        try: d = json.loads(j)
        except ValueError: lds.append(j); continue
        for n in d.get("@graph", [d]):
            if n.get("@id", "").endswith("#organization"):
                n["sameAs"] = [u for _, u in SOCIAL] + ["https://twitter.com/SouthernHL", GOOGLE_MAPS]
                n["openingHours"] = ["Mo-Fr 08:30-17:30"]
                n.setdefault("telephone", "+1-" + PHONE)
                n["areaServed"] = {"@type": "State", "name": "Florida"}
            if n.get("@type") == "WebPage" and o.get("title"):
                n["name"] = p["title"]
                if p.get("description"): n["description"] = p["description"]
        lds.append(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    faqs = SEO["faqs"].get(p["url"])
    if faqs:
        p["faqs"] = faqs
        lds.append(json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}, ensure_ascii=False, separators=(",", ":")))
    p["jsonld"] = lds

POSTS = sorted([p for p in PAGES if p["kind"] == "post"], key=lambda p: p.get("date", ""), reverse=True)
CATS = {}
for p in PAGES:
    if p["kind"] == "category":
        name = re.sub(r"\s*(Archives)?\s*-\s*Southern Home Loans.*$", "", p["title"]).strip()
        CATS[p["url"]] = name

esc = lambda s: html.escape(s or "", quote=True)

for _p in PAGES:
    apply_seo(_p)

def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def fmt_date(d):
    try:
        return datetime.date.fromisoformat(d).strftime("%B %-d, %Y")
    except Exception:
        return d or ""

def titlecase(s):
    return s.title() if s.isupper() else s

# ---------------------------------------------------------------- icons
ICON = {
 "phone": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.5 2.7.6a2 2 0 0 1 1.7 2z"/></svg>',
 "mail": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 6-10 7L2 6"/></svg>',
 "pin": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="3"/></svg>',
 "doc": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h6"/></svg>',
 "spark": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/></svg>',
 "home": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
 "shield": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>',
 "clock": '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
 "down": '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m6 9 6 6 6-6"/></svg>',
 "fb": '<svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M14 8h3V4h-3c-2.8 0-4 1.8-4 4.4V11H7v4h3v9h4v-9h3l1-4h-4V8.6c0-.4.2-.6.6-.6z"/></svg>',
 "ig": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="#fff"/></svg>',
 "li": '<svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M4 9h4v12H4zM6 3a2 2 0 1 1 0 4 2 2 0 0 1 0-4zM10 9h4v1.7c.6-1 1.9-2 3.9-2 4 0 4.1 2.7 4.1 6V21h-4v-5.5c0-1.4 0-3.2-2-3.2s-2.2 1.5-2.2 3.1V21h-4z"/></svg>',
}

# ---------------------------------------------------------------- shared pieces
CSS_VER = hashlib.md5(open(os.path.join(ROOT, "src", "styles.css"), "rb").read()).hexdigest()[:8]

def head(p, title=None, desc=None):
    title = title or p.get("title") or "Southern Home Loans"
    desc = desc if desc is not None else p.get("description", "")
    canon = p.get("canonical") or (DOMAIN + p["url"])
    extra = "\n".join(p.get("meta", []))
    jsonld = "\n".join(f'<script type="application/ld+json">{j}</script>' for j in p.get("jsonld", []))
    robots = f'<meta name="robots" content="{esc(p["robots"])}">' if p.get("robots") else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canon)}">
{robots}
{extra}
<meta name="msvalidate.01" content="AE572F7C3B94BFCBC52E02E6D573306B">
<meta name="theme-color" content="#0c173d">
<link rel="icon" href="/wp-content/uploads/2023/09/cropped-Favicon-Compass-32x32.png" sizes="32x32">
<link rel="icon" href="/wp-content/uploads/2023/09/cropped-Favicon-Compass-192x192.png" sizes="192x192">
<link rel="apple-touch-icon" href="/wp-content/uploads/2023/09/cropped-Favicon-Compass-180x180.png">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Montserrat:wght@600;700;800&display=swap">
<link rel="stylesheet" href="/assets/styles.css?v={CSS_VER}">
{jsonld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>"""

def loan_menu():
    items = "".join(f'<a href="{l["href"]}">{esc(l["title"])}</a>' for l in LOANS)
    items += '<a href="/portfolio-products/">Portfolio Products (Investors)</a>'
    return items + '<a class="all" href="/loans/">View all loan options →</a>'

NO_APPLY = {"/loans/builder-advantage-program/"}   # pages with no Apply Now buttons

def header(apply=True):
    social = "".join(f'<a href="{u}" target="_blank" rel="noopener" aria-label="{n}">{ICON[{"Facebook":"fb","Instagram":"ig","LinkedIn":"li"}[n]]}</a>' for n, u in SOCIAL)
    drawer_loans = "".join(f'<a href="{l["href"]}">{esc(l["title"])}</a>' for l in LOANS)
    return f"""
<div class="topbar"><div class="wrap">
  <a href="tel:{PHONE_TEL}">{ICON['phone']} {PHONE}</a>
  <a href="mailto:{EMAIL}">{ICON['mail']} {EMAIL}</a>
  <span class="sp">Ocala, FL · NMLS# {NMLS}</span>
</div></div>
<header class="site"><div class="wrap">
  <a class="logo" href="/" aria-label="Southern Home Loans home"><img src="{LOGO}" alt="Southern Home Loans, a division of Luminate Bank" width="500" height="211"></a>
  <nav class="main" aria-label="Main">
    <div><button aria-haspopup="true">Loan Options {ICON['down']}</button><div class="mega">{loan_menu()}</div></div>
    <div><button aria-haspopup="true">Buying a Home {ICON['down']}</button><div class="mega sm">
      <a href="/mortgage-process/">The Mortgage Process</a><a href="/purchase-process/">The Purchase Process</a>
      <a href="/mortgage-terms/">Mortgage Terms</a><a href="/moving-to-marion-county-fl/">Moving to Marion County</a>
      <a href="/service-areas/ocala/">Ocala Home Loans</a><a href="/builders/">For Builders</a></div></div>
    <div><a href="/about/">About</a></div>
    <div><a href="/blog/">Blog</a></div>
    <div><a href="/contact/">Contact</a></div>
  </nav>
  <div class="hdr-cta">
    <a class="hdr-phone" href="tel:{PHONE_TEL}">{ICON['phone']} {PHONE}</a>
    {f'<a class="btn btn-teal btn-sm" href="{APPLY}" target="_blank" rel="noopener">Apply Now</a>' if apply else '<a class="btn btn-teal btn-sm" href="/contact/">Contact Us</a>'}
  </div>
  <button class="burger" aria-label="Open menu" onclick="document.getElementById('drawer').classList.add('open')"><span></span><span></span><span></span></button>
</div></header>
<div class="drawer" id="drawer" onclick="if(event.target===this)this.classList.remove('open')"><div class="panel">
  <button class="x" aria-label="Close menu" onclick="document.getElementById('drawer').classList.remove('open')">×</button>
  <a href="/" style="border:0;padding-top:4px"><img src="{LOGO}" alt="Southern Home Loans" style="height:40px;width:auto"></a>
  <div class="btns" style="margin:22px 0 6px">{f'<a class="btn btn-teal" href="{APPLY}" target="_blank" rel="noopener">Apply Now</a>' if apply else ''}<a class="btn btn-line" href="tel:{PHONE_TEL}">Call</a></div>
  <h4>Loan options</h4>{drawer_loans}<a href="/portfolio-products/">Portfolio Products (Investors)</a><a href="/loans/">All loan options</a>
  <h4>Buying a home</h4><a href="/mortgage-process/">The Mortgage Process</a><a href="/purchase-process/">The Purchase Process</a><a href="/mortgage-terms/">Mortgage Terms</a><a href="/moving-to-marion-county-fl/">Moving to Marion County</a><a href="/service-areas/ocala/">Ocala Home Loans</a><a href="/builders/">For Builders</a>
  <h4>Company</h4><a href="/about/">About</a><a href="/blog/">Blog</a><a href="/contact/">Contact</a>
</div></div>
<div class="actionbar" aria-label="Quick actions">
  <a href="tel:{PHONE_TEL}">{ICON['phone']}Call</a>
  <a class="pri" href="#quote" onclick="return goQuote()">{ICON['doc']}Free Quote</a>
  {f'<a class="sec" href="{APPLY}" target="_blank" rel="noopener">{ICON["spark"]}Apply</a>' if apply else ''}
</div>"""

def footer(apply=True):
    loans = "".join(f'<li><a href="{l["href"]}">{esc(l["title"])}</a></li>' for l in LOANS[:9])
    social = "".join(f'<a href="{u}" target="_blank" rel="noopener" aria-label="{n}">{ICON[{"Facebook":"fb","Instagram":"ig","LinkedIn":"li"}[n]]}</a>' for n, u in SOCIAL)
    year = datetime.date.today().year
    return f"""
<footer class="site"><div class="wrap">
  <div class="f-grid">
    <div>
      <a class="f-logo" href="/"><img src="{LOGO}" alt="Southern Home Loans" width="500" height="211"></a>
      <p>Local mortgage guidance from Ocala, Florida. Southern Home Loans is a division of Luminate Bank.</p>
      <div class="social">{social}</div>
    </div>
    <div><h4>Loans</h4><ul>{loans}<li><a href="/loans/">All loan options →</a></li></ul></div>
    <div><h4>Company</h4><ul>
      <li><a href="/about/">About</a></li><li><a href="/mortgage-process/">Mortgage Process</a></li><li><a href="/purchase-process/">Purchase Process</a></li>
      <li><a href="/mortgage-terms/">Mortgage Terms</a></li><li><a href="/blog/">Blog</a></li><li><a href="/contact/">Contact</a></li><li><a href="/builders/">For Builders</a></li></ul></div>
    <div><h4>Areas we serve</h4><ul>{"".join(f'<li><a href="{u}">{esc(n)}</a></li>' for n, u in AREAS)}</ul></div>
    <div><h4>Contact</h4><ul>
      <li><a href="tel:{PHONE_TEL}">{PHONE}</a></li><li><a href="mailto:{EMAIL}">{EMAIL}</a></li>
      <li>{ADDRESS[0]}<br>{ADDRESS[1]}</li>
      <li style="margin-top:8px"><b style="color:#fff">Brandon Crysler</b><br>Branch Manager · NMLS# {NMLS}</li></ul>
      {f'<a class="btn btn-teal btn-sm" style="margin-top:18px" href="{APPLY}" target="_blank" rel="noopener">Get Pre-Approved</a>' if apply else ''}</div>
  </div>
  <div class="legal">
    <img src="/wp-content/uploads/2022/05/equalhousing_bw_lg.svg" alt="Equal Housing Opportunity" width="34" height="34">
    <span>© {year} Southern Home Loans, a division of Luminate Bank</span>
    <a href="https://www.nmlsconsumeraccess.org/" target="_blank" rel="noopener">NMLS Consumer Access</a>
    <a href="/licensing/">Licensing</a><a href="/cip-disclosure/">CIP Disclosure</a><a href="/privacy-policy/">Privacy Policy</a><a href="/disclaimer/">Disclaimer</a>
  </div>
  <p class="disclaim">Equal Housing Opportunity. This is not a commitment to lend. All loans are subject to credit approval, underwriting guidelines and program availability. Rates, terms and programs are subject to change without notice. Not all applicants will qualify.</p>
</div></footer>"""

SCRIPTS = f"""
<script>
function goQuote(){{var q=document.getElementById('quote');if(q){{q.scrollIntoView({{behavior:'smooth',block:'start'}});return false}}location.href='/contact/#quote';return false}}
(function(){{
  var loaded=false;
  function hs(){{if(loaded||!document.querySelector('.hs-form-frame'))return;loaded=true;var s=document.createElement('script');s.src='https://js-{HS_REGION}.hsforms.net/forms/embed/{HS_PORTAL}.js';s.defer=true;document.body.appendChild(s)}}
  function el(){{if(!document.querySelector('.{ELFSIGHT}'))return;var s=document.createElement('script');s.src='https://static.elfsight.com/platform/platform.js';s.defer=true;document.body.appendChild(s)}}
  function track(){{
    window.dataLayer=window.dataLayer||[];window.gtag=function(){{dataLayer.push(arguments)}};gtag('js',new Date());gtag('config','{GOOGLE_ADS}');
    var g=document.createElement('script');g.async=true;g.src='https://www.googletagmanager.com/gtag/js?id={GOOGLE_ADS}';document.head.appendChild(g);
    !function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
    fbq('init','{META_PIXEL}');fbq('track','PageView');
  }}
  var go=function(){{hs();el();track();['scroll','mousemove','touchstart','keydown'].forEach(function(e){{removeEventListener(e,go)}})}};
  ['scroll','mousemove','touchstart','keydown'].forEach(function(e){{addEventListener(e,go,{{passive:true,once:true}})}});
  setTimeout(go,3500);
}})();
</script>
</body></html>"""

def quote_form(title="Get your free quote", sub="Tell us a little about your plans and a loan officer will reach out with options and rates. No obligation.", anchor=True, apply=True):
    aid = ' id="quote"' if anchor else ""
    return f"""<div class="quote-card"{aid}>
  <h2>{esc(title)}</h2><p class="sub">{esc(sub)}</p>
  <div class="hs-form-frame" data-region="{HS_REGION}" data-form-id="{HS_FORM}" data-portal-id="{HS_PORTAL}"></div>
  <p class="form-fallback">Prefer to talk? Call <a href="tel:{PHONE_TEL}">{PHONE}</a>{f' or <a href="{APPLY}" target="_blank" rel="noopener">apply online</a>' if apply else ''}.</p>
</div>"""

def loan_cards(items=None, limit=None):
    items = items or LOANS
    if limit: items = items[:limit]
    out = []
    for l in items:
        tag = f'<span class="tag">{BUILDER_RATE} ({BUILDER_APR} APR)*</span>' if "builder-advantage" in l["href"] else ""
        out.append(f"""<a class="card" href="{l['href']}"><div class="ph">{tag}<img src="{l['img']}" alt="{esc(l['title'])}" loading="lazy"></div>
<div class="bd"><h3>{esc(l['title'])}</h3><p>{esc(l['desc'])}</p><span class="more">Learn more →</span></div></a>""")
    note = f'<p class="rate-note">{BUILDER_NOTE}</p>' if any("builder-advantage" in l["href"] for l in items) else ""
    return '<div class="cards">' + "".join(out) + "</div>" + note

def post_cards(posts):
    out = []
    for p in posts:
        img = p.get("image") or HERO
        out.append(f"""<a class="card" href="{p['url']}"><div class="ph"><img src="{img}" alt="{esc(p['h1'])}" loading="lazy"></div>
<div class="bd"><div class="meta">{esc(p.get('category',''))} · {fmt_date(p.get('date'))}</div><h3>{esc(p['h1'])}</h3><p>{esc(p.get('description',''))}</p><span class="more">Read article →</span></div></a>""")
    return '<div class="cards">' + "".join(out) + "</div>"

def cta_band(title="Ready to see what you qualify for?", text="Get pre-approved online in minutes, or talk with Brandon and the Southern Home Loans team today.", apply=True):
    return f"""<section class="s tight"><div class="wrap"><div class="cta-band">
  <div><h2>{esc(title)}</h2><p>{esc(text)}</p></div>
  <div class="btns">{f'<a class="btn btn-teal" href="{APPLY}" target="_blank" rel="noopener">Get Pre-Approved</a>' if apply else ''}<a class="btn btn-ghost" href="tel:{PHONE_TEL}">{ICON['phone']} {PHONE}</a></div>
</div></div></section>"""

def reviews():
    return f"""<section class="s alt"><div class="wrap"><div class="s-head"><span class="eyebrow">Reviews</span><h2>What our borrowers say</h2></div>
<div class="reviews"><div class="{ELFSIGHT}" data-elfsight-app-lazy></div></div>
<div class="btns review-links"><a class="btn btn-navy" href="{GOOGLE_REVIEWS}" target="_blank" rel="noopener">Read our Google reviews</a><a class="btn btn-line" href="{GOOGLE_WRITE_REVIEW}" target="_blank" rel="noopener">Leave us a review</a></div></div></section>"""

def sidebar(current="", apply=True):
    links = "".join(f'<a href="{l["href"]}">{esc(l["title"])}</a>' for l in LOANS if l["href"] != current)
    return f"""<aside class="side">
  <div class="side-card">
    <div class="lo"><img src="{BRANDON}" alt="Brandon Crysler" width="64" height="64"><div><b>Brandon Crysler</b><span>Branch Manager · NMLS# {NMLS}</span></div></div>
    {'<h3 style="margin-top:20px">Get pre-approved today</h3>' if apply else '<h3 style="margin-top:20px">Contact today to learn more.</h3>'}
    {f"""<p style="margin:0">Apply online in minutes or get a free, no-obligation quote.</p>
    <a class="btn btn-teal" href="{APPLY}" target="_blank" rel="noopener">Apply Now</a>""" if apply else ''}
    <a class="btn btn-ghost" href="#quote" onclick="return goQuote()">Free Quote</a>
    <a class="ph-line" href="tel:{PHONE_TEL}">{ICON['phone']} {PHONE}</a>
  </div>
  <div class="side-links"><h4>Loan options</h4>{links}</div>
</aside>"""

def page_hero(p, eyebrow=None, lead=None, image=None, buttons=True, crumbs=None, extra="", apply=True):
    h = p.get("hero", {})
    eyebrow = eyebrow if eyebrow is not None else titlecase(h.get("eyebrow", ""))
    lead = lead if lead is not None else h.get("lead", "")
    image = image if image is not None else h.get("image", "")
    img_html = f'<div class="hero-img"><img src="{image}" alt="{esc(strip(p.get('h1','')))}" fetchpriority="high"></div>' if image else ""
    apply_btn = f'<a class="btn btn-teal" href="{APPLY}" target="_blank" rel="noopener">Apply Now</a>' if apply else ''
    btns = f"""<div class="btns" style="margin-top:26px">{apply_btn}
<a class="btn btn-ghost" href="#quote" onclick="return goQuote()">Get a Free Quote</a></div>""" if buttons else ""
    cr = ""
    if crumbs:
        cr = '<div class="crumbs">' + " / ".join(f'<a href="{u}">{esc(t)}</a>' if u else esc(t) for t, u in crumbs) + "</div>"
    return f"""<section class="hero page-hero{'' if image else ' noimg'} on-dark" style="--hero-img:url('{image or HERO}')"><div class="wrap">
  <div>{cr}{f'<span class="eyebrow">{esc(eyebrow)}</span>' if eyebrow else ''}<h1>{esc(titlecase(p['h1']))}</h1>{f'<p class="lead">{esc(lead)}</p>' if lead else ''}{extra}{btns}</div>
  {img_html}
</div></section>"""

def is_loan_grid(sec):
    return sec.count('href="/loans/') >= 5 and "<img" in sec   # WordPress loan-card grid, not written copy with links

def is_form_stub(sec):
    t = strip(sec)
    return len(t) < 400 and re.search(r"fill out the form|enter your information", t, re.I)

def render_sections(secs):
    blocks, grid = [], False
    for s in secs:
        if is_loan_grid(s):
            grid = True; continue
        if is_form_stub(s):
            continue
        s = re.sub(r">\s*Explore\s*<", "><", s)
        # "fill out the form below" prompts: the page already ends with a quote form
        s = re.sub(r"<h[2-4]>[^<]*</h[2-4]>\s*<p>[^<]*(?:fill out the form|enter your information)[^<]*</p>", "", s, flags=re.I)
        s = re.sub(r"<p>[^<]*(?:fill out the form below|enter your information below)[^<]*</p>", "", s, flags=re.I)
        s = re.sub(r"<h[2-4]>(?:(?!</h[2-4]>).)*</h[2-4]>\s*(?:<p>)?[^<]*(?:fill out the form|enter your information)[^<]*(?:<br/>|</p>)?", "", s, flags=re.I | re.S)
        if not strip(s):
            continue
        blocks.append(f'<div class="block">{s}</div>')
    return "".join(blocks), grid

OLD_LINKS = {"/loans/hometown-heroes/": "/loans/down-payment-assistance/", "/loans/hometown-heros/": "/loans/down-payment-assistance/",
             "/loans/mobile-home-financing/": "/loans/manufactured-home-financing/", "/apply-online/": APPLY}

def write(url, doc):
    path = os.path.join(OUT, url.strip("/"), "index.html") if url != "/" else os.path.join(OUT, "index.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc = doc.replace("%C2%A0\"", "\"")   # stray non-breaking spaces at the end of links
    for old, new in OLD_LINKS.items():   # point old WordPress links straight at their redirect targets
        doc = doc.replace(f'href="{old}"', f'href="{new}"')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)

def doc(p, main, **kw):
    return head(p, **kw) + header(p.get("url") not in NO_APPLY) + f'<main id="main">{main}</main>' + footer(p.get("url") not in NO_APPLY) + SCRIPTS

# ---------------------------------------------------------------- page types
def render_home(p):
    hero = f"""<section class="hero hero-home on-dark" style="--hero-img:url('{HERO}')"><div class="wrap">
  <div>
    <span class="eyebrow">Southern Home Loans · Ocala, Florida</span>
    <h1>Florida home loans, made simple.</h1>
    <p class="lead">Local guidance from Ocala, lending across Florida. See why Southern Home Loans lends in 50 states and still feels like your neighbor.</p>
    <ul class="checks">
      <li>FHA, VA, USDA, conventional, jumbo, construction and land loans</li>
      <li>Down payment assistance, including Florida Hometown Heroes and SHIP</li>
      <li>Bank-statement and investor cash-flow loans for the self-employed</li>
    </ul>
    <div class="btns"><a class="btn btn-teal" href="{APPLY}" target="_blank" rel="noopener">Get Pre-Approved</a><a class="btn btn-ghost" href="tel:{PHONE_TEL}">{ICON['phone']} Call {PHONE}</a></div>
    <div class="trust" style="margin-top:26px"><span><b>Since 2000</b> serving Florida families</span><span><b>NMLS# {NMLS}</b></span><span><b>Equal Housing</b> Opportunity</span></div>
  </div>
  {quote_form()}
</div></section>"""
    strip_ = f"""<section class="strip"><div class="wrap">
  <div class="stat"><div class="badge">{ICON['clock']}</div><div><div class="n">Minutes</div><div class="t">to apply online and get pre-approved</div></div></div>
  <div class="stat"><div class="badge">{ICON['home']}</div><div><div class="n">15+</div><div class="t">loan programs for buyers, builders and investors</div></div></div>
  <div class="stat"><div class="badge">{ICON['pin']}</div><div><div class="n">Ocala</div><div class="t">local team serving Marion County and all of Florida</div></div></div>
  <div class="stat"><div class="badge">{ICON['shield']}</div><div><div class="n">Since 2000</div><div class="t">helping families finance their homes</div></div></div>
</div></section>"""
    loans = f"""<section class="s"><div class="wrap">
  <div class="s-head"><span class="eyebrow">Loan options</span><h2>Find the right loan for your move</h2><p>Whether it's your first home, a new build, land, or an investment property, we'll match you with the program that fits.</p></div>
  {loan_cards(limit=9)}
  <div class="center" style="margin-top:34px"><a class="btn btn-navy" href="/loans/">See all loan options</a></div>
</div></section>"""
    steps = f"""<section class="s alt"><div class="wrap">
  <div class="s-head"><span class="eyebrow">How it works</span><h2>From pre-approval to keys in hand</h2><p>We've streamlined the process so you always know what's next.</p></div>
  <div class="steps">
    <div class="step"><h3>Get pre-approved</h3><p>Apply online in minutes or call us. We'll review your options and give you a clear pre-approval to shop with.</p></div>
    <div class="step"><h3>Choose your loan</h3><p>We walk you through the programs you qualify for, side by side, so you can pick the payment and terms that fit.</p></div>
    <div class="step"><h3>Close with confidence</h3><p>We stay in touch from contract to closing and coordinate with your agent, builder and title company.</p></div>
  </div>
  <div class="center" style="margin-top:34px"><a class="btn btn-line" href="/mortgage-process/">See the full mortgage process</a></div>
</div></section>"""
    investors = f"""<section class="s dark on-dark"><div class="wrap split">
  <div><span class="eyebrow">Self-employed &amp; investors</span><h2>Options for entrepreneurs and investors</h2>
    <p>Tired of endless hurdles and strict income verification? Our programs for self-employed borrowers and investors offer flexible bank statement requirements, generous loan amounts and attractive terms.</p>
    <ul class="checks"><li>3-month bank statement</li><li>12-month bank statement</li><li>Investor cash flow (DSCR)</li><li>ATR-in-full</li></ul>
    <a class="btn btn-teal" href="/portfolio-products/">Explore portfolio products</a></div>
  <div><img src="/wp-content/uploads/2023/06/Portfolio-Products1-636x1024.jpg" alt="Self-employed home buyer reviewing bank statement loan options" loading="lazy" style="max-height:520px;width:auto;margin:0 auto"></div>
</div></section>"""
    blog = f"""<section class="s"><div class="wrap">
  <div class="s-head"><span class="eyebrow">From the blog</span><h2>Home buying tips and market updates</h2></div>
  {post_cards(POSTS[:3])}
  <div class="center" style="margin-top:34px"><a class="btn btn-line" href="/blog/">Read more articles</a></div>
</div></section>"""
    return doc(p, hero + strip_ + loans + steps + investors + reviews() + blog + cta_band())

def render_content(p, crumbs=None, side_current="", show_grid_title="Explore loan options"):
    body, grid = render_sections(p.get("sections", []))
    grid_html = f"""<section class="s alt"><div class="wrap"><div class="s-head"><h2>{esc(show_grid_title)}</h2></div>{loan_cards()}</div></section>""" if grid else ""
    ap = p.get("url") not in NO_APPLY
    band = cta_band() if ap else cta_band("Ready to run the numbers?", "Talk with Brandon and the Southern Home Loans team today.", apply=False)
    faq = ""
    if p.get("faqs"):
        faq = '<div class="block faq"><h2>Frequently asked questions</h2>' + "".join(
            f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in p["faqs"]) + "</div>"
    main = page_hero(p, crumbs=crumbs, apply=ap) + f"""<section class="s"><div class="wrap content-grid">
  <div class="prose content">{body}{faq}<div style="margin-top:44px">{quote_form(apply=ap)}</div></div>
  {sidebar(side_current, apply=ap)}
</div></section>""" + grid_html + reviews() + band
    return doc(p, main)

def render_post(p):
    cat_url = next((u for u, n in CATS.items() if n == p.get("category")), "/blog/")
    meta = f'<div class="post-meta"><span>{esc(p.get("category",""))}</span><span>{fmt_date(p.get("date"))}</span><span>By Brandon Crysler</span></div>'
    hero = f"""<section class="hero page-hero noimg on-dark" style="--hero-img:url('{p.get('image') or HERO}')"><div class="wrap" style="padding-bottom:90px">
  <div><div class="crumbs"><a href="/">Home</a> / <a href="/blog/">Blog</a> / <a href="{cat_url}">{esc(p.get('category',''))}</a></div>
  <h1>{esc(p['h1'])}</h1>{meta}</div></div></section>"""
    feat = f'<div class="post-feature"><img src="{p["image"]}" alt="{esc(p["h1"])}" fetchpriority="high"></div>' if p.get("image") else ""
    related = [x for x in POSTS if x["url"] != p["url"] and x.get("category") == p.get("category")][:3] or [x for x in POSTS if x["url"] != p["url"]][:3]
    main = hero + feat + f"""<section class="s" style="padding-top:56px"><div class="wrap content-grid">
  <article class="prose content">{p['body']}
    <div class="author"><img src="{BRANDON}" alt="Brandon Crysler" width="76" height="76"><div><b>Brandon Crysler</b><br>Branch Manager at Southern Home Loans · NMLS# {NMLS}. Questions about this article? <a href="tel:{PHONE_TEL}">Call {PHONE}</a>.</div></div>
    <div style="margin-top:44px">{quote_form("Talk to a loan officer")}</div>
  </article>
  {sidebar()}
</div></section>
<section class="s alt"><div class="wrap"><div class="s-head"><h2>Keep reading</h2></div>{post_cards(related)}</div></section>""" + cta_band()
    return doc(p, main)

def blog_index(p, posts, active_url="/blog/", heading="The HomeTown Blog"):
    chips = f'<a class="chip{" on" if active_url=="/blog/" else ""}" href="/blog/">All</a>' + "".join(
        f'<a class="chip{" on" if u==active_url else ""}" href="{u}">{esc(n)}</a>' for u, n in CATS.items() if any(x.get("category") == n for x in POSTS))
    hero = f"""<section class="hero page-hero noimg on-dark" style="--hero-img:url('{HERO}')"><div class="wrap">
  <div><span class="eyebrow">Blog</span><h1>{esc(heading)}</h1><p class="lead">Home buying tips, loan program guides and Central Florida market updates from the Southern Home Loans team.</p></div></div></section>"""
    main = hero + f'<section class="s"><div class="wrap"><div class="chips">{chips}</div>{post_cards(posts)}</div></section>' + cta_band()
    return doc(p, main)

def render_loans(p):
    main = page_hero(p, eyebrow="Loan options", lead="Compare the programs we offer for buyers, builders and investors, then get a free quote on the one that fits.", image="") + \
        f'<section class="s"><div class="wrap">{loan_cards()}</div></section>' + \
        f"""<section class="s alt"><div class="wrap split"><div><span class="eyebrow">Investors &amp; self-employed</span><h2>Portfolio products</h2>
<p>Bank-statement, investor cash-flow and ATR-in-full programs with simplified qualifications.</p><a class="btn btn-navy" href="/portfolio-products/">Explore portfolio products</a></div>
<div>{quote_form()}</div></div></section>""" + reviews() + cta_band()
    return doc(p, main)

def render_contact(p):
    main = f"""<section class="hero page-hero noimg on-dark" style="--hero-img:url('{HERO}')"><div class="wrap"><div>
  <span class="eyebrow">Contact</span><h1>Let's talk about your home loan</h1><p class="lead">We always respond quickly. Our friendly team is here to help.</p></div></div></section>
<section class="s"><div class="wrap contact-grid">
  <div><h2>Reach us directly</h2><p>Call, email or stop by our Ocala office. Prefer to get started on your own? Apply online any time.</p>
    <ul class="info-list">
      <li><span class="badge">{ICON['phone']}</span><div><b>Phone</b><a href="tel:{PHONE_TEL}">{PHONE}</a></div></li>
      <li><span class="badge">{ICON['mail']}</span><div><b>Email</b><a href="mailto:{EMAIL}">{EMAIL}</a></div></li>
      <li><span class="badge">{ICON['pin']}</span><div><b>Office</b><a href="https://maps.google.com/?q=2050+E+Silver+Springs+Blvd,+Ocala,+FL+34470" target="_blank" rel="noopener">{ADDRESS[0]}<br>{ADDRESS[1]}</a></div></li>
    </ul>
    <div class="side-card" style="margin-top:10px"><div class="lo"><img src="{BRANDON}" alt="Brandon Crysler" width="64" height="64"><div><b>Brandon Crysler</b><span>Branch Manager · NMLS# {NMLS}</span></div></div>
    <a class="btn btn-teal" style="margin-top:20px" href="{APPLY}" target="_blank" rel="noopener">Apply Now</a></div>
  </div>
  {quote_form("Send us a message")}
</div></section>""" + reviews()
    return doc(p, main)

# ---------------------------------------------------------------- build
def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "assets"))
    shutil.copy(os.path.join(ROOT, "src", "styles.css"), os.path.join(OUT, "assets", "styles.css"))
    for p in PAGES:
        k = p["kind"]
        if k == "home":
            d = render_home(p)
        elif k == "post":
            d = render_post(p)
        elif k == "blog":
            d = blog_index(p, POSTS)
        elif k == "category":
            name = CATS[p["url"]]
            d = blog_index(p, [x for x in POSTS if x.get("category") == name], p["url"], name)
        elif k == "loans":
            d = render_loans(p)
        elif k == "contact":
            d = render_contact(p)
        elif k == "loan":
            d = render_content(p, crumbs=[("Home", "/"), ("Loan options", "/loans/"), (titlecase(p["hero"].get("eyebrow") or p["h1"]), "")], side_current=p["url"])
        elif k == "area":
            d = render_content(p, crumbs=[("Home", "/"), ("Service areas", ""), (titlecase(p["hero"].get("eyebrow") or p["h1"]), "")])
        else:
            d = render_content(p, crumbs=[("Home", "/"), (titlecase(p["h1"]), "")])
        write(p["url"], d)
    # 404
    nf = {"url": "/404/", "title": "Page not found | Southern Home Loans", "description": "", "canonical": DOMAIN + "/", "robots": "noindex", "h1": "Page not found"}
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "404.html"), "w").write(doc(nf, f"""<section class="s"><div class="wrap center"><span class="eyebrow">404</span><h1>We couldn't find that page</h1>
<p class="lead">It may have moved. Try one of these instead.</p><div class="btns" style="justify-content:center;margin:24px 0 40px"><a class="btn btn-navy" href="/">Home</a><a class="btn btn-line" href="/loans/">Loan options</a><a class="btn btn-line" href="/blog/">Blog</a></div>{loan_cards(limit=3)}</div></section>"""))
    # uploads actually used + sitemaps/robots
    used = set()
    for f in glob.glob(os.path.join(OUT, "**", "*.html"), recursive=True):
        used |= set(re.findall(r"/wp-content/uploads/[^\"'\s)?,]+", open(f).read()))
    used |= {LOGO, BRANDON, HERO}
    used |= {f"/wp-content/uploads/2023/09/cropped-Favicon-Compass-{s}.png" for s in ("32x32", "192x192", "180x180")}
    missing = 0
    for u in used:
        src = os.path.join(UPLOADS_SRC, u.replace("/wp-content/uploads/", "", 1))
        dst = os.path.join(OUT, u.lstrip("/"))
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(src, dst)
        else:
            missing += 1; print("  missing image", u)
    optimize_images(used)
    urls = ["/"] + [p["url"] for p in PAGES if p["url"] != "/" and "noindex" not in p.get("robots", "")]
    today = datetime.date.today().isoformat()
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(
        f"<url><loc>{DOMAIN}{u}</loc><lastmod>{BY_URL.get(u,{}).get('modified') or today}</lastmod></url>\n" for u in urls) + "</urlset>\n"
    open(os.path.join(OUT, "sitemap.xml"), "w").write(sm)
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
    shutil.copy(os.path.join(UPLOADS_SRC, "2023/09/cropped-Favicon-Compass-32x32.png"), os.path.join(OUT, "favicon.ico"))
    print(f"built {len(PAGES)} pages, {len(used)} images ({missing} missing)")

def optimize_images(used, max_w=1600, max_bytes=300_000):
    """Make web-sized copies of heavy photos and point <img src> / backgrounds at them.
    Originals stay in place so social-share (og:image) links keep working."""
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow not installed; skipping image optimization"); return
    mapping = {}
    for u in used:
        path = os.path.join(OUT, u.lstrip("/"))
        if not os.path.exists(path) or not re.search(r"\.(jpe?g|png)$", u, re.I):
            continue
        if os.path.getsize(path) <= max_bytes:
            continue
        im = Image.open(path)
        if im.mode in ("RGBA", "LA", "P") and u.lower().endswith(".png"):
            if im.mode == "P": im = im.convert("RGBA")
            if im.getextrema()[-1][0] < 255:   # has real transparency: leave it
                continue
        im = im.convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        new_u = re.sub(r"\.(jpe?g|png)$", "-web.jpg", u, flags=re.I)
        im.save(os.path.join(OUT, new_u.lstrip("/")), "JPEG", quality=80, optimize=True, progressive=True)
        mapping[u] = new_u
    if not mapping:
        return
    pat = re.compile(r'(src="|url\(\')(' + "|".join(re.escape(k) for k in mapping) + r')(["\'])')
    for f in glob.glob(os.path.join(OUT, "**", "*.html"), recursive=True):
        t = open(f, encoding="utf-8").read()
        t2 = pat.sub(lambda m: m.group(1) + mapping[m.group(2)] + m.group(3), t)
        if t2 != t:
            open(f, "w", encoding="utf-8").write(t2)
    print(f"  optimized {len(mapping)} heavy images")

if __name__ == "__main__":
    build()
