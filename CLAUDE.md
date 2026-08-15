# CLAUDE.md

このファイルは、Claude Code (claude.ai/code) がこのリポジトリで作業する際のガイダンスを提供します。

## 絶対ルール

- SPEC.md はこの研究の憲法。実装の都合で内容を変更しない。
  変更が必要と判断したら、問題・理由・変更案・変更しない場合の影響を提示し、人間の承認を待つ。
- make_ppe / make_mask のように「答え」を含むActionを作らない。
- Agentに渡すプロンプトに「コスプレ」「PPE」「マスク」「COVID」の語を出さない。
- LLM decides intent. Code determines feasibility.
- 非線形な創発を観測したいからといって、非線形性をコードに埋め込まない。
- Milestoneの順番を守る。Milestone 1が完了するまでLLM実装を始めない。
- API費用の上限を設定し、超えたら実行を止める仕組みを必ず入れる。
- ユーザーへの応答は日本語で行うこと。

## プロジェクトの状態

**設計完了・実装未着手。** 現在このリポジトリには `SPEC.md`（v0.2、正典）、`docs/REVIEW.md`（§32 設計レビュー、審議完了）、`docs/DESIGN_M1.md`（Milestone 1 詳細設計、v0.2 同期済み）と環境構築物（`.venv/`、`.gitignore`）が存在します。`src/`、`configs/`、`experiments/`、`tests/` はまだ作成されていません。

- **SPEC.md §32 が要求する設計レビューは完了済みです。** 再作成しないでください（`docs/REVIEW.md`）。【要承認】3件は決着し、SPEC.md は v0.2 へ改訂されました（§33 改訂履歴）。
- **Milestone 1 の実装前提はすべて確定しています**（`docs/DESIGN_M1.md` §17: D6 技能減衰=採用 / D7 参入退出=なし・N=40固定 / D8 money=M1の因果モデル外 / D11 蓄積期間=52・104・156週のconfig切替、既定156 / D12 蓄積相のLLM=使わない / D13 材料補充=inventory_cap方式）。M1 実装をブロックする未決事項はありません。
- 実装に着手する際は `docs/DESIGN_M1.md` §16 の実装順序（S1〜S15）に従うこと。
- **`docs/REVIEW.md` 本文には SPEC v0.1 時点の旧条件名（Culture / Skill-Matched Random / Isolated / B1 / B2）が審議の記録として残っています。** 実装に持ち込まないこと。現行の条件定義は SPEC §19 と `docs/DESIGN_M1.md` が正典です。

## SPEC.md が正典である

`SPEC.md` は研究仕様書であり、単なる提案ドキュメントではありません。§0にある通り: そこで定義された研究命題・理論・実験原則は**固定**です — 独自判断で変更しないでください。実装方法・データ構造・アルゴリズム・ライブラリ選定は、*研究目的を損なわない範囲で*改善の余地があります。

もし*実装の詳細ではなく研究命題*そのものを変更すべきと判断した場合、黙って変更してはいけません。§32に従い、問題・なぜ問題なのか・変更案・変更しなかった場合の影響、を提示した上で人間の承認を待ってください。

## 環境 / コマンド

Windowsネイティブ環境、Python 3.12の仮想環境が `.venv/` にあります。

```powershell
# 仮想環境の有効化（PowerShell）
.\.venv\Scripts\Activate.ps1

# コアの依存パッケージをインストール/更新（requirements.txtはまだ無いため、これが現時点での既知の動作構成）
.\.venv\Scripts\python.exe -m pip install numpy pandas networkx pyyaml matplotlib pytest

# テストの実行（tests/ が作成された後）
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest tests/path_to_test.py::test_name  # 単一テスト
```

ビルド/lintツールはまだ設定されていません。

## 譲れない設計上の制約（SPEC.md より）

これらはSPEC.md全体で繰り返し出てくる原則で、個別の実装作業中に意図せず破ってしまいやすいものです:

