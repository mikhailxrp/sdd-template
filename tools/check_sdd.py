#!/usr/bin/env python3
"""
Валидатор покрытия ТЗ в SDD-документации.

Проверяет, что каждое требование из готового ТЗ (00-input/tz.md) —
FR-*, BR-* (включая BR-AI-*) и NFR-* в полном (заголовки) и табличном
форматах (согласовано с tz-template/tools/check_tz.py) — учтено в карте
покрытия (.docs/tz-coverage.md) и доведено до исполнения:
  - FR-* : обязательно в tz-coverage.md И назначено фазе в
           .docs/phases/_status.md (или .docs/phases/phase-*.md)
  - BR-* : обязательно в tz-coverage.md И назначено фазе либо явно
           закреплено в сквозном артефакте (database.md, dod-global.md,
           planning-log.md, AGENTS.md, modules/)
  - NFR-*: обязательно в tz-coverage.md с конкретным механизмом обеспечения
           и способом проверки; при назначении в фазу — проверяется наличие
           в _status.md / phase-*.md

Это обратная проверка относительно check_tz.py: там проверялось
"весь ли бриф попал в ТЗ", здесь — "всё ли ТЗ попало в план разработки
и сквозной контроль".

Использование:
    python3 check_sdd.py <папка-проекта>
    python3 check_sdd.py <папка-проекта> --strict
"""

import glob
import os
import re
import sys
from collections import Counter

# --- Паттерны извлечения ID (согласованы с tz-template/tools/check_tz.py) ---

# Полный формат: ### FR-CHK-012/Б · Название | ### NFR-PERF-001/Б · ... | ### BR-003/Р · ...
REQ_HEADER_RE = re.compile(
    r"^###\s+((?:FR-[A-Z][A-Z0-9]*|NFR-[A-Z]+|BR(?:-AI)?)-\d{3})(?:/[БР_])?\s*·"
)

# Табличный формат: | FR-CAT-005/Б | текст | ... |  (допускает обратные кавычки/жирный в 1-й ячейке)
TABLE_REQ_RE = re.compile(
    r"^\|\s*[`*]*"
    r"((?:FR-[A-Z][A-Z0-9]*|NFR-[A-Z]+|BR(?:-AI)?)-\d{3})"
    r"(?:/[БР_])?[`*]*\s*\|(.+)\|"
)

# Упоминания и сжатые диапазоны в документации SDD
RANGE_ANCHOR = re.compile(
    r"\b(FR-[A-Z][A-Z0-9]*|NFR-[A-Z]+|BR(?:-AI)?)-(\d{3})\b"
)

# Сегменты сжатой нотации после якоря:
#   - многоточие / двойная точка допускают необязательные пробелы: FR-CAT-001…005, FR-CAT-001..005
#   - дефис / короткое тире — только без пробелов, чтобы не хватать «FR-AUTH-001 - 404 ошибка»
#     или «NFR-PERF-001 – 200 мс» как диапазон на сотни фиктивных ID
#   - запятая с 3-значным хвостом: FR-ADM-001…002, 005, 008
SEGMENT = re.compile(
    r"(?:\s*(?:…|\.\.)\s*|[-–])(\d{3})(?![A-Za-zА-Яа-яЁё0-9])"
    r"|\s*,\s*(\d{3})(?![A-Za-zА-Яа-яЁё0-9])"
)

PHASE_REF_RE = re.compile(
    r"(?:фаз[аеуы]\s*\d+|phase[\s_-]*\d+|\bф\.?\s*\d+)",
    re.IGNORECASE,
)

VERIFY_HINT_RE = re.compile(
    r"(?:проверк|тест|audit-|curl|dod-check|dod-global|dod\b|замер|мониторинг|"
    r"view-source|phpcs|phpunit|pest|pint|лог|скрипт|бэкап|ручн|автотест|"
    r"lighthouse|ttfb|чек-?лист|метрик|индекс|explain|нагруз|скан|verify|check)",
    re.IGNORECASE,
)

DOC_FILE_REF_RE = re.compile(
    r"(?:\.docs/)?"
    r"(dod-global\.md|database\.md|planning-log\.md|capabilities\.md|prd\.md|"
    r"AGENTS\.md|rules/[a-z0-9_-]+\.md|modules/[a-z0-9_-]+\.md)",
    re.IGNORECASE,
)

EMPTY_VALUES = {"", "-", "—", "–", "?", "нет", "none", "tbd", "todo", "н/д"}


class Issue:
    def __init__(self, severity, message):
        self.severity = severity  # ERROR | WARN
        self.message = message


