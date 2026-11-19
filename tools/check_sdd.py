#!/usr/bin/env python3
"""
Валидатор покрытия ТЗ в SDD-документации.

Проверяет, что каждое FR-*/BR-* из готового ТЗ (00-input/tz.md)
упомянуто в карте покрытия (.docs/tz-coverage.md) и попало хотя бы
в одну фазу (.docs/phases/_status.md + .docs/phases/phase-*.md).

Это обратная проверка относительно check_tz.py: там проверялось
"весь ли бриф попал в ТЗ", здесь — "всё ли ТЗ попало в план разработки".

Использование:
    python3 check_sdd.py <папка-проекта>
    python3 check_sdd.py <папка-проекта> --strict
"""

import re
import sys
import glob
import os
from collections import Counter

ID_PATTERN = re.compile(
    r"^###\s+((?:FR-[A-Z][A-Z0-9]*|BR(?:-AI)?)-\d{3})(?:/[БР_])?\s*·"
)


class Issue:
    def __init__(self, severity, message):
        self.severity = severity  # ERROR | WARN
        self.message = message


def extract_ids_from_tz(path):
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()
    ids = []
    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = ID_PATTERN.match(line.strip())
        if m:
            ids.append(m.group(1))
    return ids


RANGE_ANCHOR = re.compile(r"(FR-[A-Z][A-Z0-9]*|BR(?:-AI)?)-(\d{3})")
SEGMENT = re.compile(r"\s*[…\-–]\s*(\d{3})|\s*,\s*(\d{3})")


def extract_mentions(text):
    """
    Все ID, упомянутые где угодно в тексте (для coverage/phases).

    Разворачивает сжатую нотацию диапазонов, которую документация
    намеренно использует вместо построчного перечисления каждого ID
    (см. planning-log.md, ADR-001 — не раздувать документацию):

        FR-AUTH-001…005              -> 001, 002, 003, 004, 005
        FR-ADM-001…002, 005, 008     -> 001, 002, 005, 008
        FR-CARD-001…005, 007…009     -> 001..005, 007..009 (два диапазона)

    Без разворота валидатор видит только первое число и ложно считает
    остальные потерянными требованиями. Не привязан к конкретному
    списку модулей (MARKET, CHANNELS и любые новые подхватываются
    автоматически, т.к. регэксп общий: [A-Z][A-Z0-9]*).
    """
    ids = set()
    for m in RANGE_ANCHOR.finditer(text):
        prefix, first_num = m.group(1), m.group(2)
        ids.add(f"{prefix}-{first_num}")

        pos = m.end()
        last_num = int(first_num)
        # Читаем цепочку сегментов "…NNN" / "-NNN" / ", NNN" подряд,
        # пока они идут без постороннего текста между ними.
        while True:
            sm = SEGMENT.match(text, pos)
            if not sm:
                break
            range_end, single = sm.group(1), sm.group(2)
            if range_end:
                for n in range(last_num, int(range_end) + 1):
                    ids.add(f"{prefix}-{n:03d}")
                last_num = int(range_end)
            else:
                ids.add(f"{prefix}-{single}")
                last_num = int(single)
            pos = sm.end()

    return ids


