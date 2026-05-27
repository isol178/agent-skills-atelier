---
name: azure-devops-pr
description: Azure DevOps の Pull Request を Azure CLI (az repos pr) と REST API で操作するスキル。PR の作成・一覧・詳細取得・検索・コメント/スレッド追加・レビュアー操作・投票・Work Item 紐付け・タイトル/説明更新などをカバーする。ユーザーが「PR 作って」「プルリク出して」「az repos pr で…」「Azure DevOps の PR にコメント」「レビューコメント残して」「この PR の一覧見せて」「自分が出した PR」「レビュアーになってる PR」「PR をマージできる状態にして」のような発話をした時、またはカレントディレクトリが Azure DevOps リポジトリ（remote が dev.azure.com / visualstudio.com / 社内 Azure DevOps Server）の git リポジトリで PR まわりの作業をしているときに必ず使う。git のブランチ作成・コミット・プッシュは対象外（人間がやる前提）。
---

# azure-devops-pr

Azure DevOps の Pull Request を CLI ベースで扱うためのスキル。GitHub の `gh pr` 相当の操作を、`az repos pr` と（CLI でカバーされない部分は）`az devops invoke` 経由の REST API で実現する。

## このスキルが解く問題

`az repos pr` は PR の基本操作（create / list / show / update / reviewer / work-item / set-vote）をカバーするが、以下の重要な機能を**持たない**：

- **PR コメント・スレッドの作成/取得/更新** → REST API 直叩きが必要（`az devops invoke`）
- **Azure DevOps Server 環境での全機能** → CLI 自体が非対応、REST API のみ

このスキルはこの隙間を埋め、ユーザーが「PR にコメントしておいて」と言ったときに躊躇なく実行できるようにする。

## まず最初にやること（毎回）

### 1. コンテキスト確認

ユーザーが何をしたいかに応じて、適切な references ファイルを読み込む：

| ユーザーの意図 | 読むファイル |
|---|---|
| PR を作りたい | `references/pr-create.md` |
| PR を探す・一覧見たい・詳細知りたい | `references/pr-list-show.md` |
| PR にコメント・スレッド追加したい | `references/pr-comment-thread.md` |
| レビュアー追加・投票・Work Item 紐付け・タイトル更新など | `references/pr-misc.md` |
| エラーが出た / Azure DevOps Server 環境 | `references/azure-devops-server.md` |

複数該当する場合は、まず一番中心の用件のファイルから読む。後から必要になったら追加で読む。

### 2. 環境前提を確認

PR 操作を始める前に、以下を確認する：

```bash
# Azure CLI と DevOps 拡張が入っているか
az --version | head -5
az extension show --name azure-devops 2>/dev/null | grep version || echo "azure-devops extension not installed"

# ログイン状態（PAT 環境変数 or az login）
echo "AZURE_DEVOPS_EXT_PAT is set: $([ -n "$AZURE_DEVOPS_EXT_PAT" ] && echo yes || echo no)"

# 現在のリポジトリの remote（Azure DevOps かどうか判定）
git remote -v 2>/dev/null | head -3
```

拡張が入ってなければ：

```bash
az extension add --name azure-devops
```

remote が `dev.azure.com` でも `visualstudio.com` でも `*.azure.com`（社内ホスト）でもない場合、Azure DevOps ではないので、ユーザーに状況を確認する。

### 3. 認証方式の判定

優先順位：

1. **`AZURE_DEVOPS_EXT_PAT` 環境変数**が設定されていれば、それを使う（CI/CD や社内環境で一般的）
2. **`az login` 済み**なら、それを使う（Azure DevOps Services 環境で一般的）
3. どちらもなければ、ユーザーに PAT の設定方法を案内する：

   ```bash
   # 一時的に
   export AZURE_DEVOPS_EXT_PAT=<your-pat>

   # または az login
   az login
   ```

   PAT のスコープは最低限「Code (Read & Write)」、コメント書く場合は「Code (Read, Write, & Manage)」が必要。

### 4. organization / project / repository の解決

`az repos pr` 系コマンドは、これら3つが必要。優先順位：

