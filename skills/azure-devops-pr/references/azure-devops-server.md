# Azure DevOps Server 環境のフォールバック・トラブルシュート

## 重要な事実

**Azure DevOps Server（オンプレ版 / TFS の後継）では、`az repos pr` 系コマンドの大半がサポートされない**。Microsoft 公式ドキュメントが明記している：

> Azure DevOps CLI commands aren't supported for Azure DevOps Server.

サポートされるのは Azure DevOps Services（クラウド版、`dev.azure.com`）のみ。

社内 Azure DevOps（オンプレ）を使っている場合は、**REST API を直接叩く**ことで同等の操作を実現する。

## 環境判定

カレントの remote を見て、`dev.azure.com` でも `visualstudio.com` でもなければ、Server の可能性が高い：

```bash
REMOTE_URL=$(git config --get remote.origin.url)
echo "$REMOTE_URL"

case "$REMOTE_URL" in
  *dev.azure.com*|*visualstudio.com*) echo "Azure DevOps Services" ;;
  *) echo "Azure DevOps Server の可能性大（社内ホスト）" ;;
esac
```

ただし、組織が独自ドメインで Azure DevOps Services をホストしているケースもあるので、エラーが出てから判定するのが現実的。

## エラーシグナル

以下が出たら Server 環境のサイン：

- `az repos pr` 実行時に `Azure DevOps CLI commands aren't supported for Azure DevOps Server`
- `TF400898: An Internal Error Occurred`
- `az login` や `AZURE_DEVOPS_EXT_PAT` を設定しても認証エラーが続く

## REST API フォールバック戦略

### 認証

PAT を Basic 認証ヘッダに乗せる：

```bash
PAT="<your-personal-access-token>"
BASIC_AUTH=$(echo -n ":$PAT" | base64)
# 以降 -H "Authorization: Basic $BASIC_AUTH" を付ける
```

### Server の URL 形式

Services と Server で URL のベース部分が違う：

| 環境 | URL 形式 |
|---|---|
| Services | `https://dev.azure.com/{organization}/{project}/_apis/...` |
| Server | `https://<server>/{collection}/{project}/_apis/...` |

`collection` は Server 特有の概念で、Services の `organization` に相当する。社内ホスト名 + collection 名を確認する：

```bash
git remote -v | grep origin
# 例: https://devops.example.co.jp/DefaultCollection/MyProject/_git/MyRepo
#                                  ^^^^^^^^^^^^^^^^^  ^^^^^^^^^      ^^^^^^^
#                                  collection         project        repo
```

### API バージョン

Server は古い API バージョンが必要なことが多い：

- Server 2019: `api-version=5.0`
- Server 2020: `api-version=6.0`
- Server 2022 以降: `api-version=6.0` または `7.0`

`api-version=7.1-preview.1` のように preview を指定するとうまく行く場合もある。

### 基本パターン：curl で PR 操作

#### PR 一覧

```bash
SERVER="https://devops.example.co.jp"
COLLECTION="DefaultCollection"
PROJECT="MyProject"
REPO="MyRepo"

curl -s -H "Authorization: Basic $BASIC_AUTH" \
  "$SERVER/$COLLECTION/$PROJECT/_apis/git/repositories/$REPO/pullrequests?api-version=6.0&searchCriteria.status=active" \
  | jq '.value[] | {id: .pullRequestId, title, status, source: .sourceRefName, target: .targetRefName}'
```

#### PR 詳細

```bash
PR_ID=42
curl -s -H "Authorization: Basic $BASIC_AUTH" \
  "$SERVER/$COLLECTION/$PROJECT/_apis/git/repositories/$REPO/pullrequests/$PR_ID?api-version=6.0" \
  | jq '.'
```

#### PR 作成

