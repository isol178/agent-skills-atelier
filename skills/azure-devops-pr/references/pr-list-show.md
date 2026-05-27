# PR 一覧・詳細・検索（az repos pr list / show）

PR を探したり詳細を見たりする操作。`--query`（JMESPath）でフィルタ・整形できると一気に実用度が上がる。

## 目次

1. `az repos pr list` の基本
2. 典型的なフィルタパターン
3. `az repos pr show` の使い方
4. JMESPath クエリレシピ
5. 「俺の PR」「俺がレビュアーの PR」を出すワンライナー

---

## 1. `az repos pr list` の基本

主要オプション：

| オプション | 用途 |
|---|---|
| `--status` | `active` / `completed` / `abandoned` / `all`（デフォルト active） |
| `--creator` | 作成者で絞る（表示名 or メールアドレス） |
| `--reviewer` | レビュアーで絞る（表示名 or メールアドレス） |
| `--source-branch` | ソースブランチで絞る |
| `--target-branch` | ターゲットブランチで絞る |
| `--repository` | リポジトリで絞る |
| `--project` | プロジェクトで絞る |
| `--organization` | 組織を指定 |
| `--top` | 最大件数（デフォルトは API 側の上限） |
| `--skip` | スキップ件数（ページング） |
| `--include-links` | 各 PR に関連リンクを含める |
| `--query` | JMESPath で結果を絞り込み・整形 |
| `--output` | json / table / tsv / yaml |

注意：`--top` は API 側のページング指定。**日付での絞り込みパラメータは存在しない**ので、日付フィルタは取得後に jq か JMESPath でやる。

---

## 2. 典型的なフィルタパターン

### Active な PR の一覧

```bash
az repos pr list --output table
```

### 自分が作った PR（全状態）

```bash
az repos pr list --creator "Haruki" --status all --output table
```

`--creator` には表示名 or メールアドレスが使える。Fujitsu 社内の場合は氏名のローマ字表記やメールアドレスを試す。

### 自分がレビュアーになっている PR

```bash
az repos pr list --reviewer "Haruki" --status active --output table
```

### 特定リポジトリの active な PR、テーブル表示

```bash
az repos pr list --repository MyRepo --status active --output table
```

### main 向けの PR だけ

```bash
az repos pr list --target-branch main --status active --output table
```

### 自分が出した最新の PR 1件（状態不問）

```bash
az repos pr list --creator "Haruki" --status all --top 1 --output json | jq '.[0]'
```

---

## 3. `az repos pr show`

PR ID が分かっている前提で詳細を取る：

```bash
# 基本
az repos pr show --id 42

# JSON で取得して特定フィールドだけ抜く
az repos pr show --id 42 --output json | jq '{title, status, mergeStatus, createdBy: .createdBy.displayName, reviewers: [.reviewers[].displayName], sourceRef: .sourceRefName, targetRef: .targetRefName}'

# テーブル表示
az repos pr show --id 42 --output table

# ブラウザで開く
az repos pr show --id 42 --open
```

### PR の状態を確認する

`mergeStatus` で マージ可能性が分かる：

```bash
az repos pr show --id 42 --query "{title:title, status:status, mergeStatus:mergeStatus, isDraft:isDraft}" --output table
```

`mergeStatus` の値：
- `succeeded` — マージ可能
- `conflicts` — コンフリクトあり
- `rejectedByPolicy` — ブランチポリシー違反
- `queued` — 検証中
- `failure` — その他失敗

---

## 4. JMESPath クエリレシピ

`--query` で結果を整形すると、`jq` を後付けせずに済む。

### 必要なフィールドだけテーブル化

```bash
az repos pr list --status active \
  --query "[].{ID:pullRequestId, Title:title, Creator:createdBy.displayName, Source:sourceRefName, Target:targetRefName, Created:creationDate}" \
  --output table
```

### レビュアーを文字列結合してテーブル化

```bash
az repos pr list --status active \
  --query "[].{ID:pullRequestId, Title:title, Reviewers:join(',', reviewers[].displayName)}" \
  --output table
```

### ドラフトを除外

```bash
az repos pr list --status active \
  --query "[?isDraft==\`false\`].{ID:pullRequestId, Title:title}" \
  --output table
```

### 特定の Work Item に紐付く PR を探す（include-links 使用）

```bash
az repos pr list --status all --include-links \
  --query "[?_links.workItems != null].{ID:pullRequestId, Title:title}" \
  --output table
```

ただし PR ↔ Work Item の紐付けは `az repos pr work-item list --id <PR_ID>` で個別に取るほうが確実。

### sourceRefName から `refs/heads/` を除いて整形

`sourceRefName` は `refs/heads/feature/login` のように返ってくる。JMESPath だけだと文字列加工が弱いので、`jq` を併用するのも手：

```bash
az repos pr list --status active --output json \
  | jq '.[] | {id: .pullRequestId, title, source: (.sourceRefName | sub("refs/heads/"; "")), target: (.targetRefName | sub("refs/heads/"; ""))}'
```

---

## 5. 「俺の PR」「俺がレビュアーの PR」ワンライナー

ユーザーの名前またはメールが分かっていれば、以下を即座に提案できる。`USER_NAME` は事前に確認するか、`az account show` の `user.name` から取る：

```bash
# 自分が作った active な PR
USER_NAME=$(az account show --query user.name -o tsv)
az repos pr list --creator "$USER_NAME" --status active \
  --query "[].{ID:pullRequestId, Title:title, Target:targetRefName}" \
  --output table

# 自分がレビュアーの active な PR（未投票の場合は要対応）
az repos pr list --reviewer "$USER_NAME" --status active \
  --query "[].{ID:pullRequestId, Title:title, Creator:createdBy.displayName}" \
  --output table
```

注意：`az account show` の `user.name` は Azure 側の認証アカウント名で、Azure DevOps の表示名と一致しない場合がある。一致しなければ、ユーザーに「PR 検索で使う表示名 or メールアドレスを教えてください」と一度確認する。一度教えてもらえば、その値を会話内で再利用する。

---

## 6. ページング

`--top` だけだと最初の N 件しか取れない。全件欲しい場合はループ：

```bash
SKIP=0
TOP=100
while :; do
  RESULT=$(az repos pr list --status all --top $TOP --skip $SKIP --output json)
  COUNT=$(echo "$RESULT" | jq 'length')
  echo "$RESULT" | jq '.[]'  # 必要な処理
  [ "$COUNT" -lt "$TOP" ] && break
  SKIP=$((SKIP + TOP))
done
```

ただし通常のユースケース（active な PR を見る）では `--top 50` 程度で十分。