def check(project_dir):
    issues = []

    tz_path = os.path.join(project_dir, "00-input", "tz.md")
    tz_ids = extract_ids_from_tz(tz_path)

    if tz_ids is None:
        issues.append(Issue("ERROR",
            f"Не найден {tz_path} — нечего проверять на покрытие. "
            f"Скопируй готовое ТЗ в 00-input/tz.md."))
        return issues, [], set(), set()

    if not tz_ids:
        issues.append(Issue("WARN",
            "В tz.md не найдено ни одного FR-*/BR-* — проверь, тот ли файл."))

    coverage_path = os.path.join(project_dir, ".docs", "tz-coverage.md")
    coverage_text = ""
    if os.path.exists(coverage_path):
        coverage_text = open(coverage_path, encoding="utf-8").read()
    else:
        issues.append(Issue("ERROR",
            ".docs/tz-coverage.md не найден — запусти хотя бы sdd-init."))

    covered_in_coverage = extract_mentions(coverage_text)

    # Собираем упоминания из всех файлов фаз
    phases_mentions = set()
    phases_dir = os.path.join(project_dir, ".docs", "phases")
    phase_files = glob.glob(os.path.join(phases_dir, "*.md"))
    for pf in phase_files:
        phases_mentions |= extract_mentions(open(pf, encoding="utf-8").read())

    # Модули (уровень L)
    modules_mentions = set()
    modules_dir = os.path.join(project_dir, ".docs", "modules")
    if os.path.isdir(modules_dir):
        for mf in glob.glob(os.path.join(modules_dir, "*.md")):
            modules_mentions |= extract_mentions(open(mf, encoding="utf-8").read())

    all_covered = covered_in_coverage | phases_mentions | modules_mentions

    # Дубли ID в самом ТЗ — не наша забота (это проверяет check_tz.py),
    # но полезно предупредить, если что-то не так с чтением файла
    dup = [rid for rid, c in Counter(tz_ids).items() if c > 1]
    if dup:
        issues.append(Issue("WARN",
            f"В tz.md повторяются ID: {', '.join(dup[:10])} — "
            f"это должно было поймать check_tz.py на этапе ТЗ."))

    # Главная проверка: покрытие
    uncovered = sorted(set(tz_ids) - all_covered)
    for rid in uncovered:
        issues.append(Issue("ERROR",
            f"{rid}: есть в tz.md, но не упомянуто ни в tz-coverage.md, "
            f"ни в файлах фаз, ни в modules/ — требование потеряется"))

    # Обратная проверка: упоминания в фазах, которых нет в ТЗ
    dangling = sorted((phases_mentions | modules_mentions) - set(tz_ids))
    for rid in dangling:
        issues.append(Issue("WARN",
            f"{rid}: упомянуто в фазах/модулях, но не найдено в tz.md — "
            f"опечатка в ID или устаревшая ссылка"))

    # dod-global.md должен существовать и не быть пустым
    dod_path = os.path.join(project_dir, ".docs", "dod-global.md")
    if not os.path.exists(dod_path) or os.path.getsize(dod_path) < 200:
        issues.append(Issue("ERROR",
            ".docs/dod-global.md отсутствует или пуст — стартер скопирован "
            "не полностью."))

    # AGENTS.md (или CLAUDE.md в старых проектах) — плейсхолдеры
    rules_file = "AGENTS.md"
    rules_path = os.path.join(project_dir, rules_file)
    if not os.path.exists(rules_path):
        rules_file = "CLAUDE.md"
        rules_path = os.path.join(project_dir, rules_file)
    if os.path.exists(rules_path):
        rules_text = open(rules_path, encoding="utf-8").read()
        if "< " in rules_text and " >" in rules_text:
            issues.append(Issue("WARN",
                f"{rules_file} содержит незаполненные плейсхолдеры вида < ... > "
                f"— sdd-init должен был их закрыть."))

    # Проверки пакетов capabilities (только для стеков с модульной архитектурой)
    check_capabilities(project_dir, issues)

    return issues, tz_ids, all_covered, uncovered


CAP_BEGIN_RE = re.compile(r"<!--\s*capability:([a-z0-9-]+):begin\s*-->")
CAP_END_RE = re.compile(r"<!--\s*capability:([a-z0-9-]+):end\s*-->")
CAP_ANCHOR_RE = re.compile(r"<!--\s*sdd-capabilities:")
RULE_DEF_RE = re.compile(r"^\s*\d+\.\s+\*\*([A-Z]{2,5})-(\d+)\.\*\*", re.MULTILINE)
RULE_REF_RE = re.compile(r"\b([A-Z]{2,5})-(\d+)\b")


