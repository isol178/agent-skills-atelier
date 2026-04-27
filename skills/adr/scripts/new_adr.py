#!/usr/bin/env python3
"""
新規 ADR を採番してテンプレートから生成する。

使い方:
    python scripts/new_adr.py "use-iam-db-auth"
    python scripts/new_adr.py "use-iam-db-auth" --title "Use IAM authentication for DB access"
    python scripts/new_adr.py "use-iam-db-auth" --signals S1,S2 --decision-makers "Haruki,Claude"

オプション:
    --decisions-dir   ADR の格納先(デフォルト: docs/decisions)
    --title           タイトル文字列(省略時は slug から生成)
    --signals         該当する起票シグナル(カンマ区切り、例: S1,S2)
    --decision-makers 決定者(カンマ区切り、デフォルト: "Agent (via Claude Code)")
    --status          ステータス(デフォルト: accepted)
    --supersedes      覆す既存 ADR の番号(整数)

スクリプトの動作:
1. <decisions-dir> 内の既存 ADR から次の番号を特定
2. assets/adr-template.md を読み込み、プレースホルダーを置換
3. <decisions-dir>/NNNN-<slug>.md として書き出し
4. supersedes が指定された場合、対象の旧 ADR の status を superseded by NNNN に更新
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_PATH = SKILL_DIR / "assets" / "adr-template.md"


def find_next_number(decisions_dir: Path) -> int:
    """既存 ADR の最大番号 + 1 を返す。なければ 1。"""
    if not decisions_dir.exists():
        return 1

    pattern = re.compile(r"^(\d{4})-")
    max_num = 0
    for entry in decisions_dir.iterdir():
        if not entry.is_file() or entry.suffix != ".md":
            continue
        m = pattern.match(entry.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max_num + 1


def slug_to_title(slug: str) -> str:
    """slug から自然言語タイトルを生成(粗い変換)。

    例: 'use-iam-db-auth' -> 'Use Iam Db Auth'
    実用上はユーザーに --title で指定してもらうのが望ましい。
    """
    return " ".join(word.capitalize() for word in slug.split("-"))


def render_template(
    template: str,
    *,
    number: int,
    title: str,
    status: str,
    decision_makers: str,
    signals: str,
    supersedes: int | None,
) -> str:
    """テンプレートのプレースホルダーを置換する。"""
    rendered = template
    rendered = rendered.replace("{STATUS}", status)
    rendered = rendered.replace("{DATE}", date.today().isoformat())
    rendered = rendered.replace("{DECISION_MAKERS}", decision_makers)
    rendered = rendered.replace("{NUMBER}", f"{number:04d}")
    rendered = rendered.replace("{TITLE}", title)
    rendered = rendered.replace("{SIGNALS}", signals or "未指定")

    # supersedes が指定されたら front matter に挿入
    # \n---\n の最初の出現 = front matter の閉じ区切り（先頭の --- には前の \n がないため）
    if supersedes is not None:
        rendered = re.sub(
            r'\n(---)\n',
            f'\nsupersedes: {supersedes:04d}\n\\1\n',
            rendered,
            count=1,
        )

    return rendered


def update_superseded_adr(decisions_dir: Path, old_number: int, new_number: int) -> Path | None:
    """旧 ADR の status を superseded by NNNN に書き換える。"""
    pattern = re.compile(rf"^{old_number:04d}-")
    target: Path | None = None
    for entry in decisions_dir.iterdir():
        if entry.is_file() and entry.suffix == ".md" and pattern.match(entry.name):
            target = entry
            break

    if target is None:
        print(
            f"Warning: supersedes 対象の ADR-{old_number:04d} が {decisions_dir} に見つかりません。",
            file=sys.stderr,
        )
        return None

    content = target.read_text(encoding="utf-8")
    new_status = f'"superseded by {new_number:04d}"'

    # front matter 内の status を置換（ダブルクォート・シングルクォート・クォートなし を許容）
    new_content, n_replacements = re.subn(
        r'^status:\s*["\']?[^"\']*["\']?',
        f"status: {new_status}",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    if n_replacements == 0:
        print(
            f"Warning: {target.name} の status 行を見つけられませんでした。手動で更新してください。",
            file=sys.stderr,
        )
        return None

    target.write_text(new_content, encoding="utf-8")
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="新規 ADR を採番・生成する")
    parser.add_argument("slug", help="ファイル名に使う slug(英小文字とハイフン)")
    parser.add_argument(
        "--decisions-dir",
        default="docs/decisions",
        help="ADR の格納先(デフォルト: docs/decisions)",
    )
    parser.add_argument("--title", help="タイトル文字列(省略時は slug から生成)")
    parser.add_argument(
        "--signals", default="", help="該当する起票シグナル(カンマ区切り、例: S1,S2)"
    )
    parser.add_argument(
        "--decision-makers",
        default="Agent (via Claude Code)",
        help="決定者(カンマ区切り)",
    )
    parser.add_argument("--status", default="accepted", help="ステータス(デフォルト: accepted)")
    parser.add_argument(
        "--supersedes", type=int, default=None, help="覆す既存 ADR の番号(整数)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # slug の妥当性チェック
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", args.slug):
        print(
            f"Error: slug は英小文字・数字・ハイフンのみで、先頭は英小文字または数字: {args.slug!r}",
            file=sys.stderr,
        )
        return 1

    decisions_dir = Path(args.decisions_dir)
    decisions_dir.mkdir(parents=True, exist_ok=True)

    if not TEMPLATE_PATH.exists():
        print(f"Error: テンプレートが見つかりません: {TEMPLATE_PATH}", file=sys.stderr)
        return 1

    next_num = find_next_number(decisions_dir)
    title = args.title if args.title else slug_to_title(args.slug)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    content = render_template(
        template,
        number=next_num,
        title=title,
        status=args.status,
        decision_makers=args.decision_makers,
        signals=args.signals,
        supersedes=args.supersedes,
    )

    output_path = decisions_dir / f"{next_num:04d}-{args.slug}.md"
    if output_path.exists():
        print(f"Error: 既に存在します: {output_path}", file=sys.stderr)
        return 1

    output_path.write_text(content, encoding="utf-8")
    print(f"Created: {output_path}")

    if args.supersedes is not None:
        updated = update_superseded_adr(decisions_dir, args.supersedes, next_num)
        if updated:
            print(f"Updated (superseded): {updated}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