- **LLMは意図を決め、コードが実現可能性を判定する**（§13）。資源計算、在庫、所持金、時間、生産量、材料消費、技能値、設備制約、物流、品質判定、市場清算、ネットワーク更新、Metrics、転化判定は、すべて**決定論的なコード**が担当し、LLM出力に委ねてはいけません。LLMが担当するのは局所的な意思決定、情報解釈、コミュニケーション、新用途の提案、協力判断、学習対象の選択のみです。
- **Actionに「答え」をハードコードしない**（§12）。`make_ppe` や `make_mask` のようなActionは禁止で、一般化されたAction（`make`、`modify`、`share`、`help`、`trade`、`propose` 等）のみを使用します。Agentへ「PPEを作れ」「マスクを作れ」「医療を助けろ」と指示してはいけません — Phase 1のPPEへの転化は指令ではなく創発として起きる必要があります（§8）。
- **Information Locality、神の視点の禁止**（§14）。Agentが見えるのは、自分自身、自分のmemory、接続されたAgentから届いたメッセージ、観測可能な市場情報、自ら取得した情報のみで、世界全体の状態を見せてはいけません。
- **Required Itemは抽象化された仕様であり、名称ではない**（§18）。需要は `RequiredItem` を**属性ベクトル `attr_0` 〜 `attr_6`** としてモデル化し、「PPE」という具体名で扱わないこと — これによりPhase 2への一般化が可能になります。
  - **属性に意味を持つ名前を付けないこと。** 技能・材料・設備・制作対象も同様に `skill_N` / `mat_N` / `asset_N` / `proj_N` / `attr_N` の中立コード表記を使います（`docs/DESIGN_M1.md` §3.0）。
  - **意味の対応表は研究者向けドキュメント（SPEC.md §18）にのみ存在します。** `attr_0` 〜 `attr_6` は §18 の列挙順に対応します。対応表をこのファイル・コード・プロンプトへ複製しないでください — 複製した時点で、既知知識のリーク経路と「答え」の埋め込み経路になります。
  - **禁止語テスト（T2）の対象は Agent-facing strings のみ**です（`docs/DESIGN_M1.md` §3.0.1）。対象=prompt・Action名・Agentへ渡るidentifier・Observation上の文字列・Agent memoryへ格納される文字列。対象外=README・RESULTS.md・SPEC.md・docs/・config_resolved.yaml・researcher-facing logs・コードコメント/docstring。**ただしconfigのキー名も中立に保つこと**（実装者の頭に「答え」を持ち込むため）。
- **未証明の主張を事実として扱わない**（§6）。次のことをモデルの前提として実装してはいけません: コスプレコミュニティが他の趣味コミュニティより強い、コスプレイヤーが他人より利他的である、コスプレイヤーの災害対応能力が高い、コスプレネットワークが必ずより密である、コスプレイヤーが有事に必ず供給活動を行う。これらは検証対象の仮説であり、モデルの前提ではありません。
- **Anti-Goals**（§30）: コスプレイヤーを英雄として描かない、利他的だと決めつけない、PPE制作を命令しない、結果に合わせて後からパラメータを恣意的に調整しない、LLMの文章だけを「創発」の証拠として扱わない、Agent数の多さを成果にしない、Milestone 1が終わる前にPhase 2・UI・マイクロサービス化・巨大なAgent frameworkに手を出さない。
- **モデル内実験から現実への直接推論をしない**（§19）: A/B/C/D の比較は**仮説的モデル内部でのfactorial experiment**です。この結果から現実のコスプレ文化について直接因果主張してはいけません。特に A/C の structured topology は現実のネットワークの再現ではなく、検討用の仮説的構成です。
- **条件間のネットワーク同一性**（§19）: 同一seedにおいて **A と C は完全に同じGraph object由来**、**B と D は完全に同じrewired graph由来**でなければなりません。同じ生成アルゴリズムを使うだけでは不十分です。base graphを1回生成してdeep copyで配布し、`peer_learning_enabled` フラグだけを変更します。ネットワーク生成の乱数差でA/CまたはB/Dに差が出ることを禁止します。
- **再現性**（§23）: すべての実行でseed、モデル名/バージョン、プロンプトバージョン、config、timestamp、シミュレーションパラメータ、Agentの初期状態を保存すること。LLMの非決定性があるため、単一runだけで結論を出さないこと。
- **コスト制御**（§24）: 全Agentを毎step LLMで動かさない。通常状態はコード、軽い意思決定はcheapモデル/ルール、重要な再構成判断は高性能なLLM、という切り分けにする。LLM呼び出し回数とトークン使用量をログに残すこと。

## コアモデル（見取り図として）

- **中心仮説**: 文化は「何を望むか」（Soft Power）だけでなく「何をできるか」（Latent Capability）まで変える。経路は `Cultural Participation → Latent Capability` であり、Soft Powerそのものと混同してはいけません（§2）。
- **Capability Reproduction Loop**（§5）: Attraction → Participation → Observation → Information Acquisition → Imitation/Scaffolding → Making → Feedback → Skill Acquisition → Sharing → （他者のObservationへ）。これはAgentが実行する台本ではなく、Agent間相互作用の結果として*創発*するべきものです。
- **Makerの成熟段階**（§4、シミュレーション中に変化しうる、固定属性ではない）: `Consumer → Customizer → Maker → Advanced Maker`。
  - **判定は潜在技能ではなく行動で行う**（`docs/DESIGN_M1.md` §6.4）。**Customizer = `n_projects >= 1` のみ**（技能による経路は削除済み、`customizer_skill` は存在しない）。SPEC §4 が段階を行動の記述として定義しているためです。
  - **「履歴」と「現在の能力」の非対称**: Customizer は**不可逆**（経歴は消えない）、Maker 以上は `max_skill` を要求するため**可逆**（技能減衰で落ちうる）。`maker_count` は単調増加しません。
  - この規則により初期状態の Consumer 比率は構成上100%となり、**初期分布の校正が不要**になります（恣意的調整の余地を構造的に排除）。