def _parse_prd_capabilities(prd_path):
    """Читает таблицу «Возможности» из .docs/prd.md -> (enabled, disabled, raw_rows)."""
    if not os.path.exists(prd_path):
        return [], [], []
    text = open(prd_path, encoding="utf-8").read()
    m = re.search(r"^##\s+Возможности\b.*$", text, re.MULTILINE)
    if not m:
        return [], [], []
    section = text[m.end():]
    next_h2 = re.search(r"^##\s+", section, re.MULTILINE)
    if next_h2:
        section = section[:next_h2.start()]

    enabled, disabled, rows = [], [], []
    for line in section.splitlines():
        line_s = line.strip()
        if not line_s.startswith("|"):
            continue
        cols = [c.strip() for c in line_s.strip("|").split("|")]
        if len(cols) < 2:
            continue
        name = cols[0].strip("` ").lower()
        status = cols[1].lower()
        if not name or name in ("пакет", "---") or set(name) <= {"-"}:
            continue
        if not re.match(r"^[a-z0-9-]+$", name):
            continue
        rows.append((name, status))
        if "вкл" in status and "выкл" not in status:
            enabled.append(name)
        elif "выкл" in status and "вкл" not in status:
            disabled.append(name)
    return enabled, disabled, rows


def check_capabilities(project_dir, issues):
    """
    Пост-сборочные проверки для стеков с capabilities/ (см. _format.md):
      1. Для каждой строки «вкл» в prd.md есть маркеры capability:<name>; для «выкл» — нет
      2. Маркеры begin/end парные
      3. Папка capabilities/ отсутствует после init
      4. Якоря <!-- sdd-capabilities: ... --> на месте
      5. Номера правил <PREFIX>-N в AGENTS.md идут подряд, ссылки в dod-global.md
         и capabilities.md указывают на существующие правила
    """
    agents_path = os.path.join(project_dir, "AGENTS.md")
    db_path = os.path.join(project_dir, ".docs", "database.md")
    dod_path = os.path.join(project_dir, ".docs", "dod-global.md")
    caps_doc_path = os.path.join(project_dir, ".docs", "capabilities.md")
    caps_dir = os.path.join(project_dir, "capabilities")
    prd_path = os.path.join(project_dir, ".docs", "prd.md")

    agents_text = open(agents_path, encoding="utf-8").read() if os.path.exists(agents_path) else ""
    uses_capabilities = (
        os.path.isdir(caps_dir)
        or os.path.exists(caps_doc_path)
        or bool(CAP_ANCHOR_RE.search(agents_text))
    )
    if not uses_capabilities:
        return

    # 3. Папка capabilities/ должна быть удалена после /sdd-capabilities init
    if os.path.isdir(caps_dir):
        if os.path.exists(caps_doc_path):
            issues.append(Issue("WARN",
                "capabilities/: папка осталась после сборки (.docs/capabilities.md уже есть) "
                "— удали capabilities/, чтобы невключённые пакеты не попадали в контекст агента."))
        else:
            issues.append(Issue("ERROR",
                "capabilities/: папка не собрана — запусти /sdd-capabilities перед sdd-schema."))
            return

    enabled, disabled, _ = _parse_prd_capabilities(prd_path)

    # 4. Якоря <!-- sdd-capabilities: ... --> должны оставаться на месте
    for rel, path in [
        ("AGENTS.md", agents_path),
        (".docs/database.md", db_path),
        (".docs/dod-global.md", dod_path),
    ]:
        if os.path.exists(path):
            txt = open(path, encoding="utf-8").read()
            if not CAP_ANCHOR_RE.search(txt):
                issues.append(Issue("ERROR",
                    f"{rel}: отсутствует якорь <!-- sdd-capabilities: … --> "
                    f"(нужен для будущего add/remove)."))

    # 1 & 2. Проверка парности маркеров и соответствия таблице prd.md
    target_files = [
        ("AGENTS.md", agents_path, True),
        (".docs/database.md", db_path, False),
        (".docs/dod-global.md", dod_path, True),
        (".docs/capabilities.md", caps_doc_path, True),
    ]
    for rel, path, required_for_enabled in target_files:
        if not os.path.exists(path):
            if required_for_enabled and enabled:
                issues.append(Issue("ERROR", f"{rel}: файл отсутствует при включённых пакетах."))
            continue
        txt = open(path, encoding="utf-8").read()
        begins = CAP_BEGIN_RE.findall(txt)
        ends = CAP_END_RE.findall(txt)
        if Counter(begins) != Counter(ends):
            issues.append(Issue("ERROR",
                f"{rel}: непарные маркеры capability:<name>:begin/end "
                f"(begin={dict(Counter(begins))}, end={dict(Counter(ends))})."))
        present = set(begins) | set(ends)
        if required_for_enabled:
            for name in enabled:
                if name not in present:
                    issues.append(Issue("ERROR",
                        f"{rel}: отсутствует блок включённого пакета capability:{name}."))
        for name in disabled:
            if name in present:
                issues.append(Issue("ERROR",
                    f"{rel}: найден блок выключенного пакета capability:{name}."))

    # 5. Нумерация <PREFIX>-N в AGENTS.md и валидность ссылок в dod-global.md / capabilities.md
    defined_rules = {}
    for prefix, num_s in RULE_DEF_RE.findall(agents_text):
        defined_rules.setdefault(prefix, []).append(int(num_s))

    for prefix, nums in defined_rules.items():
        expected = list(range(1, len(nums) + 1))
        if nums != expected:
            issues.append(Issue("ERROR",
                f"AGENTS.md: нарушена нумерация правил {prefix}-N "
                f"(найдено {nums}, ожидалось 1..{len(nums)})."))

    valid_rule_ids = {f"{p}-{n}" for p, ns in defined_rules.items() for n in ns}
    known_prefixes = set(defined_rules.keys())
    for rel, path in [
        (".docs/dod-global.md", dod_path),
        (".docs/capabilities.md", caps_doc_path),
    ]:
        if not os.path.exists(path):
            continue
        txt = open(path, encoding="utf-8").read()
        for prefix, num_s in RULE_REF_RE.findall(txt):
            if prefix in known_prefixes:
                ref_id = f"{prefix}-{int(num_s)}"
                if ref_id not in valid_rule_ids:
                    issues.append(Issue("ERROR",
                        f"{rel}: ссылка на несуществующее правило {ref_id} "
                        f"(нет в AGENTS.md)."))


