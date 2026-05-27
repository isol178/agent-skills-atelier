# PR 作成（az repos pr create）

`az repos pr create` で PR を作成する。ブランチ情報をできる限り**自動で推定**して、ユーザーに対話的に聞く回数を最小化する。

## 目次

1. ブランチの推定戦略
2. 最小コマンドと典型パターン
3. オプション全リスト
4. タイトル・説明の自動生成
5. よくあるエラー

---

## 1. ブランチの推定戦略

PR を作るには **ソースブランチ** と **ターゲットブランチ** が必要。以下の順序で推定する：

### ソースブランチ（`--source-branch`）

1. ユーザーが明示していればそれを使う
2. 現在のブランチを使う：
   ```bash
   git branch --show-current
   ```
3. ただし、現在のブランチが `main` / `master` / `develop` などの保護されたブランチなら、ユーザーに確認する

### ターゲットブランチ（`--target-branch`）

1. ユーザーが明示していればそれを使う
2. 省略した場合、`az repos pr create` はデフォルトブランチを自動で使う（`--target-branch` を渡さなければよい）。
3. プロジェクトの慣習が分かる場合（例：`develop` への PR が常識のリポジトリ）はそれを使う

### ソースブランチが remote に push されているかの確認

PR 作成前に**必ず**確認する：

```bash
BRANCH=$(git branch --show-current)
git ls-remote --heads origin "$BRANCH" | grep -q "refs/heads/$BRANCH$" && echo "OK: pushed" || echo "NOT pushed yet"
```

push されていなければ、ユーザーに「先に `git push -u origin $BRANCH` してください」と案内する。スキルからは git push しない。

---

## 2. 最小コマンドと典型パターン

### 最小コマンド

```bash
az repos pr create \
  --title "<title>" \
  --description "<description>"
```

これでカレントの git config から org/project/repo を検出し、現在のブランチをソース、デフォルトブランチをターゲットとして PR を作る。

### 典型パターン: レビュアーと Work Item を指定

```bash
az repos pr create \
  --title "feat(auth): JWT トークン認証を追加" \
  --description "$(cat <<'EOF'
## 概要
JWT ベースの認証機構を導入。

## 変更点
- AuthService に sign / verify メソッド追加
- middleware/auth.ts を新規作成
- 既存の Cookie 認証は後続 PR で削除予定

## 動作確認
- ローカルで `npm run test:auth` がパス
EOF
)" \
  --required-reviewers "alice@example.com bob@example.com" \
  --optional-reviewers "frontend-team" \
  --work-items 1234 1235 \
  --transition-work-items true
```

### 典型パターン: ドラフト PR

WIP の段階で投げる場合（通知も最小化される）：

```bash
az repos pr create \
  --title "WIP: パフォーマンス最適化の試験実装" \
  --description "approach の方向性を相談したい段階。レビューはまだ不要。" \
  --draft true
```

### 典型パターン: auto-complete + squash + delete-source-branch

CI と policy が通り次第マージ、squash で履歴クリーン、ブランチ自動削除：

```bash
az repos pr create \
  --title "fix(api): null チェック漏れを修正" \
  --description "..." \
  --auto-complete true \
  --squash true \
  --delete-source-branch true
```

### 典型パターン: 明示的に組織・プロジェクト・リポジトリを指定

defaults が設定されていない場合：

```bash
az repos pr create \
  --organization https://dev.azure.com/myorg \
  --project MyProject \
  --repository MyRepo \
  --source-branch feature/login \
  --target-branch main \
  --title "..." \
  --description "..."
```

### JSON 出力からの値抽出

スクリプト的に PR ID と URL を取りたい場合：

```bash
RESULT=$(az repos pr create --title "..." --description "..." --output json)
PR_ID=$(echo "$RESULT" | jq -r '.pullRequestId')
PR_URL=$(echo "$RESULT" | jq -r '.repository.webUrl + "/pullrequest/" + (.pullRequestId|tostring)')
echo "Created PR #${PR_ID}: ${PR_URL}"
```

