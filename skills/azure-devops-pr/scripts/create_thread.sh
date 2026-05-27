#!/usr/bin/env bash
# create_thread.sh — PR にコメントスレッドを追加するラッパー
#
# Azure CLI に PR コメント・スレッドのコマンドが存在しないため、
# az devops invoke 経由で REST API を叩く処理をラップする。
#
# 使い方:
#   # PR 全体への一般コメント
#   create_thread.sh --pr-id 42 --content "LGTM"
#
#   # ファイル位置を指定したコードレビューコメント
#   create_thread.sh --pr-id 42 --content "null チェック必要" \
#       --file "/src/auth.ts" --line 42
#
#   # 既存スレッドへの返信
#   create_thread.sh --pr-id 42 --content "なるほど" \
#       --thread-id 148 --parent-comment-id 1
#
# 前提:
#   - az cli + azure-devops 拡張がインストール済み
#   - AZURE_DEVOPS_EXT_PAT 環境変数が設定済み or az login 済み
#   - jq がインストール済み
#   - project と organization は az devops configure -d で設定済み（推奨）
# ---

set -euo pipefail

# $TEMP が空の場合 "$TEMP/foo.json" が "/foo.json"（ルート）になるのを防ぐ
: "${TEMP:?TEMP is not set or empty}"

PR_ID=""
CONTENT=""
FILE=""
LINE=""
THREAD_ID=""
PARENT_COMMENT_ID="0"
STATUS="1"  # 1=active
PROJECT=""
REPO=""
ORG=""
API_VERSION="7.1"

usage() {
  sed -n '2,/^# ---$/p' "$0" | sed 's/^# \?//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --pr-id) PR_ID="$2"; shift 2 ;;
    --content) CONTENT="$2"; shift 2 ;;
    --file) FILE="$2"; shift 2 ;;
    --line) LINE="$2"; shift 2 ;;
    --thread-id) THREAD_ID="$2"; shift 2 ;;
    --parent-comment-id) PARENT_COMMENT_ID="$2"; shift 2 ;;
    --status) STATUS="$2"; shift 2 ;;
    --project) PROJECT="$2"; shift 2 ;;
    --repository) REPO="$2"; shift 2 ;;
    --organization) ORG="$2"; shift 2 ;;
    --api-version) API_VERSION="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# 必須引数チェック
if [ -z "$PR_ID" ] || [ -z "$CONTENT" ]; then
  echo "ERROR: --pr-id と --content は必須です" >&2
  usage
fi

# project と repository が未指定なら PR 詳細から取る
if [ -z "$PROJECT" ] || [ -z "$REPO" ]; then
  echo "→ PR #$PR_ID から project と repositoryId を取得します..." >&2
  ORG_OPT=""
  [ -n "$ORG" ] && ORG_OPT="--organization $ORG"
  PROJECT_OPT=""
  [ -n "$PROJECT" ] && PROJECT_OPT="--project $PROJECT"

  # shellcheck disable=SC2086
  PR_INFO=$(az repos pr show --id "$PR_ID" $ORG_OPT $PROJECT_OPT --output json)
  [ -z "$PROJECT" ] && PROJECT=$(echo "$PR_INFO" | jq -r '.repository.project.name')
  [ -z "$REPO" ] && REPO=$(echo "$PR_INFO" | jq -r '.repository.id')
  echo "   project=$PROJECT, repoId=$REPO" >&2
fi

# リクエストボディを組み立て
if [ -n "$THREAD_ID" ]; then
  # --thread-id 指定時に --parent-comment-id が省略された場合、先頭コメント(id=1)へ返信
  [ "$PARENT_COMMENT_ID" = "0" ] && PARENT_COMMENT_ID="1"

  # 既存スレッドへの返信
  BODY=$(jq -n \
    --arg content "$CONTENT" \
    --arg parent "$PARENT_COMMENT_ID" \
    '{parentCommentId: ($parent|tonumber), content: $content, commentType: 1}')

  RESOURCE="pullRequestThreadComments"
  ROUTE_PARAMS=(
    project="$PROJECT"
    repositoryId="$REPO"
    pullRequestId="$PR_ID"
    threadId="$THREAD_ID"
  )
else
  # 新規スレッド
  if [ -n "$FILE" ] && [ -n "$LINE" ]; then
    # ファイル位置指定あり
    # MSYS_NO_PATHCONV=1: $FILE が /src/foo.ts のとき Git Bash の MSYS パス変換で
    # C:/Program Files/Git/src/foo.ts に展開されるのを防ぐ
    BODY=$(MSYS_NO_PATHCONV=1 jq -n \
      --arg content "$CONTENT" \
      --arg file "$FILE" \
      --arg line "$LINE" \
      --arg status "$STATUS" \
      '{
        comments: [{parentCommentId: 0, content: $content, commentType: 1}],
        status: ($status|tonumber),
        threadContext: {
          filePath: $file,
          rightFileStart: {line: ($line|tonumber), offset: 1},
          rightFileEnd: {line: ($line|tonumber), offset: 200}
        }
      }')
  else
    # ファイル位置指定なし（PR 全体への一般コメント）
    BODY=$(jq -n \
      --arg content "$CONTENT" \
      --arg status "$STATUS" \
      '{
        comments: [{parentCommentId: 0, content: $content, commentType: 1}],
        status: ($status|tonumber)
      }')
  fi

  RESOURCE="pullRequestThreads"
  ROUTE_PARAMS=(
    project="$PROJECT"
    repositoryId="$REPO"
    pullRequestId="$PR_ID"
  )
fi

# 実行内容を表示してから POST
echo "→ リクエストボディ:" >&2
echo "$BODY" | jq '.' >&2
echo "" >&2

ORG_OPT=""
[ -n "$ORG" ] && ORG_OPT="--organization $ORG"

# /dev/stdin は Windows Git Bash で C:/Program Files/Git/dev/stdin に展開されて失敗するため
# $TEMP の一時ファイル経由で渡す
echo "$BODY" > "$TEMP/create_thread_body.json"

# shellcheck disable=SC2086
RESULT=$(az devops invoke \
  --area git \
  --resource "$RESOURCE" \
  --route-parameters "${ROUTE_PARAMS[@]}" \
  --http-method POST \
  --in-file "$TEMP/create_thread_body.json" \
  --api-version "$API_VERSION" \
  $ORG_OPT \
  --output json)

echo "$RESULT" | jq '.'

if [ -n "$THREAD_ID" ]; then
  COMMENT_ID=$(echo "$RESULT" | jq -r '.id')
  echo "✓ コメント #$COMMENT_ID を thread #$THREAD_ID に追加しました" >&2
else
  NEW_THREAD_ID=$(echo "$RESULT" | jq -r '.id')
  echo "✓ スレッド #$NEW_THREAD_ID を作成しました" >&2
fi
