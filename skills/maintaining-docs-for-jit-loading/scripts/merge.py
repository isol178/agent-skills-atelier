#!/usr/bin/env python3
"""
merge.py - 分割されたMarkdown節ファイルを1つの文書に結合する

使い方:
    python scripts/merge.py <ディレクトリパス>

例:
    python scripts/merge.py docs/requirements/spec/
    python scripts/merge.py docs/design/api_design/

引数:
    dir     split.py で生成された分割ディレクトリのパス

出力:
    <ディレクトリの親>/<ディレクトリ名>_merged.md
    （例: docs/requirements/spec_merged.md）

注意:
    - 元の分割ファイルは一切変更されない
    - INDEX.md はスキップされ、結合ファイルには含まれない
    - ファイルの結合順は INDEX.md の記載順。INDEX.md がない場合はファイル名の辞書順
"""

import sys
from pathlib import Path


# ──────────────────────────────────────────
# 順序解決
# ──────────────────────────────────────────


def resolve_order(dir_path: Path) -> list[Path]:
    """
    結合するファイルの順序を決定する。

    INDEX.md が存在すればそこに記載されたファイル名順。
    存在しない場合はファイル名の辞書順（INDEX.md を除く .md ファイル）。
    """
    index = dir_path / "INDEX.md"
    md_files = sorted([f for f in dir_path.glob("*.md") if f.name != "INDEX.md"])

    if not index.exists():
        return md_files

    # INDEX.md からファイル名を抽出（テーブル行の "`filename.md`" パターン）
    import re

    ordered: list[Path] = []
    seen: set[str] = set()

    for line in index.read_text(encoding="utf-8").splitlines():
        # テーブル行（| で始まる行）かつ先頭列のバッククォートのみマッチ
        if not line.startswith("|"):
            continue
        m = re.match(r"\|\s*`([^`]+\.md)`", line)
        if m:
            name = m.group(1)
            candidate = dir_path / name
            if candidate.exists() and name not in seen:
                ordered.append(candidate)
                seen.add(name)

    # INDEX.md に記載されていないファイルを末尾に追加
    for f in md_files:
        if f.name not in seen:
            ordered.append(f)

    return ordered


# ──────────────────────────────────────────
# 結合ロジック
# ──────────────────────────────────────────


def merge(dir_path: Path) -> Path:
    """
    分割ファイルを結合して _merged.md を書き出す。

    Returns:
        生成した出力ファイルのパス
    """
    files = resolve_order(dir_path)

    if not files:
        print(
            f"エラー: {dir_path} にMarkdownファイルが見つかりません。", file=sys.stderr
        )
        sys.exit(1)

    out_path = dir_path.parent / f"{dir_path.name}_merged.md"

    chunks: list[str] = []
    for f in files:
        content = f.read_text(encoding="utf-8")
        # split.py は各節ファイルを \n 1つで終端する。
        # "\n".join により節間に \n が補われ、元の区切り空行（\n\n）が復元される
        if not content.endswith("\n"):
            content += "\n"
        chunks.append(content)

    merged = "\n".join(chunks)

    out_path.write_text(merged, encoding="utf-8")
    return out_path


# ──────────────────────────────────────────
# エントリポイント
# ──────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    dir_path = Path(sys.argv[1])

    if not dir_path.exists():
        print(f"エラー: ディレクトリが見つかりません: {dir_path}", file=sys.stderr)
        sys.exit(1)
    if not dir_path.is_dir():
        print(
            f"エラー: ディレクトリを指定してください（ファイルが渡されました）: {dir_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    files = resolve_order(dir_path)
    print(f"結合対象: {len(files)}ファイル")
    for f in files:
        lines = f.read_text(encoding="utf-8").count("\n")
        print(f"  {f.name}  ({lines}行)")

    out_path = merge(dir_path)
    total_lines = out_path.read_text(encoding="utf-8").count("\n")

    print(f"\n[OK] 結合完了 - {out_path}  (計{total_lines}行)")
    print("※ 元の分割ファイルは変更されていません。")


if __name__ == "__main__":
    main()
