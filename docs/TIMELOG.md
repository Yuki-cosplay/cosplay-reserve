# 実行タイムログ

**t=0 = 2026-08-16 12:46:23 JST（2026-08-16 03:46:23 UTC）**

## 時間判断点

| t | 時刻(JST) | 判断内容 |
|---|---|---|
| 2.5h | **15:16** | S1–S4 未完なら、必須性質を保証するテスト以外を後回しにして S4 完了を優先 |
| 5.0h | **17:46** | M1 未完走なら、感度分析（S14）を主パイプラインから切り離す。A/B/C/D 最小実行を優先 |
| 7.5h | **20:16** | M2 未稼働なら「1エージェント・1回のLLM呼び出し」に縮退し M3 へ |
| 10.0h | **22:46** | 原則 freeze |
| 11.0h | **23:46** | 絶対 freeze |

**10h→11h の延長条件**: M3 の P0/P1 が実装済みで、追加30〜60分で shock experiment 完走が合理的に期待できる場合のみ。
**延長禁止理由**: 結果を改善するための parameter tuning / prompt tuning / condition 変更。

## 必須性質（縮退時も削除禁止）と T番号の対応

| 必須性質 | テスト | 実装段階 |
|---|---|---|
| deterministic reproducibility | T1 `test_determinism` | S10（S4時点では部分版 T1p） |
| A/B/C/D pre-network initial-state invariance | T5 `test_condition_invariance` | S2 |
| A/C および B/D の network identity | T9 `test_network_pairing` | S3 |
| peer-learning ON/OFF の遮断点 | T11 `test_peer_learning_gate` | S8 |
| Agent-facing answer leak protection | T2 `test_no_answer_leak` | S15（S4時点で先行実装可） |

**準必須（削ると freeze 解除事由 P0「条件交絡」を踏む）**: T15-② participant のリング位置非連続、T3 locality。

## 記録

| t | 時刻 | 事象 |
|---|---|---|
| 0.00h | 12:46 | 開始。S1–S4 着手 |
| 0.17h | 12:57 | S1–S4 完了。54 tests green（T1p/T2/T3/T5/T9/T13/T14/T15） |
| 0.55h | 13:19 | P1（技能スカラー=平均、assortativity=目標係数）反映。S5–S13 実装 |
| 0.68h | 13:27 | **C1 達成**: 20 seed × 4条件 = 80 run 完走（162.8s）。pairing OK |
| 0.68h | 13:27 | C13（感度分析）は P2 へ後回し（ユーザー指示）。L4 に記録 |
| 0.68h | 13:27 | **L3 発見**: maker_count 天井効果（全条件 30/30, sd 0）。要人間判断 |
| 1.15h | 13:55 | M2 最小構成を実装（client/prompts/decider/CostGuard）。90 tests green。**条件1（実LLM呼び出し）は認証待ちでブロック** |
| 1.6h | 14:23 | M3 実装完了（demand/transition/shock/runner）。124 tests green。dry-run: 12 calls / $0.174 |
| 1.6h | 14:25 | M3 本実行: 段階1-2 通過、段階3（LLM呼び出し）で認証エラー。ユーザ実行待ち |
