# Схема БД

> Этот файл — детальное описание всех таблиц.
> Агент читает его при планировании тасков связанных с БД.
> Синхронизируй с `database/install.php`.

---

## Как устроен этот файл

Ниже — **базовый набор таблиц**, который есть почти в любом интернет-магазине
(каталог → корзина → заказ). Это часть шаблона, а не схема конкретного проекта:
таблицы, колонки, FK и индексы здесь — стартовая точка, рассчитанная сразу на
каталог порядка **10 000–50 000 товаров**, чтобы не переделывать индексацию
задним числом.

При адаптации под свой магазин:
- базовые таблицы обычно **не удаляют**, а расширяют колонками
  (`brand_id`, `weight`, `barcode` и т.п.);
- специфичные для проекта таблицы добавляй в раздел «Дополнительные таблицы»
  по тому же формату (колонка | тип | назначение) и зеркаль их в
  `database/install.php` в порядке зависимостей (сначала родитель, потом
  потомок — `categories` → `products` → `order_items`).

---

## Базовые таблицы

### `users`

| Колонка | Тип | Назначение |
|---------|-----|------------|
| id | INT PK AUTO_INCREMENT | |
| name | VARCHAR(100) NOT NULL | |
| email | VARCHAR(150) NOT NULL UNIQUE | |
| password_hash | VARCHAR(255) NOT NULL | |
| role | ENUM('customer','admin') NOT NULL DEFAULT 'customer' | разделение доступа к админке |
| created_at | TIMESTAMP DEFAULT NOW | |

---

### `categories`

| Колонка | Тип | Назначение |
|---------|-----|------------|
| id | INT PK AUTO_INCREMENT | |
| parent_id | INT NULL, FK → categories.id, ON DELETE SET NULL | подкатегории; NULL = корневая |
| name | VARCHAR(150) NOT NULL | |
| slug | VARCHAR(160) NOT NULL UNIQUE | для человекопонятных URL |
| sort_order | INT NOT NULL DEFAULT 0 | порядок в меню |
| seo_title | VARCHAR(70) NULL | если пусто — генерируется по шаблону, см. правило ниже |
| seo_description | VARCHAR(160) NULL | если пусто — генерируется по шаблону |
| created_at | TIMESTAMP DEFAULT NOW | |

**Индексы:** `INDEX(parent_id)`

---

### `products`

| Колонка | Тип | Назначение |
|---------|-----|------------|
| id | INT PK AUTO_INCREMENT | |
| category_id | INT NOT NULL, FK → categories.id, ON DELETE RESTRICT | нельзя удалить категорию, пока в ней есть товары |
| sku | VARCHAR(64) NOT NULL UNIQUE | артикул |
| name | VARCHAR(200) NOT NULL | |
| slug | VARCHAR(220) NOT NULL UNIQUE | |
| description | TEXT NULL | |
| price | DECIMAL(10,2) NOT NULL | никогда FLOAT — см. `php.md` |
| stock_quantity | INT NOT NULL DEFAULT 0 | |
| is_active | TINYINT(1) NOT NULL DEFAULT 1 | товар не удаляют физически, а деактивируют |
| seo_title | VARCHAR(70) NULL | если пусто — генерируется по шаблону, см. правило ниже |
| seo_description | VARCHAR(160) NULL | если пусто — генерируется по шаблону |
| created_at | TIMESTAMP DEFAULT NOW | |
| updated_at | TIMESTAMP DEFAULT NOW ON UPDATE CURRENT_TIMESTAMP | |

**Индексы:**
- `INDEX(category_id, is_active)` — листинг каталога по категории
- `INDEX(price)` — сортировка/фильтр по цене
- `FULLTEXT(name, description)` — поиск; `LIKE '%...%'` не использует индекс и
  на 50k строк деградирует

> `product_attributes` (см. «Дополнительные таблицы») хранит характеристики
> отдельно от `description`, если у товаров есть структурированные свойства
> (материал, размер, вес и подобные) — такая пара «свойство-значение» попадает
> в `schema.org/Product` и её проще процитировать ИИ-поисковику, чем вычленять
> факт из сплошного текста описания (см. `dod-global.md`, раздел «SEO и GEO»).
> Добавляй эту таблицу, если в ТЗ проекта есть хотя бы одна характеристика
> товара сверх названия и описания — не жди, пока появится второй вариант
> товара.

