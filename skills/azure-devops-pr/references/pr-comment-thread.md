# PR コメント・スレッド（az devops invoke で REST API 経由）

**重要：`az repos pr` には comment / thread のサブコマンドが存在しない**。PR コメント・スレッドの追加・取得・更新は、すべて `az devops invoke` 経由で Azure DevOps REST API を叩く必要がある。

このファイルは、その典型パターンをまとめたもの。

## 目次

1. 基礎：thread と comment の関係
2. 一般スレッド（ファイル位置なし）の作成
3. ファイル位置を指定したスレッドの作成（コードレビューコメント）
4. 既存スレッドへの返信コメント
5. スレッド一覧・取得
6. スレッドの status 更新（resolve / close など）
7. 必要な情報の収集方法

---

## 1. 基礎：thread と comment の関係

Azure DevOps の PR コメント構造は GitHub と違って **thread → comment** の2階層：

- **thread**：1つの議論の単位。ステータス（active / resolved / closed / wontfix など）を持つ
- **comment**：thread 内の個別発言。1つの thread に複数 comment がぶら下がる

PR にコメントを「新規で書く」＝**新しい thread を作成**する。返信したい時は**既存 thread に comment を追加**する。

`commentType` フィールド（数値）：
- `1` = `text`（通常のコメント）
- `2` = `codeChange`（システム生成）
- `3` = `system`（システム生成）

人間／スキルが投稿する時は常に `1` (`text`) でよい。

`status` フィールド（thread のステータス、数値）：
- `1` = `active`（議論中、デフォルト）
- `2` = `fixed`（修正済み）
- `3` = `wontFix`
- `4` = `closed`
- `5` = `byDesign`
- `6` = `pending`

---

## 2. 一般スレッド（ファイル位置なし）の作成

PR 全体に対するコメント（ファイル指定なし）を投稿する：

```bash
PR_ID=42
REPO_ID="<repository-id-or-name>"
PROJECT="<project-name>"

# リクエストボディを作る
cat > "$TEMP/thread_body.json" <<'EOF'
{
  "comments": [
    {
      "parentCommentId": 0,
      "content": "全体的に良いと思いますが、変更点 3 の意図を確認させてください。",
      "commentType": 1
    }
  ],
  "status": 1
}
EOF

# az devops invoke で POST
az devops invoke \
  --area git \
  --resource pullRequestThreads \
  --route-parameters \
    project="$PROJECT" \
    repositoryId="$REPO_ID" \
    pullRequestId="$PR_ID" \
  --http-method POST \
  --in-file "$TEMP/thread_body.json" \
  --api-version 7.1 \
  --output json
```

POST が成功すると、作成された thread の JSON が返る。`id` フィールドが thread ID。

### jq で安全に JSON を組み立てるパターン（推奨）

コメント本文に `"` や改行・日本語が含まれる場合は `jq --arg` でエスケープして `$TEMP` ファイル経由が安全：

```bash
COMMENT='コメント本文（改行や "引用符" も OK）'
jq -n --arg c "$COMMENT" '{
  comments: [{parentCommentId: 0, content: $c, commentType: 1}],
  status: 1
}' > "$TEMP/thread_body.json"

az devops invoke \
  --area git \
  --resource pullRequestThreads \
  --route-parameters \
    project="$PROJECT" \
    repositoryId="$REPO_ID" \
    pullRequestId="$PR_ID" \
  --http-method POST \
  --in-file "$TEMP/thread_body.json" \
  --api-version 7.1
```

> **Windows (Git Bash) 注意**: `/tmp/foo.json` は `C:\Program Files\Git\tmp\foo.json` にマップされるため避ける。`"$TEMP/foo.json"` を使うこと。`/dev/stdin` ヒアドキュメント経由も同様に失敗するため使わない。

---

## 3. ファイル位置を指定したスレッドの作成（コードレビューコメント）

特定ファイルの特定行に対するコメントには `threadContext` を追加する：

```bash
MSYS_NO_PATHCONV=1 jq -n \
  --arg c "ここは null チェックが必要では？" \
  --arg f "/src/auth/service.ts" \
  '{comments:[{parentCommentId:0,content:$c,commentType:1}],status:1,
    threadContext:{filePath:$f,rightFileStart:{line:42,offset:1},rightFileEnd:{line:42,offset:200}}}' \
  > "$TEMP/thread_body.json"

az devops invoke \
  --area git --resource pullRequestThreads \
  --route-parameters project="$PROJECT" repositoryId="$REPO_ID" pullRequestId="$PR_ID" \
  --http-method POST --in-file "$TEMP/thread_body.json" --api-version 7.1
```

### `threadContext` の各フィールド

| フィールド | 意味 |
|---|---|
| `filePath` | リポジトリルートからの絶対パス（先頭 `/` あり、例：`/src/foo.ts`）**※後述の MSYS 注意参照** |
| `rightFileStart` | ソースブランチ側でのコメント範囲の開始位置 |
| `rightFileEnd` | ソースブランチ側でのコメント範囲の終了位置 |
| `leftFileStart` | ターゲット（旧）側の開始位置（削除行へのコメント用） |
| `leftFileEnd` | ターゲット（旧）側の終了位置 |