---

## 3. オプション全リスト

`az repos pr create` の主要オプション：

| オプション | 用途 |
|---|---|
| `--title` | PR タイトル |
| `--description` | PR 説明（Markdown 可、複数行は `--description "$(cat <<EOF...EOF)"` パターン） |
| `--source-branch` | ソースブランチ名（例：`feature/login`、`refs/heads/` プレフィックス不要） |
| `--target-branch` | ターゲットブランチ名（省略時はリポジトリのデフォルトブランチ） |
| `--repository` | リポジトリ名 or ID |
| `--project` | プロジェクト名 or ID |
| `--organization` | 組織 URL（`https://dev.azure.com/<org>`） |
| `--draft` | `true` でドラフト PR |
| `--auto-complete` | `true` でポリシー充足時に自動マージ予約 |
| `--squash` | マージ方式を squash に |
| `--delete-source-branch` | マージ後にソースブランチを自動削除 |
| `--merge-commit-message` | マージコミットメッセージ（auto-complete と併用） |
| `--bypass-policy` | `true` でブランチポリシー無視（要権限、原則使わない） |
| `--bypass-policy-reason` | bypass の理由（監査ログに残る） |
| `--required-reviewers` | 必須レビュアー（スペース区切り、メール or 表示名） |
| `--optional-reviewers` | 任意レビュアー |
| `--work-items` | 紐付ける Work Item ID（スペース区切り） |
| `--transition-work-items` | `true` で関連 Work Item を次の状態に遷移 |
| `--labels` | ラベル（スペース区切り） |
| `--open` | 作成後にブラウザで開く |
| `--detect` | `true` で git config から org/project/repo を自動推定（デフォルト） |
| `--output` | 出力形式（json / table / tsv） |

---

## 4. タイトル・説明の自動生成

ユーザーがタイトルや説明を明示しなかった場合、以下の素材から生成案を作って**ユーザーに見せて確認**する：

### タイトルの素材

優先順位：
1. ブランチ名から拾えるパターン（例：`feature/JIRA-1234-add-login` → `feat: add login (JIRA-1234)`）
2. 最後のコミットメッセージ：
   ```bash
   git log -1 --pretty=%s
   ```
3. ブランチ作成後の全コミットメッセージから推測：
   ```bash
   git log <target-branch>..HEAD --pretty=%s
   ```

### 説明の素材

```bash
# ブランチ作成後の差分コミット一覧
git log <target-branch>..HEAD --pretty="- %s" --no-merges

# 変更ファイルのサマリ
git diff <target-branch>..HEAD --stat
```

これらから「変更概要」「変更ファイル」セクションを組み立てて、テンプレートに流し込む：

```markdown
## 概要
<推測した要約>

## 変更点
<コミットメッセージから箇条書き>

## 動作確認
- [ ] <要確認項目>
```

生成案は**必ずユーザーに見せて承認をもらってから** `az repos pr create` を実行する。

---

## 5. よくあるエラー

### `TF401179: An active pull request for the source and target branch already exists`

同じソース→ターゲットの組み合わせで既に active な PR がある。既存 PR を更新する方針に切り替える：

```bash
# 既存 PR の ID を探す
az repos pr list --source-branch <branch> --status active --output table
# 見つかったら update
az repos pr update --id <id> --title "..." --description "..."
```

### `Source branch ... does not exist`

ソースブランチが remote に push されていない。`git push -u origin <branch>` を案内する。

### `TF401019: The Git repository ... is either disabled or not found`

`--detect` が誤った repo を拾った可能性。`--organization` `--project` `--repository` を明示する。

### `Azure DevOps CLI commands aren't supported for Azure DevOps Server`

→ `references/azure-devops-server.md` 参照。REST API 直叩きにフォールバック。
