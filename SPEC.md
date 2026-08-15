# COSPLAY RESERVE — Claude Code Implementation Brief v0.1

## 0. あなたの役割

あなたは、AIエージェント社会シミュレーション「COSPLAY RESERVE」の設計・実装を担当するソフトウェアエンジニアです。

このプロジェクトでは、単なるデモやストーリー生成ではなく、再現可能な社会シミュレーション実験を構築します。

以下に記載された研究命題・理論・実験原則は、これまでの検討によって確定したものです。
これらを独自判断で変更しないでください。

一方、実装方法、データ構造、アルゴリズム、ライブラリ選定については、研究目的を壊さない範囲でより良い方法を提案してください。

---

## 1. Project

**COSPLAY RESERVE**

コスプレは、いつ安全保障になるのか？

本プロジェクトは「メタ安全保障」をテーマとしたAIエージェント社会シミュレーションです。

中心となる問いは、

> 安全保障を目的としていないコスプレ文化は、どの環境条件を境に「消費者コミュニティ」から社会の「分散型供給能力」へ転化するのか？

です。

---

## 2. 背景となる理論

一般的なSoft Powerは、

```
Cultural Attraction → Soft Power
```

という経路で考えられます。

文化的魅力が、

- 親近感
- 好み
- 価値観
- 選好

などを形成し、他者の行動へ影響するという考え方です。

COSPLAY RESERVEでは、これとは異なる第二の経路を仮説として扱います。

```
Cultural Participation → Latent Capability
```

すなわち、

```
文化 → 参加 → 技能・設備・関係性の形成 → 社会の潜在能力
```

という経路です。

中心仮説は、

> 文化は、人々が「何を望むか」を変えるだけでなく、人々が「何をできるか」まで変える。

です。

Soft PowerそのものとLatent Capabilityを混同しないでください。

---

## 3. なぜコスプレなのか

コスプレは単なる消費文化ではありません。

アニメ・漫画等への文化的魅力から、

```
文化的魅力 → ファンダム → コスプレ参加 → 消費者から制作者へ → 技能・設備・ネットワーク獲得
```

という変化が起こり得ます。

コスプレを本プロジェクトでは、

> 「文化的魅力を、現実世界の能力へ変換する装置」

として仮説化します。

コスプレ参加者が獲得し得る能力には例えば、

- 縫製
- 裁断
- 造形
- 接着
- 塗装
- CAD
- 3Dモデリング
- 3Dプリント
- 電子工作
- 修理
- 材料選択
- 試作
- 改良

などがあります。

ただし、全コスプレイヤーがこれらを持つと仮定してはいけません。
購入中心の参加者も存在します。

---

## 4. Agentの成熟段階

コスプレ参加者には少なくとも以下の段階を持たせます。

```
Consumer → Customizer → Maker → Advanced Maker
```

- **Consumer**: 完成品購入中心。
- **Customizer**: 既製品の調整・加工、一部制作等を行う。
- **Maker**: 衣装・小道具等を制作できる。
- **Advanced Maker**: 複数技能、高度造形、CAD、3Dプリント、電子工作等を組み合わせられる。

重要なのは、この属性を固定しないことです。

シミュレーション中の文化活動・学習によって、

```
Consumer → Customizer → Maker → Advanced Maker
```

という遷移が起こり得るようにしてください。

---

## 5. Capability Reproduction Loop

学術研究から、コスプレ文化では制作情報の共有、peer-based learning、reciprocal learning、scaffolding等が観測されています。

本プロジェクトでは、

**Capability Reproduction Loop（能力再生産ループ）**

を主要仮説として扱います。

概念的には、

```
Cultural Attraction
→ Participation
→ Observation
→ Information Acquisition
→ Imitation / Scaffolding
→ Making
→ Feedback
→ Skill Acquisition
→ Sharing
→ 他の参加者によるObservation
```

という循環です。

**注意：**
これは固定された手続きとしてAgentに実行させるものではありません。
Agent間相互作用の結果として、この循環がマクロに形成されるよう設計してください。

---

## 6. 現時点で証明されていないこと

以下を事実として実装しないでください。

- コスプレコミュニティは他の全趣味コミュニティより強い
- コスプレイヤーは一般人より利他的である
- コスプレイヤーは災害対応能力が高い
- コスプレネットワークは必ず他コミュニティより密である
- コスプレイヤーは有事に必ず供給活動を行う

