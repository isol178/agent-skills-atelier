#!/usr/bin/env python3
"""
estimate.py — 分割前の見積もりと品質チェックを行う

split.py を実行する前に必ずこのスクリプトで見積もりを確認すること。
見積もり結果をユーザーに提示し、分割レベルの妥当性を判断してから split.py を実行する。

使い方:
    python scripts/estimate.py <ファイルパス> [--level 2]
    python scripts/estimate.py <ファイルパス> --all-levels

例:
    python scripts/estimate.py docs/requirements/spec.md
    python scripts/estimate.py docs/requirements/spec.md --level 3
    python scripts/estimate.py docs/requirements/spec.md --all-levels

引数:
    file          対象のMarkdownファイルパス
    --level       見積もりする見出しレベル（デフォルト: 2）
    --all-levels  H1〜H4 の全レベルを一覧表示する（レベル選択の参考に）

出力:
    - 節数・行数分布・警告の一覧
    - 独立性リスク（節をまたぐ可能性のある参照）の一覧
    - 推奨レベルの提案
"""

import argparse
import re
import sys
from pathlib import Path


# ──────────────────────────────────────────
# 分割シミュレーション（split.py と共通ロジック）
# ──────────────────────────────────────────

def parse_sections(content: str, level: int) -> list[dict]:
    prefix = "#" * level + " "
    sections = []
    current: dict | None = None

    for line in content.splitlines(keepends=True):
        if line.startswith(prefix) and not line.startswith(prefix + "#"):
            if current is not None:
                sections.append(current)
            heading_text = line.lstrip("#").strip().rstrip("\n")
            current = {"heading": heading_text, "lines": [line]}
        else:
            if current is not None:
                current["lines"].append(line)
            elif not sections:
                sections.append({"heading": "_preamble", "lines": [line]})
                current = None
                continue

    if current is not None:
        sections.append(current)

    return sections


# ──────────────────────────────────────────
# 品質チェック
# ──────────────────────────────────────────

def check_quality(sections: list[dict]) -> list[tuple[str, str]]:
    """
    Returns list of (severity, message).
    severity: "[WARN]" | "[INFO]" | "[OK]"
    """
    results = []
    content = [s for s in sections if s["heading"] != "_preamble"]
    count = len(content)
    line_counts = [len(s["lines"]) for s in content]

    if count == 0:
        results.append(("[WARN]", "この見出しレベルでは節が見つかりません"))
        return results

    if count <= 2:
        results.append(("[WARN]", f"節数が{count}個と少ない → より細かいレベルを推奨"))
    elif count >= 30:
        results.append(("[WARN]", f"節数が{count}個と多すぎる → より粗いレベルを推奨"))
    else:
        results.append(("[OK]", f"節数 {count}個（適切）"))

    tiny = sum(1 for n in line_counts if n < 10)
    if count > 0 and tiny / count >= 0.5:
        results.append(("[WARN]", f"節の{tiny}/{count}個が10行未満 → レベルを1段上げることを推奨"))
    else:
        results.append(("[OK]", f"10行未満の節: {tiny}/{count}個"))

    large = [(s["heading"], len(s["lines"])) for s in content if len(s["lines"]) > 300]
    for h, n in large:
        results.append(("[INFO]", f"「{h}」は{n}行 → 参照時のトークン量に注意"))

    return results


# ──────────────────────────────────────────
# 独立性リスク検出
# ──────────────────────────────────────────

