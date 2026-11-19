# Laravel Starter Template — SDD методология

Модульный шаблон для старта проектов на Laravel с готовой документацией, правилами ядра и подключаемыми пакетами возможностей (`capabilities/`).

**Стек ядра:** Laravel 13 (PHP 8.3+) + PostgreSQL + Blade / Livewire 4 / Alpine.js + Tailwind CSS + Filament 5 + Pest 4 + Pint  
**Деплой:** VPS (PHP-FPM + nginx + PostgreSQL; shared-хостинг не подходит)  
**Инструмент разработки:** любой агент, понимающий `AGENTS.md` — Claude Code (через `CLAUDE.md`) или Antigravity. Промпты, правила и команды одинаковы для обоих.

---

## Быстрый старт

1. Создай проект скриптом `sdd-new-project.ps1 -Stack laravel ...` (он скопирует шаблон и сделает первый коммит с исходной папкой `capabilities/`)
2. Положи ТЗ в `00-input/tz.md`
3. Пройди конвейер документации:
   - `/sdd-init` — заполнит «О продукте» и «Роли» в `.docs/prd.md`
   - `/sdd-capabilities` — соберёт блоки включённых пакетов (`catalog`, `leads`, `onec-sync`, `ai`, …) в `AGENTS.md`, `.docs/database.md`, `.docs/dod-global.md` и `.docs/capabilities.md`, затем после подтверждения удалит `capabilities/`
   - `/sdd-schema` — добавит проектные таблицы и колонки сверх пакетов в `.docs/database.md`
   - `/sdd-roadmap` — спланирует фазы в `.docs/phases/_status.md`
   - `/sdd-review` — проверит готовность документации новой сессией
4. В Фазе 0 разверни каркас Laravel + PostgreSQL + Filament + Pest + Pint, настрой `.env` по `.env.example` и двигайся по циклу из `current-pipeline.md`.

---

## Структура шаблона

```
stacks/laravel/
├── AGENTS.md                    ← Конституция проекта (ядро + блоки включённых пакетов)
├── CLAUDE.md                    ← Точка входа Claude Code: подключает AGENTS.md и .docs/rules/ (не править)
├── TASK.md                      ← Текущий активный таск
├── TASK-example.md              ← Шаблон для создания тасков
├── current-pipeline.md          ← Схема цикла разработки
├── .gitignore                   ← Игнор-лист под Laravel, Vite, Pest, .env
├── .env.example                 ← Базовые переменные окружения (PostgreSQL, очереди)
│
├── capabilities/                ← Исходники пакетов (удаляется после /sdd-capabilities init)
│   ├── _format.md               ← Формат пакетов, маркеры, проверки
│   ├── catalog.md               ← Каталог товаров (ready)
│   ├── leads.md                 ← Заявки без оплаты с подключаемыми каналами (ready)
│   ├── onec-sync.md             ← Обмен с 1С (ready)
│   ├── ai.md                    ← ИИ-помощники по ТЗ (ready)
│   ├── cart-checkout.md         ← Корзина и заказы (stub)
│   └── payments.md              ← Онлайн-оплата (stub)
│
└── .docs/
    ├── prd.md                   ← Описание продукта, роли, таблица возможностей
    ├── database.md              ← Схема БД PostgreSQL (ядро + блоки пакетов)
    ├── dod-global.md            ← Глобальный чеклист готовности (ядро + блоки пакетов)
    ├── dev-log.md               ← Журнал сессий и архитектурных решений
    ├── rules/                   ← Правила кода (подключены из AGENTS.md и CLAUDE.md)
    │   ├── general.md           ← Универсальные правила кода, Tailwind, Alpine.js
    │   ├── laravel.md           ← Контракты слоёв к CORE-N (Actions, Livewire, Filament, Pest)
    │   └── seo.md               ← Правила SEO/GEO (<x-seo>, sitemap, robots)
    ├── phases/
    │   ├── _status.md           ← Статус всех фаз
    │   └── phase-example.md     ← Шаблон фазы
    └── prompts/
        ├── project-init.md      ← Ручной старт из ТЗ (альтернатива слэш-командам)
        ├── phase-init.md        ← Промпт планирования фазы
        ├── task-init.md         ← Промпт создания TASK.md
        └── dod-check.md         ← Промпт проверки DoD перед коммитом
```

---

## Управление пакетами (`capabilities`)

- Состав пакетов задаётся **только** в `.docs/prd.md` → «Возможности».
- После первой сборки `/sdd-capabilities` удаляет папку `capabilities/` из проекта, чтобы правила невключённых пакетов не попадали в контекст агента.
- Если позже нужно подключить или убрать пакет:
  - `/sdd-capabilities add <name>` — берёт пакет из первого коммита проекта или из `sdd-template` и вставляет блоки по якорям `<!-- sdd-capabilities: … -->`.
  - `/sdd-capabilities remove <name>` — удаляет блоки по маркерам `<!-- capability:<name>:begin/end -->` (таблицы БД удаляются отдельной миграцией по `CORE-8`).

---

## Цикл работы

1. Проверить `.docs/phases/_status.md` и `TASK.md`.
2. Создать таск через `.docs/prompts/task-init.md`.
3. Реализовать задачу: `Реализуй задачу из TASK.md. Следуй AGENTS.md`.
4. Проверить `vendor/bin/pint --test`, `vendor/bin/pest`, `.docs/prompts/dod-check.md` и браузер.
5. Закрыть таск, обновить `phase-N.md`, в конце сессии записать итог в `.docs/dev-log.md`.
