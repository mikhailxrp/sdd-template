# WordPress + WooCommerce Starter Template — SDD методология

Модульный шаблон для старта проектов на **WordPress 6.x + WooCommerce** с готовой документацией, болванкой чистой темы (`starter-theme`), правилами ядра и подключаемыми пакетами возможностей (`capabilities/`).

**Стек ядра:** WordPress 6.x (PHP 8.1+) + MySQL/MariaDB + кастомная тема (`starter-theme`) + Redux Framework + Bootstrap 5 (`row/col`) + BEM + jQuery/vanilla JS (без сборщиков и CDN) + SEO-плагин  
**Окружение:** локально **OpenServer**, продакшен — **shared-хостинг**  
**Инструмент разработки:** любой агент, понимающий `AGENTS.md` — Claude Code (через `CLAUDE.md`) или Antigravity. Промпты, правила и команды одинаковы для обоих.

---

## Быстрый старт

1. Создай проект скриптом `sdd-new-project.ps1 -Stack wp-woocommerce ...` (он скопирует шаблон, болванку темы и сделает первый коммит с исходной папкой `capabilities/`).
2. Убедись, что ТЗ лежит в `00-input/tz.md` (а если есть готовая статическая вёрстка Stage 1 / `direction.md` — в `00-input/design/`).
3. Пройди конвейер документации:
   - `/sdd-init` — заполнит «О продукте» и «Роли» в `.docs/prd.md`
   - `/sdd-capabilities` — соберёт блоки включённых пакетов (`woocommerce`, `leads`, `custom-plugin`, …) в `AGENTS.md`, `.docs/database.md`, `.docs/dod-global.md` и `.docs/capabilities.md`, затем после подтверждения удалит `capabilities/`
   - `/sdd-schema` — добавит проектные CPT, метаполя Redux и кастомные таблицы сверх пакетов в `.docs/database.md`
   - `/sdd-roadmap` — спланирует фазы в `.docs/phases/_status.md`
   - `/sdd-review` — проверит готовность документации новой сессией
4. В Фазе 0:
   - Разверни WordPress в домене OpenServer (PHP 8.1+, MySQL/MariaDB), скопируй `wp-config-local.example.php` → `wp-config-local.php` и подключи его в `wp-config.php`.
   - Переименуй `wp-content/themes/starter-theme/` в `wp-content/themes/<theme-slug>/` (и обнови шапку `style.css`, text-domain и префиксы функций).
   - Установи и активируй нужные плагины (Redux Framework, SEO-плагин, WooCommerce при включённом пакете `woocommerce`).
   - Двигайся по циклу из `current-pipeline.md`.

---

## Структура шаблона

```
stacks/wp-woocommerce/
├── AGENTS.md                        ← Конституция проекта (ядро + блоки включённых пакетов)
├── CLAUDE.md                        ← Точка входа Claude Code: подключает AGENTS.md и .docs/rules/ (не править)
├── TASK.md                          ← Текущий активный таск
├── TASK-example.md                  ← Шаблон для создания тасков
├── current-pipeline.md              ← Схема цикла разработки
├── .gitignore                       ← Игнор-лист под WordPress (трекаем тему и кастомные плагины, не ядро)
├── wp-config-local.example.php      ← Пример локальных настроек OpenServer (БД, WP_DEBUG)
│
├── wp-content/
│   └── themes/
│       └── starter-theme/           ← Болванка чистой темы (без npm/сборщиков; переименовать в Фазе 0)
│
├── capabilities/                    ← Исходники пакетов (удаляется после /sdd-capabilities init)
│   ├── _format.md                   ← Формат пакетов, маркеры, проверки
│   ├── woocommerce.md               ← Магазин WooCommerce (ready, critical)
│   ├── leads.md                     ← Формы заявок и обратной связи (ready)
│   ├── custom-plugin.md             ← Отдельный проектный плагин (ready)
│   ├── payments-ru.md               ← РФ платёжные шлюзы и 54-ФЗ (stub)
│   ├── shipping-ru.md               ← Службы доставки СДЭК/Почта/Boxberry (stub)
│   └── onec-sync.md                 ← Обмен с 1С (stub)
│
└── .docs/
    ├── prd.md                       ← Описание продукта, роли, таблица возможностей
    ├── database.md                  ← Схема БД, CPT, метаполя Redux и кастомные таблицы
    ├── dod-global.md                ← Глобальный чеклист готовности (ядро + блоки пакетов)
    ├── dev-log.md                   ← Журнал сессий и архитектурных решений
    ├── rules/                       ← Правила кода (подключены из AGENTS.md и CLAUDE.md)
    │   ├── general.md               ← Общие правила, Bootstrap 5, BEM, JS, дизайн-токены
    │   ├── wordpress.md             ← Детальные правила WordPress к CORE-N
    │   └── seo.md                   ← Правила SEO/GEO на WordPress (раздел 7b)
    ├── phases/
    │   ├── _status.md               ← Статус всех фаз
    │   └── phase-example.md         ← Шаблон фазы
    └── prompts/
        ├── project-init.md          ← Ручной старт из ТЗ (альтернатива слэш-командам)
        ├── phase-init.md            ← Промпт планирования фазы
        ├── task-init.md             ← Промпт создания TASK.md
        └── dod-check.md             ← Промпт проверки DoD перед коммитом
```

---

## Управление пакетами (`capabilities`)

- Состав пакетов задаётся **только** в `.docs/prd.md` → «Возможности».
- После первой сборки `/sdd-capabilities` удаляет папку `capabilities/` из проекта, чтобы правила невключённых пакетов не попадали в контекст агента.
- Если позже нужно подключить или убрать пакет:
  - `/sdd-capabilities add <name>` — берёт пакет из первого коммита проекта или из `sdd-template` и вставляет блоки по якорям `<!-- sdd-capabilities: … -->`.
  - `/sdd-capabilities remove <name>` — удаляет блоки по маркерам `<!-- capability:<name>:begin/end -->`.

---

## Цикл работы

1. Проверить `.docs/phases/_status.md` и `TASK.md`.
2. Создать таск через `.docs/prompts/task-init.md`.
3. Выполнить таск, следуя `AGENTS.md` и `.docs/rules/*.md`.
4. Проверить `php -l`, `phpcs`, `wp-content/debug.log`, браузер (OpenServer) и `view-source` по `.docs/prompts/dod-check.md`.
5. Зафиксировать итоги в `.docs/dev-log.md`.