位置オブジェクトは `{"line": N, "offset": M}`：
- `line`：1始まり
- `offset`：行内の文字位置（1始まり）

行全体にコメントしたい場合は `offset` を `1`〜`<その行の文字数+1>` にする。厳密でなくても表示はされるので、`{"line": N, "offset": 1}` から `{"line": N, "offset": 100}` のような雑な範囲でも実用上 OK。

> **Windows (Git Bash) 落とし穴**: `jq --arg f "/src/foo.ts"` のように `--arg` に `/` 始まりの文字列を渡すと、MSYS のパス変換が働いて `C:/Program Files/Git/src/foo.ts` に展開されることがある。これを防ぐには **`MSYS_NO_PATHCONV=1 jq ...`** と前置きする。展開されたパスは ADO 上で「このファイルは PR に存在しない」エラーになる。

### 削除された行へのコメント

`leftFileStart` / `leftFileEnd` を使う（`rightFile*` は付けない）：

```json
"threadContext": {
  "filePath": "/src/old.ts",
  "leftFileStart": {"line": 10, "offset": 1},
  "leftFileEnd": {"line": 10, "offset": 50}
}
```

---

## 4. 既存スレッドへの返信コメント

既存 thread に comment を追加（＝返信）：

```bash
THREAD_ID=148

jq -n --arg c "なるほど、確認します。" \
  '{parentCommentId:1,content:$c,commentType:1}' \
  > "$TEMP/comment_body.json"

az devops invoke \
  --area git \
  --resource pullRequestThreadComments \
  --route-parameters \
    project="$PROJECT" \
    repositoryId="$REPO_ID" \
    pullRequestId="$PR_ID" \
    threadId="$THREAD_ID" \
  --http-method POST \
  --in-file "$TEMP/comment_body.json" \
  --api-version 7.1
```

`parentCommentId` には、返信先の comment ID を入れる（thread の先頭コメントは通常 ID = 1）。

---

## 5. スレッド一覧・取得

PR のスレッド一覧：

```bash
az devops invoke \
  --area git \
  --resource pullRequestThreads \
  --route-parameters \
    project="$PROJECT" \
    repositoryId="$REPO_ID" \
    pullRequestId="$PR_ID" \
  --http-method GET \
  --api-version 7.1 \
  --output json
```

返ってきた JSON から、まだ active なスレッドだけ抜く：

```bash
... | jq '.value[] | select(.status == "active") | {id, file: .threadContext.filePath, comments: [.comments[].content]}'
```

注：レスポンスでは `status` は数値ではなく文字列（`"active"`, `"fixed"` など）で返ってくることがある。両方ハンドルできるようにする：

```bash
... | jq '.value[] | select(.status == "active" or .status == 1)'
```

---

## 6. スレッドの status 更新（resolve / close など）

スレッドを「解決済み」にする：

```bash
echo '{"status": 2}' > "$TEMP/thread_update.json"

az devops invoke \
  --area git \
  --resource pullRequestThreads \
  --route-parameters \
    project="$PROJECT" \
    repositoryId="$REPO_ID" \
    pullRequestId="$PR_ID" \
    threadId="$THREAD_ID" \
  --http-method PATCH \
  --in-file "$TEMP/thread_update.json" \
  --api-version 7.1
```

status の値（再掲）：1=active, 2=fixed, 3=wontFix, 4=closed, 5=byDesign, 6=pending

---

## 7. 必要な情報の収集方法

REST 呼び出しには `repositoryId`、`project`、`pullRequestId` が必要。これらの取り方：

### project 名

```bash
# az devops defaults から
az devops configure --list | grep project

# または PR の show から
az repos pr show --id $PR_ID --query "repository.project.name" -o tsv
```

### repositoryId

`az devops invoke` の route-parameters では **リポジトリ名でも ID でも通る**ことが多いが、確実なのは ID：

```bash
# repo 名から ID を引く
REPO_ID=$(az repos show --repository <repo-name> --query id -o tsv)

# または PR の show から
REPO_ID=$(az repos pr show --id $PR_ID --query repository.id -o tsv)
```

### pullRequestId

ユーザーから明示されているはず。なければ list で探す。

### organization

`AZURE_DEVOPS_EXT_ORGANIZATION` 環境変数 or `az devops configure -d organization=...` で設定済みであれば、`--organization` を省略できる。

---

## 8. 全体を1つにまとめたパターン

このパターンは `scripts/create_thread.sh` にラッパー化してある。手動で組み立てるより、スクリプトを使うことを推奨する：

```bash
# PR #42 全体にコメントを残す
scripts/create_thread.sh --pr-id 42 --content "LGTM 👍"

# ファイル位置を指定したコードレビューコメント
scripts/create_thread.sh --pr-id 42 --content "null チェックが必要では？" \
    --file "/src/auth/service.ts" --line 42

# 既存スレッドへ返信（--parent-comment-id 省略時は 1 が自動でセットされる）
scripts/create_thread.sh --pr-id 42 --content "対応しました" --thread-id 148
```

スクリプトは $TEMP の空チェック・`--project` の自動伝搬・`--argjson` の数値バリデーション等を処理済み。
