#!/usr/bin/env python3
"""
ADR ファイルのフォーマットと構造を検証する。

使い方:
    python scripts/validate_adr.py docs/decisions/0001-use-iam-db-auth.md
    python scripts/validate_adr.py docs/decisions/        # ディレクトリ内の全 ADR を検証
    python scripts/validate_adr.py --strict <path>         # warning も error として扱う

終了コード:
    0: 全件 pass
    1: 1件以上 error
    2: --strict 指定時に warning があった

検証項目:
    [Front Matter]
    - YAML front matter の存在と構文妥当性
    - 必須キー: status, date, decision-makers
    - status の値が許容セットに含まれる
    - date が ISO 8601 (YYYY-MM-DD) 形式

    [構造]
    - "# NNNN. <タイトル>" 形式の H1 タイトル行
    - 必須セクション: Context and Problem Statement / Decision Drivers /
                    Considered Options / Decision Outcome / Consequences

    [品質ゲート]
    - Considered Options が最低2項目
    - Consequences に "Bad, because" が最低1項目
    - Context and Problem Statement が空でない

    [警告のみ(--strict で error 化)]
    - Confirmation セクションが存在しない
    - 起票シグナルコメント(<!-- 起票シグナル: ... -->)が存在しない
    - More Information に Confidence の記載がない
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML が必要です。`pip install pyyaml` でインストールしてください。",
        file=sys.stderr,
    )
    sys.exit(1)


VALID_STATUSES = {"proposed", "accepted", "rejected", "deprecated"}
SUPERSEDED_PATTERN = re.compile(r"^superseded by \d{4}$")

REQUIRED_SECTIONS = [
    "Context and Problem Statement",
    "Decision Drivers",
    "Considered Options",
    "Decision Outcome",
    "Consequences",
]

OPTIONAL_BUT_RECOMMENDED = [
    "Confirmation",
]


class Issue:
    """検証で見つかった問題を表す。level は 'error' | 'warning'。"""

    def __init__(self, level: str, message: str):
        self.level = level
        self.message = message

    def __str__(self) -> str:
        prefix = "ERROR" if self.level == "error" else "WARN "
        return f"  [{prefix}] {self.message}"


def parse_front_matter(content: str) -> tuple[dict | None, str, list[Issue]]:
    """front matter を抽出して dict として返す。本文も併せて返す。"""
    issues: list[Issue] = []

    if not content.startswith("---"):
        issues.append(Issue("error", "YAML front matter が見つからない(--- で始まっていない)"))
        return None, content, issues

    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        issues.append(Issue("error", "front matter の終端 (---) が見つからない"))
        return None, content, issues

    fm_text = match.group(1)
    body = match.group(2)

    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as e:
        issues.append(Issue("error", f"front matter の YAML 構文エラー: {e}"))
        return None, body, issues

    if not isinstance(fm, dict):
        issues.append(Issue("error", "front matter は YAML マッピングである必要がある"))
        return None, body, issues

    return fm, body, issues


def validate_front_matter(fm: dict) -> list[Issue]:
    issues: list[Issue] = []

    # 必須キー
    for key in ("status", "date", "decision-makers"):
        if key not in fm:
            issues.append(Issue("error", f"front matter に必須キー '{key}' がない"))

    # status の値
    if "status" in fm:
        status = fm["status"]
        if not isinstance(status, str):
            issues.append(Issue("error", f"status は文字列である必要がある: {status!r}"))
        elif status not in VALID_STATUSES and not SUPERSEDED_PATTERN.match(status):
            issues.append(
                Issue(
                    "error",
                    f"status の値が不正: {status!r} "
                    f"(許容値: {sorted(VALID_STATUSES)} または 'superseded by NNNN')",
                )
            )

    # date の形式
    if "date" in fm:
        date_val = fm["date"]
        # YAML が自動で date 型に変換することがあるので両方許容
        date_str = date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val)
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            issues.append(
                Issue("error", f"date は YYYY-MM-DD 形式である必要がある: {date_val!r}")
            )

    # decision-makers が空でない
    if "decision-makers" in fm:
        dm = fm["decision-makers"]
        if not dm or (isinstance(dm, list) and len(dm) == 0):
            issues.append(Issue("error", "decision-makers が空"))

    return issues


def validate_structure(body: str) -> list[Issue]:
    issues: list[Issue] = []

    # H1 タイトル行
    title_match = re.search(r"^# (\d{4})\. (.+)$", body, re.MULTILINE)
    if not title_match:
        issues.append(
            Issue("error", "H1 タイトル行 '# NNNN. <タイトル>' が見つからない")
        )
    else:
        title_text = title_match.group(2).strip()
        if not title_text or title_text.startswith("{"):
            issues.append(
                Issue("error", f"タイトルが未記入またはプレースホルダーのまま: {title_text!r}")
            )

    # 起票シグナルコメント(警告レベル)
    if not re.search(r"<!--\s*起票シグナル:", body):
        issues.append(
            Issue("warning", "起票シグナルコメント '<!-- 起票シグナル: ... -->' が見つからない")
        )

    # 必須セクション
    for section in REQUIRED_SECTIONS:
        # ## Section Name または ### Section Name にマッチ
        pattern = rf"^#{{2,3}}\s+{re.escape(section)}\s*$"
        if not re.search(pattern, body, re.MULTILINE):
            issues.append(Issue("error", f"必須セクション '{section}' が見つからない"))

    # 推奨セクション(警告レベル)
    for section in OPTIONAL_BUT_RECOMMENDED:
        pattern = rf"^#{{2,3}}\s+{re.escape(section)}\s*$"
        if not re.search(pattern, body, re.MULTILINE):
            issues.append(
                Issue("warning", f"推奨セクション '{section}' が見つからない")
            )

    return issues


def extract_section(body: str, section_name: str) -> str:
    """指定セクションの本文を抽出する。次の同レベル以上の見出しまで。"""
    pattern = rf"^(#{{2,3}})\s+{re.escape(section_name)}\s*$"
    match = re.search(pattern, body, re.MULTILINE)
    if not match:
        return ""

    level = len(match.group(1))
    start = match.end()

    # 次の同レベル以上の見出しを探す
    next_pattern = rf"^#{{1,{level}}}\s+\S"
    next_match = re.search(next_pattern, body[start:], re.MULTILINE)
    end = start + next_match.start() if next_match else len(body)

    return body[start:end].strip()


def count_list_items(text: str) -> int:
    """箇条書き項目数を数える(プレースホルダーや HTML コメントは除外)。"""
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        # `-` で始まる行
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        # プレースホルダー除外
        if item.startswith("{") and item.endswith("}"):
            continue
        # コメント行除外
        if item.startswith("<!--"):
            continue
        if not item:
            continue
        count += 1
    return count


def validate_quality_gates(body: str) -> list[Issue]:
    issues: list[Issue] = []

    # Context and Problem Statement が実質的に空でない
    context = extract_section(body, "Context and Problem Statement")
    # コメントとプレースホルダーを除いた実質コンテンツ
    context_stripped = re.sub(r"<!--.*?-->", "", context, flags=re.DOTALL).strip()
    context_stripped = re.sub(r"\{[A-Z_0-9]+\}", "", context_stripped).strip()
    if not context_stripped:
        issues.append(Issue("error", "Context and Problem Statement が空"))

    # Considered Options が最低2項目
    options = extract_section(body, "Considered Options")
    n_options = count_list_items(options)
    if n_options < 2:
        issues.append(
            Issue(
                "error",
                f"Considered Options が {n_options} 項目しかない(最低2項目必要)",
            )
        )

    # Consequences に Bad, because が最低1項目
    consequences = extract_section(body, "Consequences")
    bad_items = re.findall(
        r"^- Bad, because\s+(.+)$", consequences, re.MULTILINE | re.IGNORECASE
    )
    bad_real = [
        item for item in bad_items if not (item.strip().startswith("{") and item.strip().endswith("}"))
    ]
    if len(bad_real) < 1:
        issues.append(
            Issue(
                "error",
                "Consequences に 'Bad, because ...' が最低1項目必要(プレースホルダーは無効)",
            )
        )

    # More Information に Confidence の記載(警告)
    more_info = extract_section(body, "More Information")
    if more_info and not re.search(r"\*\*Confidence\*\*\s*:", more_info):
        issues.append(
            Issue("warning", "More Information に Confidence の記載がない")
        )

    return issues


def validate_file(path: Path) -> list[Issue]:
    """1ファイルを検証する。"""
    issues: list[Issue] = []

    if not path.exists():
        return [Issue("error", f"ファイルが存在しない: {path}")]

    content = path.read_text(encoding="utf-8")

    fm, body, fm_issues = parse_front_matter(content)
    issues.extend(fm_issues)

    if fm is not None:
        issues.extend(validate_front_matter(fm))

    issues.extend(validate_structure(body))
    issues.extend(validate_quality_gates(body))

    return issues


def collect_targets(target: Path) -> list[Path]:
    """対象パス(ファイル or ディレクトリ)から検証対象ファイルを収集する。"""
    if target.is_file():
        return [target]
    if target.is_dir():
        files = sorted(target.glob("*.md"))
        # README.md などを除外したい場合のため、NNNN- で始まるものに限定
        adr_pattern = re.compile(r"^\d{4}-")
        return [f for f in files if adr_pattern.match(f.name)]
    return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ADR ファイルの形式と品質を検証する")
    parser.add_argument("path", help="検証対象のファイルまたはディレクトリ")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="warning を error として扱う(終了コード 2)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    target = Path(args.path)
    files = collect_targets(target)

    if not files:
        print(f"検証対象が見つかりません: {target}", file=sys.stderr)
        return 1

    total_errors = 0
    total_warnings = 0

    for f in files:
        issues = validate_file(f)
        errors = [i for i in issues if i.level == "error"]
        warnings = [i for i in issues if i.level == "warning"]

        if not errors and not warnings:
            print(f"OK   {f}")
        else:
            status_label = "FAIL" if errors else "WARN"
            print(f"{status_label} {f}")
            for issue in issues:
                print(issue)

        total_errors += len(errors)
        total_warnings += len(warnings)

    print()
    print(
        f"検証完了: {len(files)} ファイル / "
        f"errors: {total_errors} / warnings: {total_warnings}"
    )

    if total_errors > 0:
        return 1
    if args.strict and total_warnings > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
