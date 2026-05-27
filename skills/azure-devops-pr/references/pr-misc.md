# PR その他操作（reviewer / vote / work-item / update / abandon）

PR 作成・コメント・検索以外の操作。`az repos pr` のサブコマンドでカバーされる。

## 目次

1. レビュアー追加・削除
2. 投票（approve / reject / waiting）
3. Work Item の紐付け・解除
4. PR 更新（タイトル・説明・draft 切替・auto-complete 切替）
5. PR を abandon / reactivate
6. ポリシー状況の確認
7. PR をローカルに checkout

---

## 1. レビュアー追加・削除

### 追加

```bash
# 任意レビュアー
az repos pr reviewer add --id $PR_ID --reviewers "alice@example.com" "bob@example.com"

# 必須レビュアー
az repos pr reviewer add --id $PR_ID --reviewers "alice@example.com" --required true
```

### 一覧

```bash
az repos pr reviewer list --id $PR_ID --output table
```

### 削除

```bash
az repos pr reviewer remove --id $PR_ID --reviewers "alice@example.com"
```

注：ブランチポリシーで自動追加された必須レビュアーは削除できない。

---

## 2. 投票（approve / reject / waiting）

```bash
# 承認
az repos pr set-vote --id $PR_ID --vote approve

# 承認だが提案付き
az repos pr set-vote --id $PR_ID --vote approve-with-suggestions

# 待機（後で見る）
az repos pr set-vote --id $PR_ID --vote wait-for-author

# 拒否
az repos pr set-vote --id $PR_ID --vote reject

# 投票リセット
az repos pr set-vote --id $PR_ID --vote reset
```

`--vote` の値：`approve` / `approve-with-suggestions` / `reset` / `reject` / `wait-for-author`

注意：reject や approve は重い決定。スキルは**ユーザーの最終承認を取ってから**実行する。

---

## 3. Work Item の紐付け・解除

```bash
# 紐付け
az repos pr work-item add --id $PR_ID --work-items 1234 1235

# 一覧
az repos pr work-item list --id $PR_ID --output table

# 解除
az repos pr work-item remove --id $PR_ID --work-items 1234
```

PR 説明に `AB#1234` 形式で書くと自動リンクされる場合もある（Azure Boards 統合時）。

---

## 4. PR 更新

### タイトル・説明を変更

```bash
az repos pr update --id $PR_ID --title "新しいタイトル"
az repos pr update --id $PR_ID --description "新しい説明（Markdown 可）"
```

### draft の切替

```bash
# Draft 化
az repos pr update --id $PR_ID --draft true

# Draft 解除（公開）
az repos pr update --id $PR_ID --draft false
```

### auto-complete の切替

```bash
# 有効化
az repos pr update --id $PR_ID --auto-complete true \
  --squash true \
  --delete-source-branch true

# 無効化
az repos pr update --id $PR_ID --auto-complete false
```

### マージ方法の指定（auto-complete と併用）

```bash
az repos pr update --id $PR_ID \
  --auto-complete true \
  --squash true \
  --delete-source-branch true \
  --merge-commit-message "feat: ...（squash 後のメッセージ）"
```

---

## 5. PR を abandon / reactivate

### Abandon（取り下げ）

```bash
az repos pr update --id $PR_ID --status abandoned
```

**重要：abandon は取り下げ操作。実行前にユーザーの最終確認を取る**。後で reactivate できるが、レビュー履歴やコメントが見づらくなる。

### Reactivate

```bash
az repos pr update --id $PR_ID --status active
```

### Complete（マージ実行）

```bash
az repos pr update --id $PR_ID --status completed
```

**重要：complete は取り返しがつかない**。auto-complete を使うほうが安全（ポリシー満たしてから自動マージ）。手動 complete はユーザーが明示的に「マージ実行」と言った時だけ。

---

## 6. ポリシー状況の確認

PR がブランチポリシーを満たしているかを見る：

```bash
az repos pr policy list --id $PR_ID --output table
```

出力例：
```
Evaluation ID  Policy                              Blocking  Status
-------------- ----------------------------------- --------- ---------
xxxx-xxxx      Minimum number of reviewers (1)     True      Approved
yyyy-yyyy      Build validation                    True      Approved
zzzz-zzzz      Comment requirements                False     Approved
```

policy が失敗してマージできない場合、ここを見ると原因が分かる。

### Build policy のキュー再実行

CI ビルドが失敗・キャンセル後、再実行したい場合：

```bash
az repos pr policy queue --evaluation-id <evaluation-id>
```

`evaluation-id` は `policy list` の出力から取る。

---

## 7. PR をローカルに checkout

レビュー時に PR ブランチをローカルで動かしたい時：

```bash
az repos pr checkout --id $PR_ID
```

これは内部的に `git fetch` + `git checkout <branch>` を実行する。ローカルに未コミット変更があると失敗する。

---

## クイックリファレンス：よくある組み合わせ

### 「PR #42 をレビューしてマージ可能なら auto-complete に」

```bash
PR_ID=42

# 1. 状態確認
az repos pr show --id $PR_ID --query "{title, status, mergeStatus, isDraft}" -o table
az repos pr policy list --id $PR_ID -o table

# 2. 内容確認後、承認
az repos pr set-vote --id $PR_ID --vote approve

# 3. auto-complete 設定（ポリシー満たし次第マージ）
az repos pr update --id $PR_ID \
  --auto-complete true \
  --squash true \
  --delete-source-branch true
```

### 「自分の PR にタイトル/説明追記してレビュアー追加」

```bash
PR_ID=42

az repos pr update --id $PR_ID \
  --title "feat(auth): JWT 認証導入" \
  --description "$(cat <<'EOF'
## 概要
...

## 動作確認
- [x] ローカルテストパス
- [ ] ステージング動作確認待ち
EOF
)"

az repos pr reviewer add --id $PR_ID --reviewers "alice@example.com" --required true
```
