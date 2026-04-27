---
name: adr
description: コードを読むだけでは "なぜそうなっているか" を復元できない技術判断を ADR (Architecture Decision Record) として MADR 4.0.0 形式で記録する。ユーザーが「ADRを書いて」「決定を残して」「なぜこうしたか記録したい」と言った時、または非自明な技術選定・アーキテクチャ判断を行った/検出した時に使用する。DB認証方式の変更、ライブラリ固有の制約への対応、意図的な分離設計、複数の合理的な代替案からの選択など、半年後の自分や新メンバーがコードを見て困惑するような判断は対象。バグ修正やリファクタリングなど自明な変更には使わない。
---

# ADR (Architecture Decision Record) 起票

将来の開発者(6ヶ月後の自分を含む)が **コード・設定・コミットメッセージだけを読んでも why を復元できない判断** を `docs/decisions/NNNN-slug.md` に記録する。

ADR の本質は文書化ではなく **why の保全** である。コードから自明に読み取れる決定は記録不要で、むしろノイズになる。本スキルは [MADR 4.0.0](https://adr.github.io/madr/) を採用し、Y-statement の含意 (Zdun et al.) を取り込んでいる。

## 判定軸

ADR を書くべきかは、たった一つの問いで決まる:

> このコードを6ヶ月後の自分や新メンバーが見て、**なぜこの形になっているかを推測ではなく根拠を持って説明できるか?**

- Yes → ADR 不要(コードがドキュメントを兼ねている)
- No → ADR 起票候補(why が消失するリスクがある)

「重要だから」「大きい変更だから」では起票しない。**小さくても why が消える判断は記録し、大きくても自明な判断は記録しない**。

## 起票シグナル(概要)

以下のいずれかに該当すれば起票候補。詳細・具体例・失敗シナリオは `references/signals.md` を参照する。

- **S1. 自然なデフォルトの放棄** — フレームワーク/言語の "普通の使い方" を意図的に避けた
- **S2. 非自明な技術制約への対応** — ライブラリ/ランタイム固有の罠を回避するための設計
- **S3. 意図的な分離・抽象化** — 「なぜここだけ別扱い?」という疑問にコードが答えない構造
- **S4. トレードオフを伴う代替案からの選択** — 選ばなかった案にもメリットがあった
- **S5. アーキテクチャ上重要な要件 (ASR) への対応** — セキュリティ・可用性・性能などの非機能要件
- **S6. 既存 ADR を覆す/修正する判断** — 必ず Supersede 処理

「これは ADR 対象か?」という具体的な判断に迷ったら `references/signals.md` を読む。`references/antipatterns.md` には「ADR ではないもの」の例が集めてある。

## 自発起票とユーザー確認のフロー

エージェントは以下のいずれかの契機で起票プロセスに入る:

- **明示依頼**: ユーザーが「ADR を書いて」「決定を残して」と指示した
- **自発検出**: コード変更中に S1〜S6 のシグナルを検出した

**自発検出の場合は必ずユーザー確認を挟む**。承認なしに書き始めない。検出を伝える際は、該当シグナルと why が消失する具体的なシナリオを併記する。

```
例:
「DB 接続を IAM 認証に変更しました。これは S1 (自然なデフォルトの放棄) と
 S2 (非自明な技術制約: パスワード認証では Lambda 環境で接続プールが正しく動作しない) に
 該当します。半年後にこの判断の why が失われると、運用中に "シンプル化" の名目で
 パスワード認証に戻されるリスクがあります。ADR-NNNN として起票してよいですか?」
```

## 起票手順

### 1. 判定軸チェック

着手前に自問する:

1. このコードを6ヶ月後の自分が見て、why を即座に説明できるか?
2. 新メンバーがこのコードを読んで、別の "自然な" 書き方に改善しようとしないか?
3. どのシグナル(S1〜S6)に該当するか?

1 が Yes かつ 2 が No なら起票不要。それ以外なら次へ。

### 2. 情報の収集

ドラフトの原料を揃える。**制約の出所(URL、Issue、実験ログ)を必ず引用元として明記する**こと。「なんとなく」「経験上」は不可。

- **Context**: 決定が必要になった背景(具体的な課題、制約、前提条件)
- **Decision Drivers**: 判断を駆動した力 — 性能要件、コスト制約、運用要件、セキュリティ要件など
- **Considered Options**: 検討した代替案(最低2案を推奨)
- **Pros/Cons**: 各案の良い点と悪い点
- **Confirmation 手段**: 決定がコードベースで遵守されていることをどう検証するか

### 3. 新規 ADR の作成

採番とテンプレ展開はスクリプトで自動化する:

```bash
python scripts/new_adr.py "use-iam-db-auth"
```

これは次の番号(`NNNN`)を特定し、`docs/decisions/NNNN-use-iam-db-auth.md` に MADR 4.0.0 テンプレート(`assets/adr-template.md`)を展開する。

テンプレート各セクションの記述ガイドは `references/madr-template.md` を参照する。

### 4. 既存 ADR との整合 (Supersede)

新しい判断が既存 ADR を覆す場合:

1. **新 ADR**: front matter に `supersedes: NNNN` を追加し、`More Information` で経緯を説明
2. **旧 ADR**: front matter の `status` を `superseded by NNNN` に書き換え。**本文は immutability 原則に従い書き換えない**(歴史的経緯を保全する)

### 5. 品質ゲート

提出前に検証スクリプトを実行する:

```bash
python scripts/validate_adr.py docs/decisions/NNNN-use-iam-db-auth.md
```

このスクリプトは以下を機械的にチェックする:
- front matter の妥当性(`status`, `date`, `decision-makers` 必須)
- 必須セクションの存在(Context and Problem Statement / Decision Drivers / Considered Options / Decision Outcome / Consequences)
- Considered Options が最低2項目
- Consequences に "Bad, because" が最低1項目
- タイトル行の存在と整形

機械的にチェックできない品質基準(出所の妥当性、Confirmation の実効性、inverted pyramid 文体)は人間/エージェントの目視確認による。チェックリストは `references/madr-template.md` の末尾にある。

### 6. ユーザーへの提示

作成した ADR をユーザーに提示し、承認を得る。承認後、**関連するコード変更と同じコミット/PR に含める** ことを推奨する(コードと判断記録を一緒にレビューできるため)。

## 禁止事項

- 既存 ADR を **status 更新以外で削除/大幅変更** すること(immutability 原則)
- ADR 番号を重複させること
- Context や代替案を省略すること
- 制約の出所を「なんとなく」「経験上」で済ませること
- 1つの ADR に複数の独立した決定を詰め込むこと(複数フェーズの判断は分割)

## 参考資料の索引

- `references/signals.md` — 起票シグナル S1〜S6 の詳細、失敗シナリオ、具体例
- `references/madr-template.md` — MADR 4.0.0 各セクションの記述ガイドと品質チェックリスト
- `references/antipatterns.md` — 「ADR ではないもの」の代表例と理由
- `references/bibliography.md` — 出典・参考文献(Nygard, Zdun, Fowler, AWS, Azure 他)
- `assets/adr-template.md` — MADR 4.0.0 テンプレート本体(`new_adr.py` が読む)
- `scripts/new_adr.py` — 採番とテンプレ展開
- `scripts/validate_adr.py` — フォーマット検証
