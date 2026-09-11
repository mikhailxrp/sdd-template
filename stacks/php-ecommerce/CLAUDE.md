# CLAUDE.md — Project Rules

Этот файл читается при каждой сессии.
Следуй этим правилам при любой задаче.

---

## О проекте

< Название проекта > — < краткое описание в 2-3 предложения: что это, для кого, деплой >

---

## Документация

Перед началом задачи читай нужные файлы:

| Тема | Файл |
|------|------|
| Обзор продукта + фичи | `.docs/prd.md` |
| Схема БД | `.docs/database.md` |
| Текущая фаза | `.docs/phases/phase-N.md` |
| Текущий таск | `TASK.md` |
| Definition of Done | `.docs/dod-global.md` |

---

## Tech Stack

**Используем:**

| Слой | Технология | Почему |
|------|------------|--------|
| Backend | PHP 8.x | Работает на любом shared-хостинге |
| БД | MySQL 8 | Стандарт shared-хостинга |
| Frontend | Bootstrap 5 + Vanilla JS | Без сборщиков |
| Графики | Chart.js | Лёгкий, без зависимостей |
| Авторизация | PHP Sessions + bcrypt | Встроено, безопасно |
| Тестирование | PHPUnit (dev-зависимость через Composer) | Unit-тесты для чистой логики (Core-хелперы, Router); не деплоится на прод |

**Не используем — никогда:**
- Next.js / React / Vue (требуют Node.js)
- ORM (только PDO напрямую)
- jQuery (только Vanilla JS)
- Composer-пакеты для роутинга/DI (самописный роутер)

---

## Архитектура

```
public/          → document root, единственная точка входа
public/uploads/  → загружаемый контент (фото товаров), PHP там не выполняется
src/Controllers/ → логика обработки запросов, никакого SQL
src/Models/      → только работа с БД
src/Views/       → только HTML + минимум PHP
src/Core/        → Router, Database, Request, functions, Logger
src/Services/    → email, файлы, внешние сервисы
config/          → routes.php, config.php (не секреты)
.env             → секреты, в .gitignore
storage/logs/    → логи приложения (вне document root, недоступны по HTTP)
```

---

## Правила по слоям

### Controllers
- Принимают запрос → вызывают Model → передают данные в View
- Никакого SQL
- POST всегда заканчивается redirect()
- Валидация входных данных здесь

### Models
- Только SQL через PDO prepared statements
- Возвращают массивы, не объекты PDO
- Никакого HTML, никаких редиректов

### Views
- Только HTML + echo переменных
- Никакого SQL, никакой бизнес-логики
- Весь вывод через htmlspecialchars()
- Данные получают через переменные от Controller

### Services
- Отправка email, работа с файлами, внешние API
- Вызываются из Controllers, не из Views

### PHP
- PSR-12 code style
- `declare(strict_types=1)` в каждом файле
- Функции, не классы (если не нужен DI)
- `match` вместо `switch`
- Валидация и санитизация всего внешнего ввода

### CSS
- Mobile-first
- BEM: `block__element`, `block--modifier`
- CSS custom properties вместо magic numbers
- Никаких inline-стилей

### JS
- ES Modules, async/await, arrow functions
- Functional style — никаких классов
- Никаких глобальных переменных

### HTML
- Семантические теги: `<main>`, `<section>`, `<article>`, `<nav>`
- `alt` на всех изображениях, `aria-*` где нужно
- Никаких inline-стилей

---

## Views — компоненты

- Компонент = отдельный `.php` файл в `src/Views/components/`
- Данные передаются через переменные: `$card = [...]; include 'component.php'`
- Переиспользуемый блок = выноси в `components/` если встречается 2+ раз
- Никаких inline-стилей в `.php` файлах

---

## Маршрутизация

```
Запрос: GET /dashboard
        ↓
.htaccess → public/index.php
        ↓
Core/Router.php читает config/routes.php
        ↓
Controllers/DashboardController.php → метод index()
        ↓
Views/dashboard.php
```

---

## Безопасность

- Все запросы к БД — PDO prepared statements, никогда конкатенация
- Пароли — `password_hash()` / `password_verify()`, никогда md5/sha1
- Вывод в Views — `htmlspecialchars()` на всё
- CSRF-токен на каждой форме с POST — `csrfField()` + `requireCsrf()` (детали в `php.md`)
- Куки сессии захардены централизованно (httponly/samesite/secure) +
  security-заголовки на каждый ответ — детали и требование HTTPS в
  проде см. `php.md`
- `.env` в `.gitignore` — секреты никогда в репозитории
- `src/` и `config/` недоступны напрямую (document root = `public/`)

---

## AI Rules (для агента)

- Перед задачей читать `TASK.md` и `phase-N.md`
- Работать только в scope текущего таска
- Не менять файлы вне scope
- Не рефакторить попутно
- Перечислять файлы которые будут изменены
- Сначала анализ → план → список файлов → только потом код
- Для многошаговых тасков — на каждый шаг сразу указывать, чем он
  будет проверен (unit-тест, ручная проверка в браузере, конкретный
  пункт DoD), а не только что сделать

### Поддержка документации проекта

- Изменения и решения фиксируй в `.docs/dev-log.md` — не версионируй
  `CLAUDE.md` записями вида «v1.2 — добавлено...» внутри самого файла.
  `CLAUDE.md` описывает текущее состояние, а не историю изменений
- Если правило уже описано в файле (`CLAUDE.md`, `general.md`, `php.md`,
  `database.md`) — обновляй его на месте. Не добавляй второе
  упоминание того же факта в другом разделе или файле: две копии
  одного правила рано или поздно разойдутся
- WHY у неочевидного архитектурного решения — 1-2 строки прямо на
  месте (в дереве папок, в таблице). Если объяснение начинает
  разрастаться в абзац с историей — выноси в отдельный файл
  (`.docs/modules/<name>.md` или аналог), а на месте оставляй только
  короткую ссылку на него