これらは結論ではありません。検証対象です。

特に重要なのは、

> 「供給するモデル」ではなく、「供給するかもしれない世界」を作ること

です。

---

## 7. 検証仮説

**H1**
コスプレ文化の相互学習構造は、時間経過とともにMaker人口を増加させるか。

**H2**
同じ初期技能・設備を持つ集団でも、Capability Reproduction Loopが存在する社会ではLatent Capabilityがより速く成長するか。

**H3**
その蓄積差は供給ショック発生時の、

- 転化確率
- 転化速度
- 供給量

に差を生むか。

---

## 8. Phase 1

COVID-19期に現実に観測された、

```
コスプレ／Maker的技能 → PPE等への転用
```

を教師ケースとして使用します。

目的は、**PPEを作らせること**ではありません。

現実に起きた転化現象を、個別具体的な行動命令なしに再現可能か検証することです。

Agentへ、

- PPEを作れ
- マスクを作れ
- 医療を助けろ
- コスプレ技能を転用せよ

などと指示してはいけません。

---

## 9. Phase 2

Phase 1でモデル妥当性を確認した後、PPEという答えを外します。

未知の供給ショックを発生させ、**第二の転化**を探索します。

人間が事前に答えを指定していない状況で、既存技能・設備・ネットワークが新用途へ再構成されるかを観測します。

Phase 2は重要ですが、初期実装ではまだ作らないでください。

---

## 10. AI Agent設計原則

LLMに「コスプレイヤーを演技」させることを目的としません。

> 「あなたはコスプレイヤーです。コスプレイヤーらしく行動してください」

という単純なロールプレイ型シミュレーションは避けてください。

代わりに、Agentには実証可能な特徴を状態として持たせます。

例：

- skills
- assets
- resources
- maker stage
- network
- knowledge
- memory
- previous projects
- available time
- information received
- relationships

LLMはその局所状態から次の行動を判断します。

---

## 11. Agent State

最低限、以下を想定してください。

**Agent**
- id
- role

**resources**
- money
- free_time
- materials

**skills**
- sewing
- crafting
- cad
- printing_3d
- electronics
- repair

**assets**
- sewing_machine
- printer_3d
- tools
- workspace

**culture**
- participation_level
- maker_stage
- sharing_tendency
- imitation_tendency
- helping_norm

**network**
- known_agents
- trust
- known_skills_of_others

**memory**
- recent_events
- learned_methods
- previous_projects

**current_action**

実装上より良いスキーマがあれば提案可能ですが、変更理由を説明してください。

---

## 12. Agent Actions

初期候補：

- consume
- observe
- ask
- practice
- make
- modify
- share
- help
- trade
- propose
- join
- ignore

**重要：**

`make_ppe`、`make_mask` など、答えを含んだActionを作らないでください。

`make` は一般化された制作行動です。

---

## 13. LLMとコードの責務分離

極めて重要です。

**LLM 担当：**
- 局所意思決定
- 情報解釈
- 他Agentとのコミュニケーション
- 新しい用途の提案
- 協力判断
- 学習対象選択

**Code 担当：**
- 資源保存
- 在庫
- 所持金
- 時間
- 生産量
- 材料消費
- 技能値
- 設備制約
- 物流
- 品質判定
- 市場
- Network更新
- Metrics
- Transition判定

LLMが「一晩で1万個作れる」と言っても、コード側の生産能力計算が不可能なら実行できない設計にしてください。

**原則：**

> LLM decides intent. Code determines feasibility.

---

## 14. Information Locality

Agentへ世界全体の状態を与えないでください。

Agentが認識できるのは、

- 自分自身
- 自分のmemory
- 接続されたAgentから届いた情報
- 観測可能な市場情報
- 自分が取得した情報
- 自分が知っている他Agentの能力

等です。

神の視点を禁止します。
局所情報からマクロ構造が形成されることを重視します。

---

## 15. Agent Prompt原則

方向性は以下です。

> "You are an autonomous participant in a simulated society.
>
> Decide your next action only from:
> - your current resources,
> - skills and equipment,
> - information available to you,
> - your relationships,
> - your previous experiences,
> - current environmental conditions.
>
> Do not optimize for society as a whole unless your own beliefs and available information support doing so.
> Do not assume knowledge you have not received.
> You may reuse, combine, modify, learn, communicate, cooperate, or decline to act.
>
> Return one intended action and a short reason."