---

### `product_images`

| Колонка | Тип | Назначение |
|---------|-----|------------|
| id | INT PK AUTO_INCREMENT | |
| product_id | INT NOT NULL, FK → products.id, ON DELETE CASCADE | |
| path | VARCHAR(255) NOT NULL | относительный путь в `storage/` или `public/assets/img/` |
| sort_order | INT NOT NULL DEFAULT 0 | |
| is_main | TINYINT(1) NOT NULL DEFAULT 0 | главное фото карточки |

**Индексы:** `INDEX(product_id)`

---

### `cart_items`

| Колонка | Тип | Назначение |
|---------|-----|------------|
| id | INT PK AUTO_INCREMENT | |
| session_id | VARCHAR(64) NULL | корзина гостя (PHP session id) |
| user_id | INT NULL, FK → users.id, ON DELETE CASCADE | корзина авторизованного |
| product_id | INT NOT NULL, FK → products.id, ON DELETE CASCADE | |
| quantity | INT NOT NULL DEFAULT 1 | |
| created_at | TIMESTAMP DEFAULT NOW | |

**Индексы:** `INDEX(session_id)`, `INDEX(user_id)`

> Цена здесь никогда не хранится — при чекауте всегда перечитывается из
> `products` (см. правило "server is the source of truth" в `general.md`).
> Ровно одно из `session_id` / `user_id` должно быть заполнено — проверяется
> в Model, а не constraint'ом БД.

---

### `orders`

| Колонка | Тип | Назначение |
|---------|-----|------------|
| id | INT PK AUTO_INCREMENT | |
| user_id | INT NULL, FK → users.id, **ON DELETE SET NULL** | гостевой заказ = NULL |
| status | ENUM('created','paid','shipped','cancelled') NOT NULL DEFAULT 'created' | меняется только через одну функцию-переход, см. `php.md` |
| total | DECIMAL(10,2) NOT NULL | |
| created_at | TIMESTAMP DEFAULT NOW | |
| updated_at | TIMESTAMP DEFAULT NOW ON UPDATE CURRENT_TIMESTAMP | |

**Индексы:** `INDEX(user_id)`, `INDEX(status)`, `INDEX(created_at)`

> Исключение из общего правила «`user_id` → CASCADE»: если удалить
> пользователя, заказы должны остаться (бухгалтерия/история), поэтому здесь
> `SET NULL`, а не `CASCADE`.

---

### `order_items`

| Колонка | Тип | Назначение |
|---------|-----|------------|
| id | INT PK AUTO_INCREMENT | |
| order_id | INT NOT NULL, FK → orders.id, ON DELETE CASCADE | |
| product_id | INT NULL, FK → products.id, ON DELETE SET NULL | NULL, если товар позже удалили физически |
| product_name | VARCHAR(200) NOT NULL | снэпшот названия на момент заказа |
| price | DECIMAL(10,2) NOT NULL | снэпшот цены на момент заказа |
| quantity | INT NOT NULL | |

**Индексы:** `INDEX(order_id)`, `INDEX(product_id)`

> `product_name` и `price` дублируются намеренно — если товар подорожает или
> исчезнет из каталога, история заказа не должна измениться задним числом.

---

### `payment_logs`

| Колонка | Тип | Назначение |
|---------|-----|------------|
| id | INT PK AUTO_INCREMENT | |
| order_id | INT NOT NULL, FK → orders.id, ON DELETE CASCADE | |
| provider | VARCHAR(50) NOT NULL | например `yookassa`, `cloudpayments` |
| signature_valid | TINYINT(1) NOT NULL | результат проверки подписи вебхука |
| payload | TEXT NOT NULL | сырое тело запроса — для разбора спорных платежей |
| created_at | TIMESTAMP DEFAULT NOW | |

**Индексы:** `INDEX(order_id)`

> Обязательна, потому что `php.md` уже требует: «верифицировать подпись
> вебхука и логировать каждый вызов». Без этой таблицы требование нечем
> подтвердить при разборе спорного платежа.

---

### `content_pages`

