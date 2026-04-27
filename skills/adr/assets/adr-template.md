---
status: "{STATUS}"
date: {DATE}
decision-makers: [{DECISION_MAKERS}]
consulted: []
informed: []
---

# {NUMBER}. {TITLE}

<!-- 起票シグナル: {SIGNALS} -->

## Context and Problem Statement

<!--
なぜこの判断が必要になったか。背景・制約・前提条件を 2〜3文で簡潔に。
inverted pyramid 文体で最重要事項を冒頭に。
制約の出所(URL/Issue/実験ログ)を必ず引用元として明記する。

形式の参考(Y-statement の context + concern):
「<ユースケース/状況> において、<懸念/制約>(出所: <URL/Issue>)に直面し、解決が必要だった。」
-->

## Decision Drivers

<!-- 判断を駆動した力(forces)。性能要件、コスト制約、運用要件、セキュリティ要件など。 -->

- {DRIVER_1}
- {DRIVER_2}
- {DRIVER_3}

## Considered Options

<!--
最低2案を推奨。S4(トレードオフ案)該当時は必須。
一方向の選択肢しかなかった場合は、そもそも ADR 不要の可能性が高い。
-->

- {OPTION_1}
- {OPTION_2}
- {OPTION_3}

## Decision Outcome

Chosen option: "{CHOSEN_OPTION}", because {RATIONALE}.

<!--
選定理由は Y-statement の "to achieve <quality>" + "accepting <downside>" の構造を意識する。
例: "IAM authentication", because it eliminates credential rotation overhead
    (to achieve operational simplicity), accepting the constraint that local
    development requires AWS profile setup.
-->

### Consequences

<!-- ネガティブ(Bad)が最低1項目必須。書けない場合は判定軸を再実施。 -->

- Good, because {POSITIVE_1}
- Good, because {POSITIVE_2}
- Bad, because {NEGATIVE_1}
- Bad, because {NEGATIVE_2}

### Confirmation

<!--
この決定がコードベースで遵守されているかをどう検証するか。
- 例: コードレビュー時に確認する具体的な観点
- 例: ArchUnit / カスタム lint ルール / CI チェック
- 例: 統合テストで担保
- 例: 定期レビュー時に再評価する条件

書けない場合はその理由を明記する。
-->

{CONFIRMATION}

## Pros and Cons of the Options

### {OPTION_1}

- Good, because {OPT1_GOOD}
- Neutral, because {OPT1_NEUTRAL}
- Bad, because {OPT1_BAD}

### {OPTION_2}

- Good, because {OPT2_GOOD}
- Bad, because {OPT2_BAD}

### {OPTION_3}

- Good, because {OPT3_GOOD}
- Bad, because {OPT3_BAD}

## More Information

- **Confidence**: {CONFIDENCE}
- **Re-evaluation triggers**: {REEVAL_TRIGGERS}
- **References**:
  - {REFERENCE_1}
  - {REFERENCE_2}
