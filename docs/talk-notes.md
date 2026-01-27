# ReplayGate Talk Notes

## 30 秒项目概述
ReplayGate 是一个面向回放验证与差异门禁的工程化平台：通过网关录制真实请求，replay-worker 将同一批请求并行重放到基线与候选版本，diff-engine 依据规则对响应做结构/数值/关键字段校验，gate 输出 PASS/FAIL 及原因。平台按 run 生成 artifacts，支持一键清理副作用，确保回放可重复、可追溯。

## 2 分钟讲解提纲
- 录制：gateway 记录请求/响应，按 recording_id 存储，作为回放输入。
- 回放：replay-worker 注入 run_id/trace_id，并为基线/候选版本设置不同 idempotency_key。
- diff：支持 global ignore、endpoint 规则、strict 字段、schema breaking、数值漂移容忍。
- gate：以 diff summary 为输入，输出可解释的 PASS/FAIL 与原因。
- 副作用治理：服务端幂等（Redis + DB 唯一约束）+ cleanup(run_id)。
- 可配置阈值：strict_tolerance 随 run 配置，用于控制严格字段的漂移容忍。

## 常见深挖问答（8）
1) Q: strict_mismatches 与 strict_tolerance 有什么区别？
   A: strict_mismatches 是严格字段超出 strict_tolerance 后的计数；strict_tolerance 是严格字段可接受的漂移阈值（默认 0.05，可在 run 里配置）。

2) Q: 为什么 PASS/FAIL 要以 gate_verdict.json 为准？
   A: gate 是最终门禁决策点，gate_verdict.json 记录 verdict 与 reasons，作为唯一权威来源，避免前端或 diff 结果被误读。

3) Q: 如何减少误报？
   A: 通过 global ignore 排除时间戳/trace_id 等噪声；按接口设置 ignore 路径与 strict 字段；对数值字段设置可容忍漂移。

4) Q: run_id 的作用是什么？
   A: 用于请求注入、数据隔离与清理标识，贯穿 gateway → services → cleanup。

5) Q: 如何保证回放的可重复性？
   A: 录制固定输入、服务端幂等（Idempotency-Key + DB 约束），并在回放后清理 run_id 相关数据。

6) Q: schema breaking 怎么判定？
   A: diff-engine 对响应扁平化后比较 key 集合，缺失或新增字段会计为 schema breaking。

7) Q: 为什么 strict 字段需要单独阈值？
   A: strict 字段代表业务核心（如 total_price），需要更可控的漂移策略，不与普通字段的 numeric_tolerance 混用。

8) Q: 扩展性怎么做？
   A: runner 通过队列触发，diff/gate 通过 HTTP 解耦；后续可增加新的 runner 或规则，无需改变核心 API 契约。