def req_kind(rid):
    if rid.startswith("NFR-"):
        return "NFR"
    if rid.startswith("BR-"):
        return "BR"
    return "FR"


def extract_ids_from_tz(path):
    """Извлекает все FR-*, BR-* и NFR-* из заголовков и таблиц tz.md (вне код-блоков)."""
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()
    ids = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = REQ_HEADER_RE.match(stripped)
        if m:
            ids.append(m.group(1))
            continue
        tm = TABLE_REQ_RE.match(stripped)
        if tm:
            ids.append(tm.group(1))
    return ids


def extract_mentions(text):
    """
    Все ID (FR-*, BR-*, NFR-*), упомянутые в тексте (для coverage/phases/артефактов).

    Разворачивает сжатую нотацию диапазонов, которую документация
    намеренно использует вместо построчного перечисления каждого ID:

        FR-AUTH-001…005              -> 001, 002, 003, 004, 005
        FR-AUTH-001–005              -> 001, 002, 003, 004, 005
        FR-ADM-001…002, 005, 008     -> 001, 002, 005, 008
        FR-CARD-001…005, 007…009     -> 001..005, 007..009
        NFR-PERF-001…003             -> 001, 002, 003
    """
    ids = set()
    for m in RANGE_ANCHOR.finditer(text):
        prefix, first_num = m.group(1), m.group(2)
        ids.add(f"{prefix}-{first_num}")

        pos = m.end()
        last_num = int(first_num)
        while True:
            sm = SEGMENT.match(text, pos)
            if not sm:
                break
            range_end, single = sm.group(1), sm.group(2)
            if range_end:
                end_num = int(range_end)
                if end_num >= last_num and (end_num - last_num) <= 200:
                    for n in range(last_num, end_num + 1):
                        ids.add(f"{prefix}-{n:03d}")
                    last_num = end_num
                else:
                    break
            else:
                ids.add(f"{prefix}-{single}")
                last_num = int(single)
            pos = sm.end()

    return ids


def _is_empty_cell(val):
    return val.strip().strip("`*_ ").lower() in EMPTY_VALUES


def parse_coverage_entries(coverage_text):
    """
    Разбирает таблицы .docs/tz-coverage.md по строкам.

    Поддерживает форматы:
      3 колонки: | Раздел/ID ТЗ | Куда пошло | Статус |
      4 колонки: | Раздел/ID ТЗ | Механизм обеспечения / Куда пошло | Способ проверки | Статус |

    Возвращает dict: rid -> list[entry], где entry содержит target, verify, status, has_verify_col.
    """
    entries = {}
    in_code = False
    has_verify_col = False

    for line in coverage_text.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not s.startswith("|"):
            has_verify_col = False
            continue

        cols = [c.strip() for c in s.strip("|").split("|")]
        if len(cols) < 2:
            continue

        # Строка-разделитель таблицы |---|---|...|
        if all(set(c.replace(":", "").replace(" ", "")) <= {"-"} and c for c in cols):
            continue

        # Заголовок таблицы — определяем, есть ли отдельная колонка «Способ проверки»
        first_l = cols[0].lower()
        if any(h in first_l for h in ("раздел", "id тз", "требован")):
            has_verify_col = len(cols) >= 4 and any(
                "проверк" in c.lower() or "верифик" in c.lower() for c in cols[2:-1]
            )
            continue

        row_ids = extract_mentions(cols[0])
        if not row_ids:
            continue

        target = cols[1] if len(cols) >= 2 else ""
        if has_verify_col and len(cols) >= 4:
            verify = cols[2]
            status = cols[3]
        elif len(cols) >= 4:
            # 4-колоночная таблица без явного заголовка со словом «проверка»
            verify = cols[2]
            status = cols[3]
        else:
            verify = ""
            status = cols[2] if len(cols) >= 3 else ""

        entry = {
            "target": target,
            "verify": verify,
            "status": status,
            "has_verify_col": has_verify_col or len(cols) >= 4,
            "raw": s,
        }
        for rid in row_ids:
            entries.setdefault(rid, []).append(entry)

    return entries


def _collect_phase_mentions(project_dir):
    """
    Собирает упоминания ID из плана фаз:
      - .docs/phases/_status.md (существует сразу после sdd-roadmap, до phase-init)
      - .docs/phases/phase-*.md (кроме шаблона phase-example.md)
    """
    phases_dir = os.path.join(project_dir, ".docs", "phases")
    mentions = set()
    files_read = []
    if not os.path.isdir(phases_dir):
        return mentions, files_read

    for pf in sorted(glob.glob(os.path.join(phases_dir, "*.md"))):
        base = os.path.basename(pf).lower()
        if base == "phase-example.md" or base.endswith("-example.md"):
            continue
        files_read.append(pf)
        mentions |= extract_mentions(open(pf, encoding="utf-8").read())

    return mentions, files_read


