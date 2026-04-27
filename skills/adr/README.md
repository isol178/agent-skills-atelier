# ADR Skill

エージェント(Claude Code / Claude.ai 等)に **コードを読むだけでは "なぜそうなっているか" を復元できない技術判断** を ADR (Architecture Decision Record) として MADR 4.0.0 形式で記録させるためのスキル。

> このドキュメントは人間向け。エージェントは `SKILL.md` を読む。

## このスキルが解決する課題

ADR は「書くべき」「書かないと困る」と言われるが、実際の運用では:

- **何を ADR にすべきかの基準が曖昧** で、過剰起票(ノイズ化)または過少起票(why が消失)に陥りやすい
- **テンプレートだけ提供しても**、エージェントが起票判断や記述粒度を一貫させられない
- **品質ゲート不在** で、出所不明・代替案省略・トレードオフ未記載の弱い ADR が量産される

このスキルは以下で対応する:

1. **判定軸の一元化**: 「コードを見て why が復元できるか?」という単一の問いに集約
2. **6つの起票シグナル (S1〜S6)**: 該当パターンを具体例と失敗シナリオで提示
3. **MADR 4.0.0 準拠**: Confirmation セクションを含む業界標準形式
4. **自動検証**: `validate_adr.py` で構造・必須セクション・最低品質を機械チェック
5. **自発検出 + ユーザー確認**: エージェントが起票候補を検出するが、必ず確認を挟む

## ディレクトリ構成

```
adr/
├── SKILL.md                 # エージェントが発火時に読むコア(判定軸 + 起票フロー)
├── README.md                # このファイル(人間向け)
├── references/              # エージェントが必要時のみ view する参考資料
│   ├── signals.md           # 起票シグナル S1〜S6 の詳細・具体例・失敗シナリオ
│   ├── madr-template.md     # 各セクションの記述ガイドと品質チェックリスト
│   ├── antipatterns.md      # 「ADR ではないもの」の代表例
│   └── bibliography.md      # 出典・参考文献
├── assets/
│   └── adr-template.md      # MADR 4.0.0 テンプレート本体(new_adr.py が読む)
└── scripts/
    ├── new_adr.py           # 採番とテンプレ展開
    └── validate_adr.py      # フォーマット検証
```

Progressive Disclosure(skill-creator の3層構造)に従い:
- メタデータ(常時): `SKILL.md` の front matter
- 発火時: `SKILL.md` 本体(判定軸と最小フロー)
- 必要時: `references/` と `scripts/`

## クイックスタート

### スキルを使う(エージェント側)

ユーザーが「ADR を書いて」「決定を残して」と発話するか、エージェントがコード変更中に S1〜S6 のシグナルを検出すると発火する。

### 新規 ADR を起こす

```bash
# 最小
python scripts/new_adr.py "use-iam-db-auth"

# 推奨(タイトルとシグナルを明示)
python scripts/new_adr.py "use-iam-db-auth" \
  --title "Use IAM authentication for DB access" \
  --signals S1,S2 \
  --decision-makers "Haruki,Claude"

# 既存 ADR を覆す場合
python scripts/new_adr.py "use-pgbouncer" \
  --title "Adopt PgBouncer for connection pooling" \
  --supersedes 3
```

`docs/decisions/NNNN-<slug>.md` に MADR 4.0.0 テンプレートが展開される。`--supersedes` 指定時は対象の旧 ADR の `status` も自動更新される。

### 検証する

```bash
# 単一ファイル
python scripts/validate_adr.py docs/decisions/0001-use-iam-db-auth.md

# ディレクトリ全体
python scripts/validate_adr.py docs/decisions/

# warning も error 扱いにする(CI 用)
python scripts/validate_adr.py --strict docs/decisions/
```

## 何を ADR にすべきか / すべきでないか

### 起票候補(S1〜S6 のいずれかに該当)

- **S1**. 自然なデフォルトの放棄(例: パスワード認証 → IAM 認証)
- **S2**. 非自明な技術制約への対応(例: `connect_async()` を使う必要がある)
- **S3**. 意図的な分離・抽象化(例: 特定の credentials だけ別管理)
- **S4**. トレードオフを伴う代替案からの選択(例: SQLite vs PostgreSQL)
- **S5**. ASR (アーキテクチャ上重要な要件) への対応(例: マルチテナント分離方針)
- **S6**. 既存 ADR を覆す/修正する判断

詳細は `references/signals.md`。

### 起票しない

- 言語/フレームワークの慣用表現に従っただけ
- 公式ドキュメント通りのデフォルト構成
- 一方向しか選択肢がない決定
- バグ修正、リファクタリング、命名変更
- コーディング規約レベル(Linter で管理)
- プロトタイプ段階の暫定実装

判断に迷ったら `references/antipatterns.md` を参照。

## カスタマイズ

### 格納先を変える

デフォルトは `docs/decisions/` (Martin Fowler / MADR の推奨)。`docs/adr/` 等に変えたい場合:

```bash
python scripts/new_adr.py <slug> --decisions-dir docs/adr
```

### テンプレートを編集する

`assets/adr-template.md` を編集する。プレースホルダー(`{NUMBER}`, `{TITLE}` など)は `scripts/new_adr.py` の `render_template` 関数で置換される。新しいプレースホルダーを追加する場合は両方を更新する。

### 必須セクションを変える

`scripts/validate_adr.py` の `REQUIRED_SECTIONS` / `OPTIONAL_BUT_RECOMMENDED` を編集する。

### 起票シグナルを増減する

`references/signals.md` を編集し、`SKILL.md` の概要リストも合わせて更新する。

## CI への組み込み例

```yaml
# .github/workflows/adr-lint.yml
name: ADR Lint
on:
  pull_request:
    paths:
      - 'docs/decisions/**'
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install pyyaml
      - run: python .skills/adr/scripts/validate_adr.py --strict docs/decisions/
```

## 設計上の選択

このスキル自体の設計判断:

- **判定軸を1つに絞った**: 「重要だから」「大きいから」のような複数軸は実運用でブレるため、why 復元という単一軸に集約
- **MADR 4.0.0 を採用**: 2024-09 にリリースされた業界デファクト。Confirmation セクション(決定の遵守をどう検証するか)が強力
- **自発起票には必ずユーザー確認**: エージェントが勝手に ADR を量産するとノイズ化する。検出は自発、起票は確認後
- **機械チェック可能なものはスクリプト化**: 構造・必須セクション・最低項目数。文体・出所妥当性・実効性は人間判断
- **references/ への分離**: SKILL.md を <500 行に保ち、詳細は必要時のみエージェントが読む(Progressive Disclosure)

詳細な出典は `references/bibliography.md`。

## 参考文献

主な出典(完全版は `references/bibliography.md`):

- Michael Nygard, "Documenting Architecture Decisions" (2011) — ADR 概念の原典
- [MADR 4.0.0](https://adr.github.io/madr/) — 採用テンプレート
- Zdun et al., "Sustainable Architectural Decisions" (IEEE Software, 2013) — Y-statement 出典
- [Martin Fowler, "Architecture Decision Record"](https://martinfowler.com/bliki/ArchitectureDecisionRecord.html)
- [AWS Prescriptive Guidance: ADR](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/)
- [Microsoft Azure WAF: ADR](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)
