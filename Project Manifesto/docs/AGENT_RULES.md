# AGENT_RULES

Mandatory rules for this repo:
- Small iterations: ship one reversible goal at a time.
- Verify each step: run feasibility checks and record results.
- Progress log: append to ??????.md every iteration.
- A-F output format on delivery (Goal/Changes/Files/Verify/Risk/Log).
- No copying reference source or dependencies; references are notes only.
- Dependencies must be reproducible; install via package manager only; no node_modules copying.
## Token Protocol（对话额度快满时的自动交接）
当会话 tokens 即将耗尽（界面提示接近上限或判断剩余 < 15%）时，必须立即切换到“交接模式”：
- 停止新增功能与大范围改动，只做收尾与落盘。
- 必须更新：
  - docs/HANDOFF.md（Repo/Branch/Commit、已完成、接口对接结论、Backend gaps、env 变量名与用途、运行与验证）
  - 开发进度文档.md（记录触发原因、当前停在何处、下一步优先级列表）
- 若存在未提交改动：优先提交 checkpoint（"chore: handoff checkpoint"）。
- 回复末尾必须输出 [NEW CHAT STARTER]（<= 25 行）用于新会话续接。
- 禁止粘贴大段代码/全文文档；交接内容必须简洁可执行。