def report(issues, tz_ids, all_covered, uncovered, project_dir):
    errors = [i for i in issues if i.severity == "ERROR"]
    warns = [i for i in issues if i.severity == "WARN"]

    print(f"\n{'='*62}")
    print(f"  ПРОВЕРКА ПОКРЫТИЯ ТЗ: {project_dir}")
    print(f"{'='*62}\n")

    if tz_ids:
        covered_count = len(set(tz_ids)) - len(uncovered)
        pct = 100 * covered_count / len(set(tz_ids)) if tz_ids else 0
        print(f"Требований в ТЗ: {len(set(tz_ids))}")
        print(f"Покрыто в плане разработки: {covered_count} ({pct:.0f}%)")
        print(f"Не покрыто: {len(uncovered)}")

    print(f"\n{'-'*62}")
    print(f"Ошибок: {len(errors)}   Предупреждений: {len(warns)}")
    print(f"{'-'*62}\n")

    if errors:
        print("ОШИБКИ (блокируют переход к phase-init):\n")
        for i in errors:
            print(f"  {i.message}")
        print()

    if warns:
        print("ПРЕДУПРЕЖДЕНИЯ:\n")
        for i in warns[:40]:
            print(f"  {i.message}")
        if len(warns) > 40:
            print(f"  ... и ещё {len(warns) - 40}")
        print()

    if not errors and not warns:
        print("  Покрытие полное, механических дефектов не найдено.\n")
        print("  Это НЕ означает, что план разработки корректен по сути:")
        print("  нарезка фаз, зависимости и схема БД скриптом не")
        print("  оцениваются. Нужен sdd-review отдельной сессией.\n")

    return len(errors)


def main():
    if len(sys.argv) < 2:
        print("Использование: python3 check_sdd.py <папка-проекта> [--strict]")
        sys.exit(2)

    project_dir = sys.argv[1]
    strict = "--strict" in sys.argv

    if not os.path.isdir(project_dir):
        print(f"Папка не найдена: {project_dir}")
        sys.exit(2)

    issues, tz_ids, all_covered, uncovered = check(project_dir)
    error_count = report(issues, tz_ids, all_covered, uncovered, project_dir)

    if strict and error_count:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
