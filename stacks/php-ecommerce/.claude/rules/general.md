---
description: PHP e-commerce project rules (Bootstrap grid only, no CSS Grid, no jQuery/Tailwind)
alwaysApply: true
---

## Universal

- One file = one responsibility
- Always handle errors explicitly (try/catch, fallback UI)
- No magic numbers — use named constants
- Prefer simple over clever — if it needs a comment to understand, rewrite it
- Never hardcode secrets — always use `.env`
- Before writing code — make sure you understand the task fully
- If task is unclear — ask ONE question before coding
- Surface assumptions out loud even when not fully blocked; if a task
  has more than one reasonable interpretation, show the options — don't
  silently pick one
- If a simpler approach exists than the one requested, say so before
  writing code — don't just build the more complex version
- When editing existing code, match its existing style even if you'd
  do it differently; remove only the imports/variables that YOUR
  change made unused, don't clean up pre-existing dead code nearby —
  mention it instead
- Always use Context7 to fetch up-to-date documentation before writing code
  that uses any library or external API (Bootstrap, Chart.js, payment
  gateways, SMS/email providers, etc.)

## PHP

- PSR-12 code style
- Always add `declare(strict_types=1)` at the top of every file
- Prefer functions over classes unless OOP is clearly justified
- Use `match` over `switch`, `??` over long ternary chains
- Always validate and sanitize external input
- No inline SQL — use PDO with prepared statements only
- Separate config / routing / templates — self-written router, no
  Composer packages for routing/DI
- No mixed PHP/HTML — logic and presentation in separate files
- Money is never a `float` — store prices as `DECIMAL(10,2)` in the DB
  (or integer minor units, e.g. kopecks/cents, if the project already
  uses that convention); format for display only inside Views

## E-commerce specific

- Cart: server is the source of truth — always recheck price and stock
  from the DB at checkout, never trust totals sent from the client
- Orders: status transitions (created → paid → shipped → cancelled) go
  through one function that validates the transition, never a raw
  `UPDATE orders SET status = ...`
- Stock/inventory updates that touch money or quantity run inside a
  PDO transaction (`beginTransaction` / `commit` / `rollBack`) — but a
  bare transaction does NOT by itself prevent overselling: two
  concurrent requests can both read the same stock value before
  either commits. Decrement with a single conditional statement that
  fails when there isn't enough left —
  `UPDATE products SET stock_quantity = stock_quantity - :qty
  WHERE id = :id AND stock_quantity >= :qty` — and check
  `rowCount()` (0 = out of stock, roll back); or take a
  `SELECT ... FOR UPDATE` row lock first if the flow needs to read
  the value before deciding
- Payment/shipping provider integrations live in `src/Services/`,
  never called directly from Controllers or Views
- Always verify payment webhook signatures before trusting a payload;
  log every webhook call

## HTML

- Semantic tags first: `<main>`, `<section>`, `<article>`, `<nav>`
- Accessibility required: `alt` on every image (product photos
  included), `aria-*` and `role` where needed
- No inline styles — use classes

## CSS

- Mobile-first by default
- Layout uses the **Bootstrap 5 grid only**: `container` / `row` /
  `col-*` — no CSS Grid (`display: grid`), no ad-hoc flex layouts
  instead of grid
- Custom classes follow BEM on top of the grid, e.g.
  `product-card__price`, `product-card__price--sale`
- Use CSS custom properties instead of magic numbers
  (`--spacing-md: 1rem`)
- Self-host Bootstrap and all third-party CSS/JS locally — no CDN
  (shared hosting must not depend on external uptime)
- Avoid `!important` except for utility overrides
- Group properties: positioning → box model → typography → visual →
  animation

## JavaScript

- ES Modules, async/await, arrow functions
- Functional style only — no class-based components
- No jQuery, no global variables — Bootstrap 5's JS components
  (modal, dropdown, carousel, offcanvas) are used via their native
  vanilla JS API
