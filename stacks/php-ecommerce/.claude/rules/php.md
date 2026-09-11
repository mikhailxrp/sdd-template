---
description: PHP rules for e-commerce Mini-MVC projects (PHP 8+, no framework, own engine)
globs: ["**/*.php"]
---

## Core principles

- PHP 8+ only — use match, named arguments, nullsafe operator
- Always add `declare(strict_types=1)` at the top of every file
- Functional style by default — no classes unless justified
- No spaghetti — logic and HTML must never mix in the same file

## Structure rules

- public/index.php — front controller only, no business logic
- src/Controllers/ — handle request, call model, pass data to view
- src/Models/ — only DB queries, return plain arrays
- src/Views/ — only HTML + echo, no loops over DB, no business logic
- src/Core/ — router, request helpers, shared utilities
- src/Services/ — email, file upload, external APIs
- config/routes.php — all routes in one place
- config/config.php — all constants and env loading

## Functions vs classes

- Functions stay the default for Controllers, Models, and business
  logic operating on plain arrays (catalog, cart contents, order rows)
- A class is justified when:
  - integrating multiple interchangeable providers behind one contract
    (payment gateways: YooKassa/CloudPayments/Stripe; shipping:
    СДЭМ/Boxberry) — write a small interface + one class per provider
    instead of a growing `match` on provider name
  - a service needs the same config/client on every call (SMTP
    client, S3/file storage client, HTTP client to an external API) —
    constructor-injected config beats passing `$config` into every
    function
  - wrapping a third-party SDK that is itself OOP (Stripe SDK, PayPal
    SDK) — call their classes directly, keep your own wrapper thin
- Do not introduce domain objects (Order, Cart as classes) just for
  the sake of OOP — plain arrays + functions are enough at this scale

## Database

- PDO only — no mysqli
- Always use prepared statements
- All DB functions live in src/Models/
- Return plain arrays from model functions
- One function = one query — except a multi-step write that must be
  atomic (e.g. create order + insert order_items + decrement stock):
  keep all of it in one Model function wrapped in
  `beginTransaction()` / `commit()` / `rollBack()`
- Stock/quantity decrements always happen inside that same
  transaction, never as a separate follow-up query — use the
  conditional `UPDATE ... WHERE stock_quantity >= :qty` pattern from
  general.md, not a plain SELECT-then-UPDATE (a transaction alone does
  not stop two concurrent requests from overselling)

## Views

- Views receive data as variables — never query DB inside a view
- Escape all output: htmlspecialchars($var, ENT_QUOTES, 'UTF-8')
- Use e() helper function as shortcut

## Cart & orders

- Cart totals and item prices are never trusted from the client —
  re-read price and stock from the DB at every checkout step
- Order status changes (created → paid → shipped → cancelled) go
  through one function that validates the transition — never a raw
  `UPDATE orders SET status = ...` from a controller
- Payment/shipping provider calls live in src/Services/, never
  directly in Controllers or Views

## Security

- Never trust user input
- Use password_hash() / password_verify(); minimum 8 characters,
  validated before hashing — don't add further complexity rules
  unless the product explicitly needs them
- Call `regenerateSession()` right after a successful login (rotates
  session id and CSRF token — `src/Core/functions.php`), not the raw
  `session_regenerate_id()` call
- Login/register/forgot-password error messages never reveal whether
  an email exists in the system — same generic message for "wrong
  password" and "no such account" (prevents account enumeration)
- Log failed login attempts and rate-limit trips with `logWarning()`
  (context is auto-redacted for password/token/secret — see
  `src/Core/Logger.php`) for later incident review
- Session cookies are hardened centrally in `ensureSessionStarted()`
  (`httponly`, `samesite=Lax`, `secure` when `APP_ENV=production`) —
  don't override cookie params per-controller. `secure` only works if
  production is actually served over HTTPS; deploying prod on plain
  HTTP silently breaks sessions
- Security response headers (`X-Content-Type-Options`,
  `X-Frame-Options`, `Content-Security-Policy: frame-ancestors`,
  `Referrer-Policy`) are sent once for every request via
  `sendSecurityHeaders()` in `public/index.php` — don't duplicate them
  per-controller, extend that one function if a new header is needed
- CSRF token on every state-changing form — render it with
  `csrfField()`, and call `requireCsrf()` (or
  `verifyCsrfToken(input('_csrf'))` directly) at the top of every POST
  handler before touching the Model (`src/Core/functions.php`)
- Never store raw card/payment data — only tokens returned by the
  payment gateway
- Verify payment webhook signatures before trusting the payload; log
  every webhook call with its order id (see `payment_logs` in
  database.md)
- Rate-limit login and checkout submissions to slow brute-force and
  fake-order spam — guard with `tooManyAttempts('login', 5, 60)`
  before processing, `hitRateLimit('login')` on a failed attempt, and
  `clearRateLimit('login')` on success (`src/Core/functions.php`)

## Тестирование

- `vendor/` и `composer.lock` не лежат в шаблоне — при первом запуске
  тестов в новом проекте, если `vendor/` отсутствует, сначала выполни
  `composer install`, и только потом `composer test`
- PHPUnit — dev-зависимость через Composer (`composer require-dev`),
  не деплоится на прод (`composer install --no-dev` для боевого сервера)
- Юнит-тестами покрывается только логика без обращения к БД и без
  HTTP-контекста (работа с `$_SESSION` в CLI допустима): хелперы
  `src/Core/functions.php` (CSRF, rate-limit, `normalizeUserId`,
  `regenerateSession`), сопоставление маршрутов `src/Core/Router.php`,
  расчёты над массивами (корзина, суммы)
- Тесты на Model-функции, которые ходят в БД — отдельная категория
  (integration), требуют тестовую БД. Не заводи эту инфраструктуру
  заранее — только когда появится первая реальная Model, которую
  нужно тестировать
- Views/HTML/JS и любые DB-потоки — по-прежнему только ручная
  проверка через `.docs/dod-global.md`, автотесты её не заменяют

## Error handling

- Never use @ to suppress errors
- Log errors to file — never output raw errors in production
- User sees: friendly message. Log sees: full trace
- Payment/order errors are logged with order id and transaction id;
  the user-facing message never includes gateway-specific details
