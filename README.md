# southernhl.com – static copy on Vercel

This repository holds a static copy of the southernhl.com WordPress site.

- `site/` – the published website (generated; do not hand-edit unless you mean to diverge from WordPress)
- `tools/mirror.py` – copies every page in the WordPress sitemaps plus its CSS, JS, images and fonts
- `.github/workflows/mirror.yml` – runs the copy on GitHub and commits the result to `site/`

To refresh the copy after editing WordPress: GitHub → Actions → "Copy WordPress site" → Run workflow.
After southernhl.com points at Vercel, run it with the WordPress server's other address as `origin`.

Forms: HubSpot embedded forms work as-is. The reverse-mortgage Gravity Form is replaced by a script
that submits to HubSpot form f7c9da26 (portal 242109586).