def _collect_crosscutting_mentions(project_dir):
    """
    Собирает упоминания ID из сквозных артефактов проекта
    (dod-global.md, database.md, planning-log.md, capabilities.md, AGENTS.md,
    .docs/rules/*.md, .docs/modules/*.md).
    """
    candidates = [
        os.path.join(project_dir, "AGENTS.md"),
        os.path.join(project_dir, ".docs", "dod-global.md"),
        os.path.join(project_dir, ".docs", "database.md"),
        os.path.join(project_dir, ".docs", "planning-log.md"),
        os.path.join(project_dir, ".docs", "capabilities.md"),
        os.path.join(project_dir, ".docs", "prd.md"),
    ]
    for sub in ("rules", "modules"):
        sub_dir = os.path.join(project_dir, ".docs", sub)
        if os.path.isdir(sub_dir):
            candidates.extend(sorted(glob.glob(os.path.join(sub_dir, "*.md"))))

    mentions = set()
    for fp in candidates:
        if os.path.isfile(fp):
            mentions |= extract_mentions(open(fp, encoding="utf-8").read())
    return mentions


def _resolve_doc_ref(project_dir, ref_name):
    """Проверяет, существует ли упомянутый в tz-coverage.md файл артефакта."""
    ref_norm = ref_name.replace("\\", "/")
    if ref_norm.upper() == "AGENTS.MD":
        return os.path.isfile(os.path.join(project_dir, "AGENTS.md"))
    if os.path.isfile(os.path.join(project_dir, ".docs", ref_norm)):
        return True
    if os.path.isfile(os.path.join(project_dir, ref_norm)):
        return True
    return False


