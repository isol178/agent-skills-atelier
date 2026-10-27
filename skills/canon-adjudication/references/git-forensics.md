# 来歴調査の Git コマンドと罠

SKILL.md §3 の補足。`scripts/trace_divergence.py` が使えないとき、または出力の先を掘るときに読む。

## 最初に確認すること

```bash
git rev-parse --is-shallow-repository   # true なら履歴が切れている → git fetch --unshallow
git status --short                      # 作業中の変更で乖離が生じていないか
git log --oneline <base>..HEAD          # このブランチで乖離が生じていないか（<base> は main 等）
git log -1 --format='%h %ad' origin/main  # 手元の main が古すぎないか（必要なら fetch）
```

CI やクラウドの環境では `--depth` 付きの clone が普通にある。shallow のまま調べると、境界のコミットがすべての行を「作った」ように見える。

## 問い別のコマンド

| 問い | コマンド |
|---|---|
| この行範囲を変えたコミットは | `git log -L 40,52:docs/api.md --no-patch --format='%h %as %an %s'`（差分も見るなら `--no-patch` を外す。ファイルの改名は追跡される） |
| この関数を変えたコミットは | `git log -L :get_user:src/users.py --no-patch --format='%h %as %an %s'` |
| この値・識別子が入った／消えたのは | `git log -S 'MAX_RETRIES = 3' --format='%h %as %s'`（出現回数の変化）、`git log -G 'MAX_RETRIES\s*=' --format='%h %as %s'`（その行の追加・削除。値の変更はこちら）。他のブランチも含めるなら `--all` |
| ファイル単位の履歴（改名を跨ぐ） | `git log --follow --format='%h %as %s' -- docs/api.md` |
| この行の由来 | `git blame -w -M -C -C -C -L 40,52 src/users.py`（空白変更を無視し、ファイル内外の移動・コピーを遡る）。整形コミットを飛ばすなら `--ignore-revs-file .git-blame-ignore-revs` または `--ignore-rev <sha>` |
| さらに1つ前の版での由来 | `git blame -L 40,52 <sha>^ -- src/users.py` |
| ある時点の内容 | `git show <sha>:<path>`。日付で指定するなら `git show $(git rev-list -1 --before='2023-06-01' main):<path>`（`main@{日付}` は手元の reflog に依存するので使わない） |
| 2つのファイルを同時に変えたコミット | `comm -12 <(git log --format=%H --follow -- docs/api.md \| sort) <(git log --format=%H --follow -- src/users.py \| sort)` |
| どのリリースに入ったか | `git tag --contains <sha>`、`git describe --contains <sha>` |
| どのブランチ経由で入ったか | `git branch -a --contains <sha>`、`git log --merges --ancestry-path --format='%h %s' <sha>..main \| tail -1`（main に取り込んだマージコミット） |
| 挙動がいつ変わったか（履歴が長く、変化が複数のコミットに散っている） | 文書どおりの挙動を確かめるテストを用意して `git bisect start HEAD <good-sha>` → `git bisect run <テストコマンド>` |

## コミットから PR・issue を引く

- 件名から: マージコミットの「Merge pull request #123」、squash merge の件名末尾の「(#123)」、本文の `Closes #45`、`JIRA-123`、`AB#123`（Azure Boards）
- マージコミットから: 上の `--ancestry-path` で取り込んだマージを特定し、その件名から PR 番号を得る
- ホスティングの CLI / MCP が使えるなら、SHA から PR を検索する（GitHub なら `gh pr list --search <sha> --state merged`、または `gh api repos/{owner}/{repo}/commits/<sha>/pulls`）
- PR の説明・レビューコメント・リンクされた issue は、コミットメッセージより詳しく意図を残していることが多い。squash merge では PR が意図の単位になる

## 履歴が誤誘導する罠

| 罠 | 何が起きるか | 対処 |
|---|---|---|
| shallow clone | 境界コミットが全行の作者に見える | `git fetch --unshallow`。できなければ来歴の証拠を弱く扱う |
| 整形・一括置換 | formatter や lint の一括修正が最終変更に見える | `blame -w`、`--ignore-rev`、スクリプトの `[mass]` `[blame-ignore-revs]` を飛ばして1つ前を見る |
| ファイル移動・分割 | 移動コミットが「作成」に見える | `log --follow`（単一ファイル）、`blame -C -C -C`（ファイルを跨ぐコード移動）。`log -L` は改名を追跡する |
| コメントのコピー | コメントはコードと一緒に移動・複製されるので、「書かれた」コミットがコピーにすぎないことがある | `blame -C -C -C` で元を辿り、元の場所で書かれた時点の真偽を確かめる |
| squash merge | 複数の意図が1コミットに混ざり、「refactor と挙動変更」が同居する | PR の説明とレビュー議論を読む。差分のうち該当部分だけを意図の判断に使う |
| rebase・cherry-pick | 同じ変更が別 SHA で2回現れる。committer date が書き換わり、順序が実際の作業順と違う | `git log --cherry-mark`。作業順は author date（`%ad`）、main に入った順は `--first-parent main` で見る |
| マージ衝突の解消 | 衝突の解消で片方の変更が黙って消える。差分は通常の `git show` に出にくい | `git show --remerge-diff <merge-sha>`（Git 2.36 以降）で、自動マージの結果から人がどう変えたかを見る。`log -L` はマージコミットも表示する |
| revert と再 revert | 同じ変更の出入りで、最終状態の意図が読みにくい | revert の本文（理由）と、再 revert の issue を読む |
| 長命ブランチ | author date は古いのに、main に入ったのはずっと後 | main に入った時点は `git log --first-parent main` で取り込んだマージを見る |
| 生成物・vendored | 履歴は生成器や取り込みの実行記録で、意図を語らない | 生成元・取り込み元の履歴を見る |
| bot のコミット | 依存更新 bot の変更が挙動を変えている | 依存の CHANGELOG を読み、挙動変更が依存側由来か確かめる |

## Git の外にある文書

Wiki・Confluence・Google Docs などの文書も、同じ問いで調べる。

1. その文書の版履歴から、該当する記述が今の形になった日付を得る
2. その日付時点の実装を `git show $(git rev-list -1 --before='<日付>' main):<path>` で見て、書かれた時点で真だったかを確かめる
3. その日付以降に実装の該当箇所を変えたコミットを `git log --since='<日付>' -L ...` で列挙し、意図を読む

版履歴が取れない文書は、来歴の証拠を持たない。依存（§4）と整合・理由（§5）の比重を上げ、確信度を1段下げる。
