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


def extract_mentions(text):
    """Все ID, упомянутые где угодно в тексте (для coverage/phases)."""
    return set(re.findall(r"\b(?:FR-[A-Z][A-Z0-9]*|BR(?:-AI)?)-\d{3}\b", text))


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

    # CLAUDE.md — плейсхолдеры
    claude_path = os.path.join(project_dir, "CLAUDE.md")
    if os.path.exists(claude_path):
        claude_text = open(claude_path, encoding="utf-8").read()
        if "< " in claude_text and " >" in claude_text:
            issues.append(Issue("WARN",
                "CLAUDE.md содержит незаполненные плейсхолдеры вида < ... > "
                "— sdd-init должен был их закрыть."))

    return issues, tz_ids, all_covered, uncovered


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