def check(project_dir):
    issues = []
    stats = {
        "fr_br_total": 0,
        "fr_br_covered": 0,
        "nfr_total": 0,
        "nfr_covered": 0,
    }

    tz_path = os.path.join(project_dir, "00-input", "tz.md")
    tz_ids = extract_ids_from_tz(tz_path)

    if tz_ids is None:
        issues.append(Issue("ERROR",
            f"Не найден {tz_path} — нечего проверять на покрытие. "
            f"Скопируй готовое ТЗ в 00-input/tz.md."))
        return issues, [], set(), set(), stats

    if not tz_ids:
        issues.append(Issue("WARN",
            "В tz.md не найдено ни одного FR-*/BR-*/NFR-* — проверь, тот ли файл."))

    coverage_path = os.path.join(project_dir, ".docs", "tz-coverage.md")
    coverage_text = ""
    if os.path.exists(coverage_path):
        coverage_text = open(coverage_path, encoding="utf-8").read()
    else:
        issues.append(Issue("ERROR",
            ".docs/tz-coverage.md не найден — запусти хотя бы sdd-init."))

    coverage_mentions = extract_mentions(coverage_text)
    coverage_entries = parse_coverage_entries(coverage_text)

    # План фаз (_status.md + phase-*.md без phase-example.md)
    phases_mentions, _ = _collect_phase_mentions(project_dir)

    # Сквозные артефакты (dod-global.md, database.md, planning-log.md, modules/, rules/, AGENTS.md)
    crosscutting_mentions = _collect_crosscutting_mentions(project_dir)

    # Дубли ID в самом ТЗ
    dup = [rid for rid, c in Counter(tz_ids).items() if c > 1]
    if dup:
        issues.append(Issue("WARN",
            f"В tz.md повторяются ID: {', '.join(dup[:10])} — "
            f"это должно было поймать check_tz.py на этапе ТЗ."))

    unique_tz_ids = sorted(set(tz_ids))
    covered_ids = set()
    uncovered_ids = set()

    for rid in unique_tz_ids:
        kind = req_kind(rid)
        if kind == "NFR":
            stats["nfr_total"] += 1
        else:
            stats["fr_br_total"] += 1

        in_cov = rid in coverage_mentions
        entries = coverage_entries.get(rid, [])
        in_phases = rid in phases_mentions
        in_crosscutting = rid in crosscutting_mentions

        # Оценка строк tz-coverage.md для этого ID
        has_valid_cov_entry = False
        explicitly_uncovered = False
        cov_claims_phase = False
        cov_has_verify = False
        cov_missing_verify_col = False
        missing_ref_files = set()

        for e in entries:
            status_l = e["status"].lower()
            target = e["target"]
            verify = e["verify"]

            if "не покрыто" in status_l or _is_empty_cell(target):
                explicitly_uncovered = True
                continue

            has_valid_cov_entry = True
            if PHASE_REF_RE.search(target):
                cov_claims_phase = True

            if e["has_verify_col"]:
                if not _is_empty_cell(verify):
                    cov_has_verify = True
                else:
                    cov_missing_verify_col = True
            else:
                if VERIFY_HINT_RE.search(e["raw"]):
                    cov_has_verify = True

            for m in DOC_FILE_REF_RE.finditer(target):
                ref_name = m.group(1)
                if not _resolve_doc_ref(project_dir, ref_name):
                    missing_ref_files.add(ref_name)

        # Если ID упомянут в tz-coverage.md вне таблицы (например списком) —
        # не считаем отсутствующим в карте, но для строгих проверок предпочитаем таблицу
        cov_ok = has_valid_cov_entry or (in_cov and not entries)

        if kind == "FR":
            # FR обязателен И в карте покрытия, И в плане фаз (_status.md / phase-*.md)
            fr_errors = []
            if not in_cov:
                fr_errors.append(
                    f"{rid}: есть в tz.md, но отсутствует в .docs/tz-coverage.md"
                )
            elif explicitly_uncovered and not has_valid_cov_entry:
                fr_errors.append(
                    f"{rid}: в .docs/tz-coverage.md помечено как непокрытое или без назначения"
                )

            if not in_phases:
                if in_cov:
                    fr_errors.append(
                        f"{rid}: есть в .docs/tz-coverage.md, но не назначено ни одной фазе "
                        f"в .docs/phases/_status.md (или phase-*.md) — требование потеряется"
                    )
                else:
                    fr_errors.append(
                        f"{rid}: не назначено ни одной фазе в .docs/phases/_status.md "
                        f"(или phase-*.md) — требование потеряется"
                    )

            for msg in fr_errors:
                issues.append(Issue("ERROR", msg))

            if not fr_errors:
                covered_ids.add(rid)
                stats["fr_br_covered"] += 1
            else:
                uncovered_ids.add(rid)

        elif kind == "BR":
            # BR обязателен в карте покрытия И (в фазах ЛИБО в явном сквозном контроле)
            br_errors = []
            if not in_cov:
                br_errors.append(
                    f"{rid}: есть в tz.md, но отсутствует в .docs/tz-coverage.md"
                )
            elif explicitly_uncovered and not has_valid_cov_entry:
                br_errors.append(
                    f"{rid}: в .docs/tz-coverage.md помечено как непокрытое или без назначения"
                )

            if cov_claims_phase and not in_phases:
                br_errors.append(
                    f"{rid}: в .docs/tz-coverage.md назначено фазе, но отсутствует "
                    f"в .docs/phases/_status.md (или phase-*.md)"
                )
            elif not in_phases and not in_crosscutting:
                br_errors.append(
                    f"{rid}: не назначено фазе в _status.md/phase-*.md и не закреплено "
                    f"в сквозных документах (database.md, dod-global.md, planning-log.md, modules/)"
                )

            for rf in sorted(missing_ref_files):
                br_errors.append(
                    f"{rid}: в .docs/tz-coverage.md указан несуществующий файл '{rf}'"
                )

            for msg in br_errors:
                issues.append(Issue("ERROR", msg))

            if not br_errors:
                covered_ids.add(rid)
                stats["fr_br_covered"] += 1
            else:
                uncovered_ids.add(rid)

        else:  # NFR
            # NFR -> карта покрытия -> конкретный механизм обеспечения -> способ проверки.
            # Привязка к фазе обязательна только если в tz-coverage.md указана фаза.
            nfr_errors = []
            if not in_cov:
                nfr_errors.append(
                    f"{rid}: есть в tz.md, но отсутствует в .docs/tz-coverage.md "
                    f"(нужен механизм обеспечения и способ проверки)"
                )
            elif explicitly_uncovered and not has_valid_cov_entry:
                nfr_errors.append(
                    f"{rid}: в .docs/tz-coverage.md помечено как непокрытое или не указан "
                    f"механизм обеспечения"
                )
            else:
                if cov_claims_phase and not in_phases:
                    nfr_errors.append(
                        f"{rid}: в .docs/tz-coverage.md для NFR запланирована фаза, "
                        f"но ID отсутствует в .docs/phases/_status.md (или phase-*.md)"
                    )
                for rf in sorted(missing_ref_files):
                    nfr_errors.append(
                        f"{rid}: в .docs/tz-coverage.md указан несуществующий файл '{rf}'"
                    )
                if cov_missing_verify_col and not cov_has_verify:
                    nfr_errors.append(
                        f"{rid}: в .docs/tz-coverage.md не заполнен способ проверки NFR"
                    )
                elif not cov_has_verify and not in_phases and not in_crosscutting:
                    issues.append(Issue("WARN",
                        f"{rid}: в .docs/tz-coverage.md указан механизм обеспечения, но не "
                        f"очевиден способ проверки (добавь колонку «Способ проверки» или явно "
                        f"укажи проверку, например audit-*/curl/DoD)"))

            for msg in nfr_errors:
                issues.append(Issue("ERROR", msg))

            if not nfr_errors:
                covered_ids.add(rid)
                stats["nfr_covered"] += 1
            else:
                uncovered_ids.add(rid)

    # Обратная проверка: упоминания в фазах, модулях и карте покрытия, которых нет в ТЗ
    modules_mentions = set()
    modules_dir = os.path.join(project_dir, ".docs", "modules")
    if os.path.isdir(modules_dir):
        for mf in glob.glob(os.path.join(modules_dir, "*.md")):
            modules_mentions |= extract_mentions(open(mf, encoding="utf-8").read())

    dangling = sorted(
        rid for rid in (phases_mentions | modules_mentions | coverage_mentions) - set(tz_ids)
        if not rid.endswith("-000")
    )
    for rid in dangling:
        issues.append(Issue("WARN",
            f"{rid}: упомянуто в SDD-документации (tz-coverage/фазы/модули), "
            f"но не найдено в tz.md — опечатка в ID или устаревшая ссылка"))

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

    return issues, tz_ids, covered_ids, sorted(uncovered_ids), stats