def detect_cross_refs(sections: list[dict]) -> list[dict]:
    """
    節をまたぐ可能性のある参照パターンを検出する。

    検出対象：
    - 「上記」「前述」「以下」「後述」「§N」「第N節」のような相対参照
    - 他の節の見出しテキストへの言及（# を含まない参照）

    Returns list of {
        "section": str,
        "line_no": int,      # 節内の行番号（1始まり）
        "line": str,
        "reason": str,
    }
    """
    content_sections = [s for s in sections if s["heading"] != "_preamble"]
    heading_texts = [s["heading"] for s in content_sections]

    # 相対参照パターン
    relative_patterns = [
        (r"上記|前述|前節|前章", "上位/前への相対参照"),
        (r"以下|後述|後節|後章|次節|次章", "下位/後への相対参照"),
        (r"§\s*\d+|第\s*\d+\s*[節章条項]", "節番号による直接参照"),
        (r"\(\s*[再参照|参照]\s*\)", "再参照マーカー"),
    ]

    risks = []
    for section in content_sections:
        for i, line in enumerate(section["lines"], start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            for pattern, reason in relative_patterns:
                if re.search(pattern, stripped):
                    risks.append({
                        "section": section["heading"],
                        "line_no": i,
                        "line": stripped[:100],
                        "reason": reason,
                    })
                    break  # 1行につき1件

            # 他節の見出しテキストへの言及（20文字以上のもの）
            for other_heading in heading_texts:
                if other_heading == section["heading"]:
                    continue
                if len(other_heading) >= 10 and other_heading in stripped:
                    risks.append({
                        "section": section["heading"],
                        "line_no": i,
                        "line": stripped[:100],
                        "reason": f"他節「{other_heading[:30]}」への言及",
                    })
                    break

    return risks


# ──────────────────────────────────────────
# レポート出力
# ──────────────────────────────────────────

def report_level(content: str, level: int, source_name: str) -> bool:
    """
    指定レベルの見積もりレポートを表示する。
    Returns True if no blocking warnings.
    """
    sections = parse_sections(content, level)
    content_sections = [s for s in sections if s["heading"] != "_preamble"]

    print(f"\n{'='*60}")
    print(f"  H{level} 分割見積もり — {source_name}")
    print(f"{'='*60}")

    if not content_sections:
        print(f"  （H{level} の見出しが存在しません）")
        return False

    # 節一覧
    print(f"\n  節一覧（{len(content_sections)}節）\n")
    for s in content_sections:
        bar = "#" * min(len(s["lines"]) // 10, 30)
        print(f"  {len(s['lines']):4}行  {bar}  {s['heading']}")

    # 統計
    line_counts = [len(s["lines"]) for s in content_sections]
    print(f"\n  統計")
    print(f"    節数:     {len(content_sections)}")
    print(f"    最小行数: {min(line_counts)}")
    print(f"    最大行数: {max(line_counts)}")
    print(f"    平均行数: {sum(line_counts) // len(line_counts)}")

    # 品質チェック
    print(f"\n  品質チェック")
    checks = check_quality(sections)
    has_warning = False
    for severity, msg in checks:
        print(f"    {severity}  {msg}")
        if "[WARN]" in severity:
            has_warning = True

    # 独立性リスク
    risks = detect_cross_refs(sections)
    print(f"\n  独立性リスク（節をまたぐ可能性のある参照）")
    if not risks:
        print("    [OK]  検出なし")
    else:
        print(f"    [WARN]  {len(risks)}件検出\n")
        for r in risks[:10]:  # 最大10件表示
            print(f"    節「{r['section'][:30]}」 行{r['line_no']}: {r['reason']}")
            print(f"      → {r['line'][:80]}")
        if len(risks) > 10:
            print(f"    ... 他 {len(risks) - 10} 件")

    return not has_warning


def report_all_levels(content: str, source_name: str) -> None:
    """H1〜H4 の全レベルを比較表示する。"""
    print(f"\n{'='*60}")
    print(f"  全レベル比較 — {source_name}")
    print(f"{'='*60}")
    print(f"\n  {'レベル':<8} {'節数':>4}  {'最小行':>6}  {'最大行':>6}  {'平均行':>6}  警告")
    print(f"  {'-'*55}")

    for level in range(1, 5):
        sections = parse_sections(content, level)
        content_sections = [s for s in sections if s["heading"] != "_preamble"]
        if not content_sections:
            print(f"  H{level}        {'—':>4}  {'—':>6}  {'—':>6}  {'—':>6}  (見出しなし)")
            continue

        line_counts = [len(s["lines"]) for s in content_sections]
        checks = check_quality(sections)
        warnings = [m for sev, m in checks if "[WARN]" in sev]
        warn_str = f"[WARN]{warnings[0]}" if warnings else "[OK]"

        print(
            f"  H{level}  "
            f"{len(content_sections):>8}  "
            f"{min(line_counts):>6}  "
            f"{max(line_counts):>6}  "
            f"{sum(line_counts)//len(line_counts):>6}  "
            f"{warn_str}"
        )

    print(f"\n  詳細確認: python scripts/estimate.py {source_name} --level <N>")


# ──────────────────────────────────────────
# エントリポイント
# ──────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Markdown分割の見積もりと品質チェック")
    parser.add_argument("file", help="対象のMarkdownファイルパス")
    parser.add_argument("--level", type=int, default=2, help="見積もりする見出しレベル（デフォルト: 2）")
    parser.add_argument("--all-levels", action="store_true", help="H1〜H4の全レベルを比較表示")
    args = parser.parse_args()

    source = Path(args.file)
    if not source.exists():
        print(f"エラー: ファイルが見つかりません: {source}", file=sys.stderr)
        sys.exit(1)

    content = source.read_text(encoding="utf-8")

    if args.all_levels:
        report_all_levels(content, source.name)
        print(f"\n  次のステップ: python scripts/estimate.py {source} --level <N> で詳細確認")
    else:
        ok = report_level(content, args.level, source.name)
        if ok:
            print(f"\n  次のステップ: python scripts/split.py {source} --level {args.level}")
        else:
            print(f"\n  警告あり。--all-levels で他のレベルも確認することを推奨。")
            print(f"  強制実行: python scripts/split.py {source} --level {args.level}")


if __name__ == "__main__":
    main()