```bash
cat > "$TEMP/pr_body.json" <<EOF
{
  "sourceRefName": "refs/heads/feature/login",
  "targetRefName": "refs/heads/main",
  "title": "feat(auth): JWT 認証",
  "description": "PR の説明"
}
EOF

curl -s -X POST \
  -H "Authorization: Basic $BASIC_AUTH" \
  -H "Content-Type: application/json" \
  -d @"$TEMP/pr_body.json" \
  "$SERVER/$COLLECTION/$PROJECT/_apis/git/repositories/$REPO/pullrequests?api-version=6.0" \
  | jq '{id: .pullRequestId, url: .url}'
```

`sourceRefName` / `targetRefName` は **`refs/heads/` プレフィックスが必須**（Services の CLI と違う点）。

#### PR にコメント（スレッド作成）

```bash
PR_ID=42
cat > "$TEMP/thread.json" <<'EOF'
{
  "comments": [
    {"parentCommentId": 0, "content": "LGTM", "commentType": 1}
  ],
  "status": 1
}
EOF

curl -s -X POST \
  -H "Authorization: Basic $BASIC_AUTH" \
  -H "Content-Type: application/json" \
  -d @"$TEMP/thread.json" \
  "$SERVER/$COLLECTION/$PROJECT/_apis/git/repositories/$REPO/pullrequests/$PR_ID/threads?api-version=6.0"
```

#### Reviewer 追加

```bash
# まずレビュアーの ID を引く（Server では Graph API で）
USER_ID=$(curl -s -H "Authorization: Basic $BASIC_AUTH" \
  "$SERVER/$COLLECTION/_apis/identities?searchFilter=General&filterValue=alice@example.com&api-version=6.0" \
  | jq -r '.value[0].id')

# Reviewer に追加（PUT）
curl -s -X PUT \
  -H "Authorization: Basic $BASIC_AUTH" \
  -H "Content-Type: application/json" \
  -d '{"vote": 0}' \
  "$SERVER/$COLLECTION/$PROJECT/_apis/git/repositories/$REPO/pullrequests/$PR_ID/reviewers/$USER_ID?api-version=6.0"
```

`vote` 値: 10=approve, 5=approveWithSuggestions, 0=noVote, -5=waitForAuthor, -10=reject

## REST API リファレンス

Server 環境では公式ドキュメントの Git Pull Request API を直接参照する：

- 一覧：https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-requests
- スレッド：https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-threads
- レビュアー：https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-reviewers

API バージョンは Server のバージョンに合わせて切り替える。

## 認証エラーのトラブルシュート

### `TF401002: The Git repository ... requires authentication`

PAT が無効か、スコープ不足。PAT を Azure DevOps の設定画面で再発行：
- 最低限：Code (Read & Write)
- コメント書く：Code (Read, Write, & Manage)
- Work Item 紐付け：Work Items (Read & Write)

### `VS800075: The project ... does not exist`

project 名のスペルミスか、URL の collection 名が間違っている。`git remote -v` の URL を再確認する。

### `Could not retrieve identity`

`AZURE_DEVOPS_EXT_PAT` を設定したのに認識されない場合、別の環境変数 `AZURE_DEVOPS_EXT_PAT` ではなく旧名 `SYSTEM_ACCESSTOKEN` や `AZURE_DEVOPS_CLI_PAT` を試すか、`az devops login` で対話的にセットする：

```bash
echo "<your-pat>" | az devops login --organization "$SERVER/$COLLECTION"
```

### プロキシ環境

社内ネットワーク経由なら `HTTPS_PROXY` を設定：

```bash
export HTTPS_PROXY=http://proxy.example.co.jp:8080
export HTTP_PROXY=http://proxy.example.co.jp:8080
export NO_PROXY=localhost,127.0.0.1
```

az cli は内部で requests を使うので、SSL 証明書エラーが出る場合は社内 CA 証明書を `REQUESTS_CA_BUNDLE` に設定。

## まとめ

Server 環境では：

1. **CLI コマンドは使わない**。`curl + jq` の REST 直叩きを基本とする
2. **`refs/heads/` プレフィックス**を忘れない
3. **API バージョン**は環境に合わせて 5.0 / 6.0 / 7.0 を試す
4. **`collection` 概念**を URL に正しく入れる
5. PAT は `AZURE_DEVOPS_EXT_PAT` か Basic 認証で
