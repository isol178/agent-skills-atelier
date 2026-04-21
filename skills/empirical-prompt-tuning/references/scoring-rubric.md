# Scoring Rubric

SKILL.md の「4. 両面評価」で参照される、精度計算と判定規則の一元定義。

## 採点基準

各要件項目を 3 値で評価する:

| 判定 | スコア | 条件 |
|---|---|---|
| ○ | 1.0 | 要件文言が **全面的に** 満たされている |
| 部分的 | 0.5 | 要件文言のうち一部のみ満たされている。または形式的には満たすが品質・具体性が不十分 |
| × | 0.0 | 要件が満たされていない、または評価対象が存在しない |

## 精度の算出式

```
精度 = (全項目のスコア合計) / (全項目数)
```

項目数でそのまま割る。[critical] 項目を重み付けしない（重み付けは「成功/失敗」判定で扱う）。

### 計算例

要件 5 項目（うち 1 つが [critical]）、判定が:

- [critical] 項目 1: ○ (1.0)
- 項目 2: ○ (1.0)
- 項目 3: 部分的 (0.5)
- 項目 4: × (0.0)
- 項目 5: ○ (1.0)

精度 = (1.0 + 1.0 + 0.5 + 0.0 + 1.0) / 5 = **0.70 (70%)**

## 成功/失敗の判定

精度とは別軸。`[critical]` タグ付き項目が基準。

- **成功（○）**: 全ての [critical] 項目が **○（満点 1.0）** のとき
- **失敗（×）**: [critical] 項目のうち 1 つでも × または **部分的（0.5）** のもの

つまり、**[critical] に「部分的」は不合格扱い**。[critical] は妥協しない下限として扱う。

### 判定例

ケース A: [critical] 項目が ○、他の通常項目に × が混じる
→ 成功 ○、精度は項目数で計算

ケース B: [critical] 項目が「部分的」、他の通常項目は全て ○
→ 失敗 ×（[critical] の妥協は認めない）

## 要件チェックリストの書き方

### 良い項目

○ / × / 部分的 のいずれかで判定できる粒度で書く。評価者がブレない文言にする。

例:
- `[critical] 生成された JSON に "title" フィールドが含まれる`
- `[critical] 実行結果のエラー終了コードが 0 である`
- `出力ファイルが指定ディレクトリに保存されている`
- `スクリプト先頭に shebang と docstring が含まれる`

### 悪い項目

- `品質が高い` → 判定者によってブレる
- `適切なエラー処理` → 「適切」の基準が未定義
- `使いやすい` → 主観

### [critical] の付け方

- **最低 1 つは必須**（ゼロだと成功判定が意味を失う）
- 「この要件を落としたら成果物として破綻する」ものだけ [critical] にする
- 付けすぎると成功率が暴落して弁別性が下がる。全項目の 1/3 以下が目安
- **iteration 途中で [critical] の付け外しはしない**（評価軸を動かすと前後比較ができなくなる）

## スコア集計の自動化

`scripts/score_requirements.py` を使うと JSON からの集計ができる。

入力形式例:

```json
{
  "scenario": "A",
  "requirements": [
    {"id": 1, "critical": true, "text": "...", "judgment": "pass"},
    {"id": 2, "critical": false, "text": "...", "judgment": "pass"},
    {"id": 3, "critical": false, "text": "...", "judgment": "partial"},
    {"id": 4, "critical": false, "text": "...", "judgment": "fail"},
    {"id": 5, "critical": false, "text": "...", "judgment": "pass"}
  ]
}
```

`judgment` は `"pass"` / `"partial"` / `"fail"` の 3 値を取る。

出力:

```
Scenario: A
Accuracy: 70.0% (3.5 / 5)
Outcome: FAIL (critical item 1: pass, but non-critical failures present)
  -> Actually: all critical items passed, so outcome = PASS
Outcome: PASS
```

（上は説明用の擬似出力。実際のスクリプト仕様は `scripts/score_requirements.py` を参照）
