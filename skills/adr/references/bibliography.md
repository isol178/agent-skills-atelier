# 参考文献

本スキルが採用した方針の出典。エージェントが「なぜこのスキルがこうなっているか」を辿る時、またはユーザーから方法論的な根拠を問われた時に参照する。

---

## ADR の原典

- **Michael Nygard, "Documenting Architecture Decisions" (2011)**
  - URL: https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions
  - ADR 概念を提唱した原典。Status / Context / Decision / Consequences の4セクション構成。

- **Olaf Zimmermann et al., "Sustainable Architectural Decisions" (IEEE Software 30(6), 2013)**
  - URL: https://www.infoq.com/articles/sustainable-architectural-design-decisions/
  - Y-statement 形式の出典。`In the context of <C>, facing <concern>, we decided for <option> and neglected <others>, to achieve <quality>, accepting <downside>, because <rationale>` の7要素テンプレ。

---

## 採用テンプレート

- **MADR 4.0.0 (2024-09-17 リリース)**
  - URL: https://adr.github.io/madr/
  - 本スキルが採用するベース形式。Context and Problem Statement / Decision Drivers / Considered Options / Decision Outcome (Consequences + Confirmation) / Pros and Cons of the Options / More Information のセクション構成。
  - 4.0.0 の主な変更: Validation → Confirmation にリネームし Decision Outcome のサブ要素化、Deciders → Decision Maker(s)、bare/minimal テンプレートの導入。

---

## ガイドライン

- **Martin Fowler, "Architecture Decision Record"**
  - URL: https://martinfowler.com/bliki/ArchitectureDecisionRecord.html
  - inverted pyramid 文体(最重要を冒頭、詳細を末尾に)、brevity 原則(典型的に1ページ)、`doc/adr` 配置、ライトウェイトな Markdown 推奨。

- **AWS Prescriptive Guidance: Architectural Decision Records**
  - URL: https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/
  - プロセスとガバナンス、ownership 分散、change history と supersede 処理、コードレビューでの ADR 参照。Richards & Ford (2020) の ASR 分類を踏襲。

- **Microsoft Azure Well-Architected Framework: Maintain an ADR**
  - URL: https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record
  - confidence level の記録、複数フェーズ判断の分割、structure / quality attributes / irreversibility を significance criteria とする。

- **Olaf Zimmermann, "How to create ADRs — and how not to" (2023)**
  - 関連: "How to review ADRs — and how not to"
  - メタファー、パターン、アンチパターン、チェックリスト。本スキルの `antipatterns.md` の元ネタ。

- **AWS Architecture Blog, "Master architecture decision records (ADRs): Best practices for effective decision-making" (2025)**
  - URL: https://aws.amazon.com/blogs/architecture/master-architecture-decision-records-adrs-best-practices-for-effective-decision-making/
  - 200+ ADR の実装経験から: readout meeting style、cross-functional だが lean な参加者、centralize storage、insist on highest standards。

---

## 実例集

- **joelparkerhenderson/architecture-decision-record (GitHub)**
  - URL: https://github.com/joelparkerhenderson/architecture-decision-record
  - 包括的な ADR 実例集と複数テンプレート(Nygard, MADR, Y-statement, Planguage 等)の比較。

- **adr.github.io**
  - URL: https://adr.github.io/
  - ADR 関連リソースの公式ハブ。MADR, Y-statement, Embedded ADR (Java annotation) など。

---

## 関連概念

- **Bezos の Type 1 / Type 2 decisions**
  - One-way door (不可逆) vs Two-way door (可逆)。本スキルの「不可逆性優先」原則の出典。

- **Architecturally Significant Requirements (ASR)**
  - Richards & Ford, "Fundamentals of Software Architecture" (2020) で定義。非機能要件のうちアーキテクチャに測定可能な影響を与えるもの。

- **Y-statement の語源**
  - 文型を Y 字に図示できることに由来(context と concern が上の2本、chosen option / neglected options / quality / downside / rationale が下の縦棒)。
