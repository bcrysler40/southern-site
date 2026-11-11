#!/usr/bin/env python3
"""Make a static copy of southernhl.com (WordPress) for hosting on Vercel.

Run by .github/workflows/mirror.yml. Fetches every URL in the Rank Math
sitemaps, downloads every same-site asset they reference (CSS, JS, images,
fonts, lazy-loaded data-src images, CSS url() files), rewrites links so the
copy works on any domain, swaps the one Gravity Form for a HubSpot submission,
and writes everything to ./site.

Usage: python3 tools/mirror.py [ORIGIN]
ORIGIN defaults to https://southernhl.com. After the domain moves to Vercel,
point it at the WordPress server's other address (e.g. the GridPane staging URL).
"""
import os, re, sys, json, time, hashlib, urllib.parse, urllib.request, html

ORIGIN = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ORIGIN", "https://southernhl.com")).rstrip("/")
CANON = "https://southernhl.com"          # the public domain search engines know
OUT = os.path.abspath("site")
UA = "Mozilla/5.0 (compatible; SHL-static-mirror/1.0)"
HOSTS = {urllib.parse.urlparse(ORIGIN).netloc, "southernhl.com", "www.southernhl.com"}

HUBSPOT_PORTAL = "242109586"
HUBSPOT_FORM = "f7c9da26-9530-4f31-92b1-4db11e576281"

import ssl
SSL_CTX = ssl._create_unverified_context() if os.environ.get("MIRROR_INSECURE") else None

def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read(), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (404, 410, 403):
                return e.code, "", b"", url
            time.sleep(2 * (i + 1))
        except Exception:
            time.sleep(2 * (i + 1))
    return 0, "", b"", url

def to_origin(u):
    p = urllib.parse.urlparse(u)
    if p.netloc in HOSTS:
        return ORIGIN + p.path + (("?" + p.query) if p.query else "")
    return u

def local_path(u, is_page=False):
    p = urllib.parse.urlparse(u)
    path = urllib.parse.unquote(p.path)
    if is_page or path.endswith("/") or path == "":
        return os.path.join(OUT, path.lstrip("/"), "index.html")
    if p.query and re.search(r"\.(css|js)$", path) is None and "." not in os.path.basename(path):
        path += "-" + hashlib.md5(p.query.encode()).hexdigest()[:8]
    return os.path.join(OUT, path.lstrip("/"))

