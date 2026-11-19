---
description: SEO and GEO (AI-crawler) rules for PHP e-commerce projects
alwaysApply: true
---

## Meta tags

- `<title>` and `<meta name="description">` are never hardcoded per
  View — every public page calls `seoTitle($entity)` /
  `seoDescription($entity)` (`src/Core/Seo.php`)
- Both functions follow the same priority: `seo_title`/
  `seo_description` column if filled (see `database.md` —
  `products`, `categories`, `content_pages`) → template fallback if
  empty. Never return an empty string — the fallback branch is not
  optional
- Template fallback pulls only from data already on the entity (name,
  category, shop name/city from config) — never invent copy the
  entity doesn't have
- One `<h1>` per page, matching the entity's `name`/`title` column —
  don't write a second, differently-worded `<h1>` for style reasons
- `<h2>`/`<h3>` follow content structure, not font size — don't pick
  a heading level to get a particular visual weight; style that with
  CSS instead

## Structured data (schema.org)

- Every product page emits `Product` JSON-LD via
  `renderProductSchema($product)` (`src/Core/Seo.php`) — name,
  `offers.price`, `offers.availability` are required fields, not
  optional
- The price and availability inside the schema block are read from
  the **same** variable already used to render the visible price/
  stock text on the page — never compute them twice. A mismatch
  between schema and visible text is worse than no schema at all
  (`dod-global.md`, SEO section)
- Category listing pages emit `BreadcrumbList` — build it from the
  same `parent_id` chain used for the visible breadcrumb, one source,
  two renderings

## URLs & routing

- Every public entity resolves through its `slug` column, never a
  bare numeric id in the URL (`/catalog/divany`, not
  `/product.php?id=42`)
- Filtered/sorted category views (`?sort=price&color=red`) render
  `<link rel="canonical">` pointing at the bare category URL — build
  it by stripping query params in the Controller, don't hardcode it
  per View
- A slug change (product renamed, category restructured) must not
  break the old URL silently — redirect old slug → new via a
  `redirects` lookup (add the table only when the project's first
  slug change actually happens, don't pre-build it speculatively)

## Sitemap & robots

- `/sitemap.xml` is a real route (`config/routes.php`) backed by a
  Controller that queries `products`/`categories`/`content_pages` —
  never a static file. If it doesn't reflect what's actually in the
  DB right now, it's actively misleading, not just stale
- Cache the generated sitemap (file or `storage/cache/`) and
  regenerate on catalog change or on a schedule — don't rebuild it
  from a full table scan on every crawler hit
- `public/robots.txt` is a static file — allow catalog paths, disallow
  `/account/`, `/cart/`, `/checkout/`, `/admin/`
- Every URL listed in the sitemap must return 200 — a sitemap entry
  pointing at a deactivated (`is_active = 0`) product is a bug, not a
  detail; exclude inactive products from the sitemap query

## Content rendering (GEO)

- Product/category/content page text renders server-side, in the
  initial HTML response — never behind a JS fetch that populates the
  DOM after load. Most AI crawlers, unlike Googlebot, don't execute
  JS at all; if the description only exists after a `fetch()`, it
  doesn't exist for them
- Product specs (material, size, weight — anything structured) render
  as a `<dl>`/table of distinct property-value pairs, not folded into
  the prose `description` — a fact is easier to lift out of a table
  row than out of a paragraph. Store them in `product_attributes` if
  the project has any (see `database.md`), not appended to
  `description` as text
- If a fact appears in two places on the same page (schema.org value,
  visible price, spec table) it must come from one variable, rendered
  twice — see Structured data above; the same rule, restated because
  it's the most common place this breaks

## Images

- Every `<img>` has a non-empty `alt` describing the image content —
  product photos get the product name plus distinguishing detail if
  known (color/variant), not the filename and not an empty string
- Purely decorative images (icons paired with visible text, dividers)
  get `alt=""` explicitly — an empty attribute is a deliberate choice,
  a missing one is not