| Колонка | Тип | Назначение |
|---------|-----|------------|
| id | INT PK AUTO_INCREMENT | |
| slug | VARCHAR(160) NOT NULL UNIQUE | `/contacts`, `/delivery`, `/about` и т.п. |
| title | VARCHAR(200) NOT NULL | заголовок страницы, отображается как `<h1>` |
| body | TEXT NOT NULL | содержимое страницы |
| seo_title | VARCHAR(70) NULL | если пусто — используется `title` |
| seo_description | VARCHAR(160) NULL | если пусто — генерируется из первых слов `body` |
| updated_at | TIMESTAMP DEFAULT NOW ON UPDATE CURRENT_TIMESTAMP | |

> Статические страницы (контакты, доставка и оплата, о компании,
> юридические документы) редактируются Администратором через БД, не
> хардкожены во Views — иначе правка текста требует участия
> разработчика и не проходит `dod-global.md` (раздел «Безопасность»,
> пункт про контент, редактируемый без правки кода — если он есть
> в ТЗ конкретного проекта).

---

## Правило генерации SEO-полей

Применяется одинаково к `products.seo_title`/`seo_description`,
`categories.seo_title`/`seo_description`, `content_pages.seo_title`/
`seo_description` — реализуется одной общей функцией в `Core`, не
дублируется в каждом контроллере отдельно:

1. Если `seo_title`/`seo_description` заполнены — используются как есть
2. Если пусто — собираются по шаблону из имеющихся данных сущности,
   например для товара: `"{name} купить в {shop_city} — {shop_name}"`
   (конкретный шаблон и `{shop_name}`/`{shop_city}` — из настроек
   проекта, не хардкодить в шаблоне php-ecommerce буквально)
3. Ни при каком варианте `<title>`/`<meta description>` не остаются
   пустыми — фолбэк обязателен, не просто «поле есть в БД»

---

## Дополнительные таблицы (примеры для расширения)

Не создаются по умолчанию — паттерн того, как добавлять таблицы под свой
проект, не ломая конвенции выше:

| Таблица | Когда нужна |
|---------|-------------|
| `addresses` | если адресов доставки у пользователя несколько, а не один на заказ |
| `coupons` / `order_coupons` | промокоды и скидки |
| `product_attributes` | характеристики товара как структурированные пары «свойство-значение» (материал, размер, вес) — базовая по умолчанию, см. примечание к `products` выше; таблица здесь как пример структуры: `id, product_id FK, attr_name, attr_value` |
| `reviews` | отзывы на товары, `product_id FK, user_id FK, rating, text` |

---

## Карта связей

```
users (1)
  ├──< orders (1:N, ON DELETE SET NULL)
  └──< cart_items (1:N, ON DELETE CASCADE)

categories (1)
  ├──< categories (self, parent_id, ON DELETE SET NULL)
  └──< products (1:N, ON DELETE RESTRICT)

products (1)
  ├──< product_images (1:N, ON DELETE CASCADE)
  ├──< cart_items (1:N, ON DELETE CASCADE)
  └──< order_items (1:N, ON DELETE SET NULL)

orders (1)
  ├──< order_items (1:N, ON DELETE CASCADE)
  └──< payment_logs (1:N, ON DELETE CASCADE)
```

---

## Правила

- Все `user_id` FK → `ON DELETE CASCADE`, **кроме `orders.user_id`**
  (`SET NULL` — история заказов должна пережить удаление аккаунта)
- Все таблицы → `ENGINE=InnoDB`, `utf8mb4_unicode_ci`
- Пароли никогда в открытом виде
- Деньги — только `DECIMAL(10,2)`, никогда `FLOAT`/`DOUBLE`
- Товары не удаляются физически — деактивируются `is_active = 0`
  (сохраняет ссылочную целостность с `order_items` и историю заказов)
- Поиск по названию/описанию — только через `FULLTEXT`, не `LIKE '%...%'`
- Листинг каталога — всегда с пагинацией; на страницах вглубь каталога
  (когда `OFFSET` большой) предпочитать keyset-пагинацию
  (`WHERE id > :last_id LIMIT :n`) вместо `LIMIT :offset, :n`, которая на
  больших таблицах линейно замедляется с ростом смещения
- `seo_title`/`seo_description` есть у каждой публично индексируемой
  сущности (`products`, `categories`, `content_pages`) и заполняются
  по единому правилу генерации (см. выше) — не добавляй новую публичную
  таблицу без этой пары полей, если её записи открываются отдельным URL