1. **コマンドライン引数で明示**された場合はそれを使う
2. **`az devops configure -d` で設定済み**ならそれが使われる
3. **git config から自動検出**（`--detect true` がデフォルト、git remote から推定）

明示が必要な場合：

```bash
# 一度設定すれば以降のコマンドで省略可
az devops configure --defaults \
  organization=https://dev.azure.com/<org-name> \
  project=<project-name>
```

## 基本ワークフロー

ユーザーの依頼を、以下のステップで処理する：

### ステップ A. 意図を解釈する

ユーザーの発話から、必要な情報をできる限り抽出する：

- **PR ID が明示されているか？**（例：「PR #42 にコメント」「!42」「pullrequest/42」）
- **ブランチ名が分かるか？**（例：「feature/login」「現在のブランチ」「main へのマージ」）
- **タイトル・説明はあるか？**
- **レビュアー指定は？**（メールアドレス / 表示名 / グループ名）
- **Work Item ID は？**（例：「AB#1234」「WI 5678」）

足りない情報は推定するか、ユーザーに聞く。推定する場合は **何をどう推定したかを明示**してから実行する。

### ステップ B. コマンドを構築する

references から該当パターンを参照しつつ、コマンドを組み立てる。実行前に **ユーザーに見せて確認**する習慣をつける。特に以下は明示すること：

- 作成する PR のタイトル・説明・ソース/ターゲットブランチ
- コメントの内容と投稿先（ファイル位置 or 一般スレッド）
- レビュアー / Work Item / ラベルの変更内容

### ステップ C. 実行と結果整形

実行したら、結果から PR の URL と ID をユーザーに返す。`--output json` で取って必要なフィールドを抜き出す：

```bash
# PR 作成の典型例（実行後にこういう情報を返す）
echo "Created PR #${PR_ID}: ${PR_TITLE}"
echo "URL: ${PR_URL}"
```

エラーが出たら、エラーメッセージを引用して、想定される原因を提示する。よくあるエラーは `references/azure-devops-server.md` の末尾参照。

## このスキルのスコープ外

以下は**やらない**（明示的に依頼されてもこのスキルからは外れる）：

- **git 操作**：ブランチ作成・コミット・プッシュ・rebase は人間がやる前提。スキルは「ローカル変更がプッシュ済み」を出発点にする。ただし、PR 作成時に「ソースブランチが remote に push されているか」だけは確認する（プッシュされていなければ「先に `git push -u origin <branch>` してください」と案内）。
- **PR のマージ完了**：`az repos pr update --auto-complete true` での自動完了予約は OK だが、強制マージや、ポリシー違反でのマージ強行はしない。
- **ブランチポリシー作成**：`az repos policy` 系は別スキル。
- **CI/CD パイプライン操作**：`az pipelines` 系は別スキル。

## 安全側に倒すべきポイント

1. **PR の `abandon`（取り下げ）と完了（complete）は、必ずユーザーに最終確認を取ってから実行**する。これらは取り返しがつかない（abandon は復活可能だが、complete は不可）。
2. **`--bypass-policy true` は、明示的に依頼された時だけ**使う。スキルが勝手にポリシー無視を提案しない。
3. **`--squash true` / `--delete-source-branch true` は、リポジトリの慣習を確認してから**使う。
4. **PAT を会話に貼り付けるよう促さない**。ユーザーが PAT を貼ってきた場合も、コマンドに直書きせず環境変数経由を案内する。

## ファイル構成

```
azure-devops-pr/
├── SKILL.md                       ← このファイル
├── references/
│   ├── pr-create.md               ← PR 作成（ブランチ推定・オプション一覧・典型パターン）
│   ├── pr-list-show.md            ← 検索・一覧・詳細・JMESPath クエリレシピ
│   ├── pr-comment-thread.md       ← コメント/スレッド（az devops invoke で REST 叩く）
│   ├── pr-misc.md                 ← reviewer/vote/work-item/update など
│   └── azure-devops-server.md     ← Server 環境のフォールバック・トラブルシュート
└── scripts/
    └── create_thread.sh           ← スレッド作成の薄いラッパー
```

references は**必要になったときに**読む。最初から全部読まない（コンテキスト節約のため）。
