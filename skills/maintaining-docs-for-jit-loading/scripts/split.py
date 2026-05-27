#!/usr/bin/env python3
"""
split.py - Markdown文書を節単位のファイルに分割する

使い方:
    python scripts/split.py <ファイルパス> [--level 2] [--dry-run]

例:
    python scripts/split.py docs/requirements/spec.md
    python scripts/split.py docs/design/api_design.md --level 3
    python scripts/split.py docs/requirements/spec.md --dry-run

引数:
    file        分割対象のMarkdownファイルパス
    --level     分割する見出しレベル（デフォルト: 2 = "## "）
    --dry-run   実際には書き出さず、分割結果をプレビューする

出力:
    <元ファイル名ディレクトリ>/
        INDEX.md
        01_<section_title>.md
        02_<section_title>.md
        ...
    <元ファイル>.bak  （元ファイルのバックアップ）
"""

import argparse
import re
import shutil
import sys
from pathlib import Path


# ──────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────


def to_snake(text: str) -> str:
    """見出しテキストをファイル名用のsnake_caseに変換する。"""
    # 日本語・記号をアンダースコアに、英数字は小文字に
    text = text.strip()
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text)
    text = text.lower()
    # 連続アンダースコアを整理
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "section"


def extract_summary(lines: list[str], max_chars: int = 80) -> str:
    """節の先頭から意味のある1行サマリを抽出する。"""
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        # テーブルのヘッダ行はスキップ
        if line.startswith("|"):
            continue
        return line[:max_chars] + ("…" if len(line) > max_chars else "")
    return ""


# ──────────────────────────────────────────
# 分割ロジック
# ──────────────────────────────────────────


def parse_sections(content: str, level: int) -> list[dict]:
    """
    指定レベルの見出しで内容を節に分割する。

    Returns:
        list of {
            "heading": str,       # 見出しテキスト（## を除く）
            "heading_line": str,  # 元の見出し行（## つき）
            "lines": list[str],   # 見出し行を含む節の全行
        }
    """
    prefix = "#" * level + " "
    sections = []
    current: dict | None = None
    preamble_lines: list[str] = []

    in_code_block = False
    fence_char = ""

    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        if not in_code_block:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_code_block = True
                fence_char = stripped[:3]
        elif stripped.startswith(fence_char):
            in_code_block = False
            fence_char = ""
        if (
            not in_code_block
            and line.startswith(prefix)
            and not line.startswith(prefix + "#")
        ):
            # 新しい節の開始
            if current is None and preamble_lines:
                # 最初の見出しより前の内容をpreambleとして記録
                sections.append(
                    {
                        "heading": "_preamble",
                        "heading_line": "",
                        "lines": preamble_lines,
                    }
                )
                preamble_lines = []
            if current is not None:
                sections.append(current)
            heading_text = line.lstrip("#").strip().rstrip("\n")
            current = {
                "heading": heading_text,
                "heading_line": line,
                "lines": [line],
            }
        else:
            if current is not None:
                current["lines"].append(line)
            elif not sections:
                # 最初の見出しより前 → preamble に蓄積
                preamble_lines.append(line)

    if current is not None:
        sections.append(current)

    return sections


# ──────────────────────────────────────────
# ファイル書き出し
# ──────────────────────────────────────────


def build_index(
    sections: list[dict],
    out_dir: Path,
    source_file: Path,
) -> str:
    """INDEX.md の内容を生成する。"""
    lines = [
        f"# INDEX - {source_file.name}\n",
        "\n",
        f"> 元ファイル: `{source_file}`\n",
        f"> 分割ファイル数: {len([s for s in sections if s['heading'] != '_preamble'])}\n",
        f"> 結合コマンド: `python scripts/merge.py {out_dir}`\n",
        "\n",
        "---\n",
        "\n",
        "| ファイル | 見出し | 概要 |\n",
        "|---|---|---|\n",
    ]

    for s in sections:
        if s["heading"] == "_preamble":
            continue
        fname = s.get("filename", "")
        summary = extract_summary(s["lines"][1:])  # 見出し行の次から
        lines.append(f"| `{fname}` | {s['heading']} | {summary} |\n")

    return "".join(lines)


def write_split(
    source: Path,
    sections: list[dict],
    out_dir: Path,
    dry_run: bool = False,
) -> None:
    """分割ファイルを書き出す。"""
    preamble = next((s for s in sections if s["heading"] == "_preamble"), None)
    content_sections = [s for s in sections if s["heading"] != "_preamble"]

    # preamble を最初の節の先頭に連結して往復再現を保証する
    # in-place 変更により sections リスト内の同一オブジェクトにも反映され、
    # build_index が filename を正しく参照できる
    if preamble and content_sections:
        content_sections[0]["lines"] = preamble["lines"] + content_sections[0]["lines"]

    width = len(str(len(content_sections)))

    for i, section in enumerate(content_sections, start=1):
        slug = to_snake(section["heading"])
        filename = f"{str(i).zfill(width)}_{slug}.md"
        section["filename"] = filename

    index_content = build_index(sections, out_dir, source)

    if dry_run:
        print("=== DRY RUN - 実際のファイルは生成されません ===\n")
        print(f"出力先ディレクトリ: {out_dir}/\n")
        for s in content_sections:
            line_count = len(s["lines"])
            print(f"  {s['filename']}  ({line_count}行)  - {s['heading']}")
        print(f"\n  INDEX.md")
        print(f"\nバックアップ: {source}.bak")
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    # 元ファイルをバックアップ
    bak = source.with_suffix(".md.bak")
    shutil.copy2(source, bak)
    print(f"バックアップ作成: {bak}")

    # 節ファイルを書き出し（末尾の余分な空行を除去して1つの \n で終端）
    for s in content_sections:
        out_path = out_dir / s["filename"]
        content = "".join(s["lines"]).rstrip("\n") + "\n"
        out_path.write_text(content, encoding="utf-8")
        print(f"  書き出し: {out_path}  ({len(s['lines'])}行)")

    # INDEX.md を書き出し
    index_path = out_dir / "INDEX.md"
    index_path.write_text(index_content, encoding="utf-8")
    print(f"  書き出し: {index_path}")

    print(f"\n[OK] 分割完了 - {out_dir}/")


# ──────────────────────────────────────────
# エントリポイント
# ──────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Markdownを節単位に分割する")
    parser.add_argument("file", help="分割対象のMarkdownファイルパス")
    parser.add_argument(
        "--level", type=int, default=2, help="分割する見出しレベル（デフォルト: 2）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="プレビューのみ。実際にはファイルを生成しない",
    )
    args = parser.parse_args()

    source = Path(args.file)
    if not source.exists():
        print(f"エラー: ファイルが見つかりません: {source}", file=sys.stderr)
        sys.exit(1)
    if source.suffix.lower() != ".md":
        print(
            f"エラー: Markdownファイル（.md）を指定してください: {source}",
            file=sys.stderr,
        )
        sys.exit(1)

    content = source.read_text(encoding="utf-8")
    sections = parse_sections(content, args.level)
    content_sections = [s for s in sections if s["heading"] != "_preamble"]

    if not content_sections:
        print(
            f"エラー: H{args.level}（{'#' * args.level} ）の見出しが見つかりませんでした。"
            f" --level で見出しレベルを変更してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    # 出力ディレクトリ = 元ファイルと同階層の同名ディレクトリ
    out_dir = source.parent / source.stem

    write_split(source, sections, out_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
