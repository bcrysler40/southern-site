# southernhl.com (Vercel)

The Southern Home Loans website, redesigned and hosted on Vercel. It no longer copies from WordPress.

- `content/pages.json` – the text, SEO tags and structured data for every page (taken from the WordPress site in Nov 2026)
- `content/loans.json` – loan program cards (title, link, description, image)
- `src/styles.css` – the look (navy #0C173D / turquoise #17C7C4)
- `tools/build_site.py` – builds every page into `site/` (header, footer, homepage and page layouts live here)
- `uploads/` – images from WordPress; only the ones used get published
- `site/` – the published website (generated – don't hand-edit)

Build: `pip install pillow && python3 tools/build_site.py`, then commit `site/`.

Forms use HubSpot (portal 242109586, form f7c9da26). Reviews use the Elfsight widget. Tracking: Google Ads AW-957845406 and Meta Pixel 1267196966680196.
Homes for Heroes content was removed. `tools/wordpress-copy/` holds the old WordPress copy scripts for reference.
