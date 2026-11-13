# 用户提供的上下文测评 Hook 表

| 上下文测评能力 | 能力说明 | 测评指标 | 指标计算方式 | Benchmark | Openjiuwen接口 |
| --- | --- | --- | --- | --- | --- |
| 关键信息保留 | 在上下文累积、裁剪或压缩后，准确保留后续任务所需的事实、数值与细节，避免信息丢失或失真。 | ① 关键信息保留率 ↑ | ① 按原文保留的目标信息条目数 ÷ 目标条目总数 | ① ContextBench — Needle Retention | core/context_engine/base.py — ModelContext.get_context_window() |
| 关键信息保留 | 在上下文累积、裁剪或压缩后，准确保留后续任务所需的事实、数值与细节，避免信息丢失或失真。 | ② 信息保留相关检查通过率 ↑ | ② C2、C3 任务的检查项通过率 | ② TraceTrial-Bench — C2 滚动压缩保真、C3 跨轮事实保留 | core/context_engine/base.py — ModelContext.get_context_window() |
| 状态维护与传递 | 正确应用状态变更，保留当前状态和变更历史，并在交接时避免遗漏、重复或顺序错乱。 | ① 状态维护正确率 ↑ | ① 与标准棋盘完全一致的输出版本数 ÷ 应输出的棋盘版本总数 | ① ContextBench — Sudoku Sketchpad | core/context_engine/base.py — ModelContext.get_context_window() |
| 状态维护与传递 | 正确应用状态变更，保留当前状态和变更历史，并在交接时避免遗漏、重复或顺序错乱。 | ② 状态传递相关检查通过率 ↑ | ② C5 任务的检查项通过率 | ② TraceTrial-Bench — C5 跨会话状态维护 | core/context_engine/base.py — ModelContext.get_context_window() |
| 信息访问与恢复 | 当所需信息未完整保留在当前上下文中时，维持可用的访问或恢复路径，按需获取信息，并明确提示缺失。 | ① 历史信息利用正确率 ↑ | ① 历史查询中回答正确的问题数 ÷ 查询问题总数 | ① ContextBench — KV Store、Log Triage | core/context_engine/base.py — ModelContext.get_context_window() |
| 信息访问与恢复 | 当所需信息未完整保留在当前上下文中时，维持可用的访问或恢复路径，按需获取信息，并明确提示缺失。 | ② 截断恢复相关检查通过率 ↑ | ② C1 任务的检查项通过率 | ② TraceTrial-Bench — C1 截断披露与恢复 | core/context_engine/base.py — ModelContext.get_context_window() |
| 跨会话上下文接续 | 切换会话时，准确传递历史信息，保留消息角色与顺序，清楚区分历史内容和当前请求。 | 会话接续相关检查通过率 ↑ | C4 任务的检查项通过率 | TraceTrial-Bench — C4 会话恢复保真 | core/context_engine/base.py — ModelContext.get_context_window() |
| 子 Agent 上下文隔离与交接 | 按分工限定各子 Agent 接收的任务资料，准确关联其身份、返回结果与后续复核，避免资料混用和结果错配。 | 隔离交接相关检查通过率 ↑ | C6 任务的检查项通过率 | TraceTrial-Bench — C6 子 Agent 上下文隔离 | core/context_engine/base.py — ModelContext.get_context_window() |