CAP_BEGIN_RE = re.compile(r"<!--\s*capability:([a-z0-9-]+):begin\s*-->")
CAP_END_RE = re.compile(r"<!--\s*capability:([a-z0-9-]+):end\s*-->")
CAP_ANCHOR_RE = re.compile(r"<!--\s*sdd-capabilities:")
RULE_DEF_RE = re.compile(r"^\s*\d+\.\s+\*\*([A-Z]{2,5})-(\d+)\.\*\*", re.MULTILINE)
RULE_REF_RE = re.compile(r"\b([A-Z]{2,5})-(\d+)\b")


def _parse_prd_capabilities(prd_path):
    """Читает таблицу «Возможности» из .docs/prd.md -> (enabled, disabled, undecided, raw_rows)."""
    if not os.path.exists(prd_path):
        return [], [], [], []
    text = open(prd_path, encoding="utf-8").read()
    m = re.search(r"^##\s+Возможности\b.*$", text, re.MULTILINE)
    if not m:
        return [], [], [], []
    section = text[m.end():]
    next_h2 = re.search(r"^##\s+", section, re.MULTILINE)
    if next_h2:
        section = section[:next_h2.start()]

    enabled, disabled, undecided, rows = [], [], [], []
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
        else:
            undecided.append((name, cols[1]))
    return enabled, disabled, undecided, rows


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

    enabled, disabled, undecided, _ = _parse_prd_capabilities(prd_path)

    for name, raw_status in undecided:
        issues.append(Issue("ERROR",
            f".docs/prd.md: у пакета '{name}' не выбран статус ('{raw_status}') "
            f"— укажи явно «вкл» или «выкл»."))

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


def report(issues, tz_ids, all_covered, uncovered, stats, project_dir):
    errors = [i for i in issues if i.severity == "ERROR"]
    warns = [i for i in issues if i.severity == "WARN"]

    print(f"\n{'='*62}")
    print(f"  ПРОВЕРКА ПОКРЫТИЯ ТЗ: {project_dir}")
    print(f"{'='*62}\n")

    if tz_ids:
        total = len(set(tz_ids))
        covered_count = total - len(uncovered)
        pct = 100 * covered_count / total if total else 0
        print(f"Требований в ТЗ: {total}  (FR/BR: {stats['fr_br_total']}, NFR: {stats['nfr_total']})")
        print(f"Покрыто в SDD:   {covered_count} ({pct:.0f}%)"
              f"  [FR/BR: {stats['fr_br_covered']}/{stats['fr_br_total']},"
              f" NFR: {stats['nfr_covered']}/{stats['nfr_total']}]")
        print(f"Не покрыто:      {len(uncovered)}")

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

    issues, tz_ids, all_covered, uncovered, stats = check(project_dir)
    error_count = report(issues, tz_ids, all_covered, uncovered, stats, project_dir)

    if strict and error_count:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
