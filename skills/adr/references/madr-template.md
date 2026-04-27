# MADR 4.0.0 記述ガイド

ADR 各セクションの書き方と、機械的にチェックできない品質基準のチェックリスト。

テンプレート本体は `assets/adr-template.md` にある。`scripts/new_adr.py` を実行すると自動的にこのテンプレートが展開される。

---

## セクション別の書き方

### Front Matter

```yaml
---
status: "accepted"           # proposed | accepted | rejected | deprecated | superseded by NNNN
date: YYYY-MM-DD
decision-makers: [Agent Name (via Claude Code), ...]
consulted: []                # 任意: 意見を仰いだ専門家など
informed: []                 # 任意: 結果を共有すべき関係者
supersedes: NNNN             # 任意: 覆した既存 ADR の番号
---
```

`status` は YAML 文字列としてダブルクォートで囲む(MADR 4.0.0 の仕様)。

### タイトル行

```markdown
# NNNN. <短いタイトル: 解決した問題と選んだ解決策を表す現在形>
```

タイトルには **現在形の動詞** を含めることを推奨。例: "Use IAM authentication for DB access" / "Adopt async connection pattern" / "Separate Firebase credentials from env vars"。

タイトル直後にコメントで該当する起票シグナルを記録すると、後から見返した時に「なぜこの判断を ADR にしたか」が分かる:

```markdown
<!-- 起票シグナル: S1, S2 -->
```

### Context and Problem Statement

なぜこの判断が必要になったか。背景・制約・前提条件を **2〜3文で簡潔に**。

inverted pyramid 文体(Martin Fowler)に従い、最重要の事実を冒頭に置く。

**制約の出所(ドキュメント、Issue、実験結果)を必ず引用元として明記する**。「なんとなく」「経験上」は不可。

形式の参考(Y-statement の context + concern):

> 「<ユースケース/状況> において、<懸念/制約>(出所: <URL/Issue>)に直面し、解決が必要だった。」

### Decision Drivers

判断を駆動した力(forces)をリスト形式で。

```markdown
- <driver 1: 性能要件、運用制約、セキュリティ要件など>
- <driver 2>
- <driver 3>
```

これがあると後から「なぜこの軸で評価したのか」が再現できる。Decision Drivers が書けない場合、判断の評価軸自体が曖昧な可能性がある。

### Considered Options

```markdown
- <option 1>
- <option 2>
- <option 3>
```

**最低2案を推奨**。S4(トレードオフ案)該当時は必須。一方向の選択肢しかなかった場合は、そもそも ADR 不要の可能性が高い。

### Decision Outcome

```markdown
Chosen option: "<option N>", because <選定理由を1〜2文で>.
```

選定理由は Y-statement の `to achieve <quality>` + `accepting <downside>` の構造を意識する。例:

> Chosen option: "IAM authentication", because it eliminates credential rotation overhead (to achieve operational simplicity), accepting the constraint that local development requires AWS profile setup.

### Consequences

```markdown
- Good, because <ポジティブな影響>
- Good, because <...>
- Bad, because <ネガティブな影響: 最低1項目必須>
- Bad, because <...>
```

ネガティブが書けない場合は判定軸を再実施。本当にトレードオフのない決定なら ADR 不要の可能性が高い。

### Confirmation

この決定がコードベースで遵守されているかをどう検証するか。

- 例: コードレビュー時に確認する具体的な観点
- 例: ArchUnit / カスタム lint ルール / CI チェック
- 例: 統合テストで担保
- 例: 定期レビュー時に再評価する条件

MADR 4.0.0 では optional だが、本スキルでは **可能な限り記述する**。決定が「実際に守られているか」の追跡可能性を担保する。書けない場合はその理由を明記する(例: 「人間のレビューでしか確認できない」)。

### Pros and Cons of the Options

各 option を同じ粒度で評価:

```markdown
### <option 1>

- Good, because <...>
- Neutral, because <...>
- Bad, because <...>

### <option 2>

- Good, because <...>
- Bad, because <...>
```

### More Information

- **Confidence**: `high | medium | low` — 判断の自信度。low の場合は再評価のトリガー条件を明記
- **Re-evaluation triggers**: この決定を見直すべき将来の出来事
- **References**: 関連する spec / issue / PR、関連する既存 ADR(相対パスでリンク)、制約の出所となるドキュメント/Issue の URL

---

## 機械チェック不可な品質基準

`scripts/validate_adr.py` で機械的にチェックできるのは構造のみ。以下は人間/エージェントの目視確認が必要:

### 単一性

1つの ADR に1つの決定のみ。複数フェーズの判断(短期/中期/長期)は別 ADR として分割する。「Phase 1 で X、Phase 2 で Y」のように2つの独立した決定が混在していないか。

### 出所の妥当性

Context に書かれた制約の出所が:
- 実際にアクセス可能な URL/Issue/ログを指しているか
- 出所と本文の主張が一致しているか
- 「公式ドキュメント」のような曖昧表現になっていないか(具体的なセクションまで指す)

### Confirmation の実効性

書かれている検証手段が:
- 実際に運用可能か(例: 「全コードを目視で確認」は非現実的)
- 自動化可能なものは自動化を検討したか
- 人間レビューの場合、何を見ればよいかが具体的か

### inverted pyramid 文体

- 最重要(決定と理由)が冒頭にあるか
- 詳細・補足が末尾にあるか
- 1ページ程度に収まっているか(典型的な目安)

### 検索性

- タイトルと slug にドメイン用語が含まれているか
- 半年後にキーワード検索でヒットしそうか

### confidence の妥当性

- low confidence と書いた場合、再評価条件が具体的か
- high confidence の場合、実際にその確信を支える根拠があるか

---

## 提出前チェックリスト

```
□ scripts/validate_adr.py を通過した
□ 単一の決定のみ含む(複数決定の混在なし)
□ Context に制約の出所(URL/Issue/ログ)が明記されている
□ Considered Options が最低2案、各案の Pros/Cons が具体的
□ Consequences にネガティブが最低1項目ある
□ Confirmation セクションが書かれている(または書けない理由が明確)
□ 該当する起票シグナル(S1〜S6)がコメントで明記されている
□ タイトルと slug にドメイン用語が含まれている
□ inverted pyramid 文体になっている
□ 1ページ程度に収まっている
```