ただし、これは叩き台です。

より再現性が高く、token効率がよく、構造化出力可能なPromptへ改善してください。

---

## 16. 世界

初期MVPは30〜50 Human-like Agents程度とします。

目安：

- Cosplay-related Agents: 30
- General Agents: 10
- Hospital: 1
- Manufacturer: 1
- Material Supplier: 1
- Logistics: 1

数値はconfigで変更可能にしてください。

---

## 17. 世界側状態

最低限、

- demand
- supply
- inventory
- price
- materials
- production
- logistics
- quality requirements
- information propagation
- shock state

を管理します。

---

## 18. Required Item

可能であればPPEを単なる名称として扱わず、要求仕様へ抽象化してください。

例：

**RequiredItem**
- flexible_material
- filtration_requirement
- shape_requirement
- durability
- sterility_requirement
- production_complexity
- unit_demand

Hospital等は、

> 「PPEを作れ」

ではなく、

> 「この要求仕様を満たす物資が不足している」

という需要を世界へ発生させます。

これによってPhase 2への一般化を可能にします。

---

## 19. 比較世界

Phase 1では最低3条件を比較できる構造にしてください。

**A. Culture**
技能・設備あり。Capability Reproduction Loopおよび文化ネットワークあり。

**B. Skill-Matched Random**
初期技能・設備分布はAと同一。文化ネットワークをランダム化。

**C. Isolated**
初期技能・設備分布はAと同一。相互学習・ネットワークをほぼ除去。

**重要：**
可能な限り同じseedから初期Agentを生成し、文化構造だけを変えられるようにしてください。

---

## 20. Transition

「転化」は物語的判断ではなくコードで判定します。

**概念定義：**

> 文化コミュニティが、本来の活動目的とは異なる社会需要に対して、既存の技能・設備・ネットワークを再構成し、無視できない供給を継続的に成立させた状態。

**暫定条件例：**

```
community_supply_share >= threshold
AND active_supplier_count >= threshold
AND supply_duration >= threshold
AND coordination_edges >= threshold
```

閾値はconfig管理してください。最終値は実験開始前に固定します。

---

## 21. Emergence

転化と創発を区別します。

- **転化**: 社会的役割・供給状態の変化。
- **創発**: 設計者が具体的に指定していない役割、協調、供給構造がAgent間相互作用から形成されること。

**暫定的なEmergence Level：**

- **E0**: 転化なし。
- **E1**: 個人による偶発的代替行動。
- **E2**: 模倣・情報共有が発生。
- **E3**: 分業・協調ネットワーク形成。
- **E4**: マクロな供給能力として定着。

---

## 22. Metrics

最低限記録してください。

- maker_count
- maker_stage_distribution
- skill_distribution
- asset_distribution
- network_density
- skill_reachability
- resource_reachability
- knowledge_diffusion_speed
- active_supplier_count
- community_supply_share
- transition_time
- coordination_edges
- coordination_complexity
- latent_capacity

特に重要なのは、

**Reconfiguration Time**
未知の需要発生から、新しい供給チーム・生産構造が成立するまでの時間。

**Latent Capability**
概念的には、

```
Distributed Resources × Network Connectivity × Reconfiguration Ability
```

として捉えます。

初期実装では無理に単一スコアへまとめなくても構いません。構成指標を別々に保存してください。

---

## 23. Reproducibility

研究結果として扱えるよう、

- random seed
- model name
- model version
- prompt version
- config
- timestamp
- simulation parameters
- Agent initial states

を保存してください。同一条件で再実行可能にします。

LLMの非決定性があるため、単一runだけで結論を出さない設計にしてください。

---

## 24. Cost Control

全Agentを毎step LLMで動かさないでください。

**原則：**

- 通常状態 → Code
- 軽い意思決定 → cheap/small model またはrule
- 重要な再構成判断 → capable LLM

**LLM呼び出し候補：**

- 新情報を受け取った
- 新需要を知った
- 制作に失敗した
- 他Agentから提案された
- 新しい用途を検討する
- 協力相手を選ぶ
- 技能・材料の再結合を考える

LLM call数、input tokens、output tokens、推定API費用もログしてください。

---

## 25. Time

暫定：

- 1 step = 6 hours
- 4 steps = 1 day
- 120 steps = 30 days

ただしconfigurableにしてください。

---

## 26. 最終提出物

本選提出物は、

1. GitHub Repository
2. Presentation
3. README
4. RESULTS.md