- **検証対象の仮説**（§7）: H1 — 相互学習構造は時間経過とともにMaker人口を増加させるか。H2 — 初期の技能・設備が同一でも、Capability Reproduction Loopが存在するとLatent Capabilityがより速く成長するか。H3 — その蓄積差は供給ショック時の転化確率・転化速度・供給量に差を生むか。
- **2×2完全要因計画**（§19）。因子は **topology**（structured / rewired）× **peer learning**（ON / OFF）: **A**=structured+ON、**B**=rewired+ON、**C**=structured+OFF、**D**=rewired+OFF。初期技能・設備・資源は4条件で完全に同一。
  - **C/D は「ネットワークを除去した世界」ではない**。社会的接触は維持される: practice・make・**Method自己発見**・**self-scaffolding**・observe・**ask**・**share**・perceived_skills更新はすべて有効。C/Dで無効化されるのは **他AgentからのMethod取得（peer Method transfer）とpeer由来Methodによるsocial scaffolding のみ**。表現したいのは「人は社会的につながっているが、そのつながりが制作能力の再生産経路として機能しない世界」。
  - **trustはM1では固定値。更新式を実装しない**（SPEC §33 改訂6）。「askによってtrustを更新する」という記述は廃止済み。peer learningのON/OFFがtrust dynamicsまで変えると、操作因子が2つになりA−Cの差をpeer経路に帰属できなくなるため。`accept_peer_method()` は固定trust値を参照してよい。
  - `skill assortativity → knowledge diffusion向上` を事前に仮定しないこと。**A < B** も正当な研究結果。
- **転化とEmergenceは物語ではなくコードで判定する**（§20〜21）: 転化は閾値化された条件（`community_supply_share`、`active_supplier_count`、`supply_duration`、`coordination_edges`、いずれもconfig管理）で判定。Emergenceには E0（転化なし）から E4（マクロな供給能力として定着）までのレベルがあります。
- **Milestoneの順序は厳守**（§28）: M1 = LLMなしの機構のみ（Agent生成、skills/assets/network、observe/practice/make/share、skill learning、ステージ遷移 — 目標はLoopが機構として成立可能なことの証明。特にConsumer→Customizer→Makerの遷移）。M2 = event-drivenな局所LLM意思決定の導入。M3 = 供給ショックの導入、答えを与えない。M4 = A/B/C/D の2×2比較（topology × peer learning の主効果と交互作用）。先に進みすぎないこと（例: §9の通り、Phase 1の妥当性確認前にPhase 2へ着手しない）。
- **時間は二相クロック**（§25）: 蓄積相 = 1 step 1週（M1、標準156週）／ショック相 = 1 step 6時間（M3）。
- **participant / non-participant は主要な因果対照ではない**（`docs/DESIGN_M1.md` §3.4）。母集団は participant 30 / non-participant 10（N=40）。**技能・設備・材料・向社会性の初期分布は完全に同一**で、差を付けるのは `participation_level` と cultural peer-learning networkへの参加資格のみ。
  - **participantは「初期技能が高い人」でも「利他的な人」でもありません。** participationによる能力形成が起きるかは検証対象であって前提ではありません（§6）。
  - **non-participantを孤立ノードにしてはいけません。** 一般社会接触（`known_agents`）は保持し、cultural Method transferとpeer scaffoldingのみ遮断します（`cultural_peers`）。二重差にすると文化参加効果と社会接触効果を分離できなくなります。
  - non-participantは**context population**として扱い、**この比較から「文化参加の因果効果」を直接主張してはいけません**。主要対照はA/B/C/Dの2×2です。30/10も現実の人口比ではなく仮置き構成です。
  - Metricsは `all_agents` / `participants_only` / `nonparticipants_only` の3系列で保存し、**H1/H2の主要判定は `participants_only`** で行います。

## 計画中のリポジトリ構成（SPEC.md §27、まだ未作成）

```
configs/        base.yaml, condition_a.yaml 〜 condition_d.yaml
src/agents/     agent.py, decision.py, memory.py
src/world/      world.py, economy.py, production.py, logistics.py
src/culture/    learning.py, network.py, capability.py
src/simulation/ runner.py, transition.py, metrics.py
src/llm/        client.py, prompts.py
experiments/    phase1_validation.py, threshold_sweep.py, ablation.py
outputs/
tests/
```

これは出発点として改善してよいものであり、厳格な規定ではありません — ただし過剰な作り込み（重厚なframework、時期尚早なマイクロサービス化など）は避けてください（§30）。

条件別 YAML の差分は `topology` と `peer_learning_enabled` の**2キーのみ**です（`docs/DESIGN_M1.md` §14.2）。学習率・減衰率・Agent数・材料補充・効用重み・step数を条件ごとに変えてはいけません。

M1 で実際に作成するモジュール構成は `docs/DESIGN_M1.md` §2 が正典です（`src/world/resources.py`、`src/agents/observation.py` 等が追加されています）。
