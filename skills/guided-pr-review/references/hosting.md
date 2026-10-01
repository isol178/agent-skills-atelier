# ホスティングサービス別の操作

SKILL.md の各フェーズで必要になる操作を、サービスごとにまとめる。
コマンドは例であり、実行前に `--help` や公式ドキュメントで手元のバージョンの書式を確かめる。

## どのサービスでも揃える情報

| 用途 | 必要な情報 | 使うフェーズ |
|------|-----------|-------------|
| 差分の基準 | PR SHA（source の最新 commit）、target ブランチ名 | 1-1, 1-2 |
| 差分の検算 | サービスが表示する変更ファイル数 | 1-2 |
| source を取れないとき | PR 用 ref の名前 | 1-2 |
| 既出の判定 | 既存スレッド（本文、場所、解決状態、指摘者）、レビュー状況 | 1-4 |
| 行コメントの投稿 | ファイルパス、PR SHA 側の行番号、（必要なら）PR SHA | 3-2 |
| 返信の投稿 | 返信先のスレッド / コメントの ID | 3-2 |

remote 名について: 以下の `origin` は PR が属するリポジトリを指す remote とする。fork 運用では `upstream` などになるので、`git remote -v` で確かめて読み替える。

## GitHub（`gh`）

```bash
# PR の特定（番号なしなら現在のブランチの PR）
gh pr view <N> --json number,title,author,headRefOid,headRefName,baseRefName,isDraft,state,changedFiles,additions,deletions

# 差分の取得
git fetch origin <baseRefName>
git fetch origin pull/<N>/head        # fork からの PR でも取れる。結果は FETCH_HEAD
git rev-parse FETCH_HEAD              # headRefOid と一致するか確かめる

# 既存コメント
gh api --paginate repos/{owner}/{repo}/pulls/<N>/comments    # 行コメント
gh api --paginate repos/{owner}/{repo}/issues/<N>/comments   # PR 全体へのコメント
gh pr view <N> --json reviews                                 # レビュー状況
# 解決状態は REST では取れないので GraphQL の reviewThreads { isResolved } を使う
```

投稿（本文はファイルに書いて渡すと、改行や引用符で崩れない）:

```bash
# 行コメント（side=RIGHT が PR SHA 側）。範囲なら start_line と start_side も付ける
gh api repos/{owner}/{repo}/pulls/<N>/comments \
  -f commit_id=<PR SHA> -f path=<path> -F line=<line> -f side=RIGHT -F body=@comment.md

# 既存の行コメントへの返信
gh api repos/{owner}/{repo}/pulls/<N>/comments/<comment_id>/replies -F body=@reply.md

# PR 全体へのコメント
gh pr comment <N> --body-file comment.md
```

複数の行コメントをまとめて 1 つのレビューとして出したい場合は、`POST repos/{owner}/{repo}/pulls/<N>/reviews` に `event: COMMENT` と `comments` 配列を渡す。投票と誤解されないよう、`event` に `APPROVE` / `REQUEST_CHANGES` はユーザーの指示が無い限り使わない。

## Azure DevOps（`az repos pr` / `az devops invoke`）

`azure-devops-pr` skill が使えるなら、そちらの `references/pr-comment-thread.md` と `scripts/create_thread.sh` を使う。以下は要点だけ。

```bash
# PR の特定
az repos pr list --source-branch <branch> --status active
az repos pr show --id <N> --query "{sha:lastMergeSourceCommit.commitId, source:sourceRefName, target:targetRefName, status:status, isDraft:isDraft}"

# 差分の取得
git fetch origin <target>
git fetch origin <source>                  # 取れなければ PR 用 ref を使う
git fetch origin refs/pull/<N>/merge       # PR 用 ref はマージ commit。source 側は FETCH_HEAD^2
```

- 既存スレッド: `az devops invoke --area git --resource pullRequestThreads` で取得する。システムが作るスレッド（commit の push 通知など）は、コメントの `commentType` が `text` のものだけに絞って除く。解決状態はスレッドの `status`（`active` / `fixed` / `closed` など）で判断する
- 行コメント: `threadContext.rightFileStart` / `rightFileEnd` が PR SHA 側の行。`create_thread.sh --file <path> --line <line>` はこれを組み立てる
- 返信: `create_thread.sh --thread-id <id> --parent-comment-id <id>`
- Windows では az CLI の前に `export PYTHONUTF8=1 PYTHONIOENCODING=utf-8` を付けないと、日本語が文字化けすることがある。一時ファイルは `/tmp` ではなく `$TEMP` かスクラッチパッドに置く

## GitLab（`glab`）

```bash
glab mr view <N> --output json                     # sha, target_branch, source_branch
git fetch origin <target_branch>
git fetch origin refs/merge-requests/<N>/head      # fork からの MR でも取れる
```

既存のディスカッションの取得と行コメントの投稿は、`glab api projects/:id/merge_requests/<N>/discussions` を使う。行コメントには `position`（`base_sha` / `start_sha` / `head_sha` / `new_path` / `new_line`）が必要で、値は MR の `diff_refs` から取る。

## その他のサービス

次を順に確かめ、分かったことをユーザーに伝えてから進める。

1. PR のメタデータ（PR SHA、target ブランチ）を取る CLI か API があるか
2. fork からの PR の head を fetch できる ref があるか
3. 既存スレッドを一覧できるか
4. 行コメントの位置をどう指定するか（新しい側の行番号か、差分内の位置か）

取得や投稿の手段が無い場合は、ユーザーに Web UI で PR SHA と既存コメントを確かめてもらう。文面は投稿先と本文をコピーしやすい形で渡す。