def save(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        with open(path, "wb") as f:
            f.write(data)
    except (IsADirectoryError, NotADirectoryError, FileExistsError) as e:
        print("  could not save", path, e, flush=True)

# ---------- 1. page list from sitemaps ----------
pages = []
st, _, body, _ = fetch(ORIGIN + "/sitemap_index.xml")
sitemaps = re.findall(r"<loc>([^<]+)</loc>", body.decode("utf-8", "ignore"))
for sm in sitemaps:
    st, _, b, _ = fetch(to_origin(sm))
    save(local_path(sm), b.replace(ORIGIN.encode(), CANON.encode()))
    for loc in re.findall(r"<loc>([^<]+)</loc>", b.decode("utf-8", "ignore")):
        if not re.search(r"\.(jpe?g|png|webp|gif)$", loc, re.I):
            pages.append(loc)
save(local_path(ORIGIN + "/sitemap_index.xml"), body.replace(ORIGIN.encode(), CANON.encode()))
for extra in ["/", "/blog/"]:
    if CANON + extra not in pages:
        pages.append(CANON + extra)
pages = list(dict.fromkeys(pages))
print(f"{len(pages)} pages", flush=True)

# ---------- 2. fetch pages, collect assets ----------
ASSET_RE = re.compile(r"""(?:https?:)?(?:\\?/\\?/)(?:www\.)?southernhl\.com((?:\\?/)(?:wp-content|wp-includes)[^"'\s)<>,]+)""")
REL_ASSET_RE = re.compile(r"""(?<=["'(\s,])(/(?:wp-content|wp-includes)/[^"'\s)<>,]+)""")
assets = set()
page_html = {}
for i, u in enumerate(pages):
    st, ct, b, final = fetch(to_origin(u))
    if st != 200:
        print("  skip", st, u, flush=True)
        continue
    t = b.decode("utf-8", "ignore")
    page_html[u] = t
    for m in ASSET_RE.findall(t):
        assets.add(m.replace("\\/", "/"))
    for m in REL_ASSET_RE.findall(t):
        assets.add(m)
print(f"{len(page_html)} pages fetched, {len(assets)} asset refs", flush=True)

# ---------- 3. fetch assets (and CSS dependencies) ----------
def clean(a):
    a = html.unescape(a).split("#")[0]
    return a.rstrip("\\")

done, queue = set(), [clean(a) for a in assets]
while queue:
    a = queue.pop()
    key = a.split("?")[0] if not re.search(r"\.(css|js)$", a.split("?")[0]) else a.split("?")[0]
    if key in done:
        continue
    done.add(key)
    if "." not in os.path.basename(a.split("?")[0]):
        continue  # a folder reference (e.g. a plugin base URL), not a file
    st, ct, b, _ = fetch(ORIGIN + a)
    if st != 200:
        continue
    lp = local_path(CANON + a.split("?")[0])
    if lp.endswith(".css") or "text/css" in ct:
        css = b.decode("utf-8", "ignore")
        base = a.split("?")[0].rsplit("/", 1)[0] + "/"
        for ref in re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", css):
            if ref.startswith("data:") or ref.startswith("#"):
                continue
            full = urllib.parse.urljoin(ORIGIN + base, ref)
            p = urllib.parse.urlparse(full)
            if p.netloc in HOSTS:
                queue.append(p.path)
        css = re.sub(r"https?://(?:www\.)?southernhl\.com/", "/", css)
        if ORIGIN not in (CANON,):
            css = css.replace(ORIGIN + "/", "/")
        b = css.encode()
    save(lp, b)
print(f"{len(done)} assets saved", flush=True)

# ---------- 4. rewrite + save pages ----------
KEEP_ABS = re.compile(
    r"""(<link[^>]+rel=["'](?:canonical|alternate|shortlink)["'][^>]*>|<meta[^>]+(?:property|name)=["'](?:og:url|og:image|og:image:secure_url|twitter:image)["'][^>]*>|<script[^>]+application/ld\+json[^>]*>.*?</script>)""",
    re.S | re.I)

RM_FORM_JS = """
<script>
/* Static copy: Gravity Forms has no server here, so this form posts to HubSpot instead. */
(function(){
  var f=document.getElementById('gform_5'); if(!f) return;
  f.addEventListener('submit',function(e){
    e.preventDefault(); e.stopImmediatePropagation();
    var v=function(n){var el=f.querySelector('[name="'+n+'"]');return el?el.value.trim():'';};
    if(!v('input_1.3')||!v('input_1.6')||!v('input_2')){alert('Please enter your name and email.');return;}
    if(v('input_2_2')&&v('input_2_2')!==v('input_2')){alert('Email addresses do not match.');return;}
    var msg='Reverse mortgage inquiry (southernhl.com)\\nAge: '+v('input_8')+'\\nAmount still owed: '+v('input_6')+'\\nEstimated home value: '+v('input_7')+'\\nComments: '+v('input_3');
    var fields=[['firstname',v('input_1.3')],['lastname',v('input_1.6')],['email',v('input_2')],
      ['address',(v('input_4.1')+' '+v('input_4.2')).trim()],['city',v('input_4.3')],['state',v('input_4.4')],['zip',v('input_4.5')],['message',msg]]
      .filter(function(x){return x[1];}).map(function(x){return {objectTypeId:'0-1',name:x[0],value:x[1]};});
    var btn=f.querySelector('[type=submit],button'); if(btn){btn.disabled=true;}
    fetch('https://api.hsforms.com/submissions/v3/integration/submit/__PORTAL__/__FORM__',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({fields:fields,context:{pageUri:location.href,pageName:document.title}})})
    .then(function(r){if(!r.ok) throw 0; f.outerHTML='<div class="gform_confirmation_message" style="padding:20px;font-size:18px">Thank you! We received your information and will be in touch shortly.</div>';})
    .catch(function(){ if(btn){btn.disabled=false;} alert('Sorry, that did not go through. Please call 352-622-1521.'); });
  },true);
})();
</script>
""".replace("__PORTAL__", HUBSPOT_PORTAL).replace("__FORM__", HUBSPOT_FORM)

def rewrite(t):
    keep = {}
    def stash(m):
        k = f"@@KEEP{len(keep)}@@"
        keep[k] = m.group(0).replace(ORIGIN, CANON)
        return k
    # feeds and oEmbed endpoints do not exist on a static host
    t = re.sub(r'<link[^>]+(?:application/rss\+xml|application/atom\+xml|oembed)[^>]*>\s*', "", t)
    t = KEEP_ABS.sub(stash, t)
    for host in sorted({ORIGIN, CANON, "https://www.southernhl.com", "http://southernhl.com", "http://www.southernhl.com"}, key=len, reverse=True):
        t = t.replace(host + "/", "/").replace(host.replace("/", "\\/") + "\\/", "\\/")
        t = re.sub(re.escape(host) + r'(?=["\'])', "/", t)
    t = re.sub(r'(?<=["\'])//(?:www\.)?southernhl\.com/', "/", t)
    # drop WordPress-only endpoints that do not exist on a static host
    t = re.sub(r'<link[^>]+rel=["\'](?:EditURI|wlwmanifest|pingback)["\'][^>]*>\s*', "", t)
    t = re.sub(r'<link[^>]+href=["\']/wp-json/[^>]*>\s*', "", t)
    t = re.sub(r'<link[^>]+href=["\']/xmlrpc\.php[^>]*>\s*', "", t)
    for k, v in keep.items():
        t = t.replace(k, v)
    if 'id="gform_5"' in t or "id='gform_5'" in t:
        t = t.replace("</body>", RM_FORM_JS + "</body>")
    return t

for u, t in page_html.items():
    save(local_path(CANON + urllib.parse.urlparse(u).path, is_page=True), rewrite(t).encode())

# ---------- 5. extras ----------
for p in ["/robots.txt", "/favicon.ico"]:
    st, ct, b, _ = fetch(ORIGIN + p)
    if st == 200:
        save(os.path.join(OUT, p.lstrip("/")), b.replace(ORIGIN.encode(), CANON.encode()))
st, ct, b, _ = fetch(ORIGIN + "/this-page-does-not-exist-404-check/")
if b:
    save(os.path.join(OUT, "404.html"), rewrite(b.decode("utf-8", "ignore")).encode())

json.dump({"origin": ORIGIN, "pages": len(page_html), "assets": len(done),
           "generated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())},
          open(os.path.join(OUT, "mirror-info.json"), "w"), indent=1)
print("done", flush=True)