です。

コードは最終的に第三者がREADMEを読んで再実行できる状態を目標にします。

---

## 27. Repository Structure

初期案：

```
cosplay-reserve/
  README.md
  RESULTS.md
  SPEC.md
  configs/
    world_culture.yaml
    world_random.yaml
    world_isolated.yaml
  src/
    agents/
      agent.py
      decision.py
      memory.py
    world/
      world.py
      economy.py
      production.py
      logistics.py
    culture/
      learning.py
      network.py
      capability.py
    simulation/
      runner.py
      transition.py
      metrics.py
    llm/
      client.py
      prompts.py
  experiments/
    phase1_validation.py
    threshold_sweep.py
    ablation.py
  outputs/
  tests/
```

必要なら改善してください。ただし、過剰なframework化は避けてください。

---

## 28. 開発順序

いきなり完成版を作らないでください。

### Milestone 1

LLMなし。30〜50 Agent程度。

以下をコードだけで動かす。

- Agent生成
- skills
- assets
- network
- observe
- practice
- make
- share
- skill learning
- maker stage transition

**目標：** Capability Reproduction Loopがモデル上で成立可能であること。

特に、`Consumer → Customizer → Maker` の遷移を確認します。

### Milestone 2

局所LLM意思決定を導入。全Agent毎stepではなくevent-drivenで呼び出す。

**目標：** Agentが、学習・共有・制作・協力を局所情報から選択できる。

### Milestone 3

供給ショックを導入。具体的な答えをAgentへ与えない。

**目標：** 既存技能・設備を別用途へ再構成する行動が発生するか確認する。

### Milestone 4

Culture / Skill-Matched Random / Isolated を比較。

**目標：** 同じ技能・設備でも文化ネットワークの有無によって、Maker形成・Knowledge diffusion・Reconfiguration・Supply transition に差が生まれるか確認する。

---

## 29. Phase 1成功条件

最初の成功条件を「PPEが作られた」だけにしないでください。

より重要なのは、

> 同じ初期技能・設備を持つ集団でも、文化的な学習・共有ネットワークが存在する世界では、能力の伝播・組み合わせ・再構成が異なるか。

です。

その後、その差が供給ショック時の実際の供給能力差につながるかを確認します。

---

## 30. Anti-Goals

以下はやらないでください。

- コスプレイヤーを英雄として描く
- コスプレイヤーは利他的だと決めつける
- PPE制作をAgentへ命令する
- 結果が出るように後からパラメータを恣意的調整する
- LLMの文章だけを「創発」と判定する
- Agent数の多さを成果にする
- 全社会を再現しようとする
- Phase 2から実装する
- 不要なUIを先に作る
- 不要なマイクロサービス化
- 巨大なAgent frameworkを導入する

---

## 31. 最重要原則

このプロジェクトで作りたいのは、

> 「コスプレイヤーが社会を救う物語」

ではありません。

検証したいのは、

> 文化活動が技能・設備・関係性を形成し、それらを組織化可能な状態で蓄積することで、平時には認識されていなかった社会能力が危機時に別用途へ転化し得るのか。

という仮説です。

そして最終的な社会実装の思想は、

> 「安全保障に参加してください」ではなく、「好きなことを続けてください。それが安全保障になる社会」を設計する。

です。

---

## 32. あなたへの最初のタスク

まだコードを大量に生成しないでください。

まず、このSPECをレビューしてください。以下を出力してください。

1. この研究命題を実装する上での技術的リスク
2. シミュレーションとして成立しない可能性のある箇所
3. LLMによる既知知識リークのリスク
4. Capability Reproduction Loopを実装する最小モデル案
5. Agent state schemaの改善案
6. World state schema案
7. Event system案
8. LLM / deterministic codeの責務分離案
9. Milestone 1の具体的実装計画
10. Milestone 1のテスト計画
11. 想定APIコストを抑える設計案
12. このSPECで不足している意思決定事項

その上で、Milestone 1を実装可能なレベルまで設計を具体化してください。

**重要：**

研究命題そのものを変更する提案と、実装方法を改善する提案を明確に分離してください。

研究命題を変更する必要があると判断した場合は、勝手に変更せず、

- 問題
- なぜ問題なのか
- 変更案
- 変更しなかった場合の影響

を提示して、人間の承認を待ってください。

レビュー完了までは、大規模な実装を開始しないでください。
