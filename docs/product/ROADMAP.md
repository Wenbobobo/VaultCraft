# VaultCraft Roadmap（Post-demo ➜ 商用化）

本路线图在 v1 黑客松 Demo 完成后，面向“实盘可用 / 可商用”目标拆分阶段。默认为滚动 4–6 周节奏，可依资源与外部依赖调整。

---

## 阶段 Alpha · 基础稳健化（0 → 1）
**目标**：把演示环境打磨到可对真实交易员/小规模试点开放，补齐稳定性、监控与运营所需能力。  
**时间建议**：1–2 周（可并行处理）。

| 主题 | 关键工作项 | 产出 / 验收 |
| --- | --- | --- |
| 运行稳定性 | - 拆分 staging/production `.env` 模板，提供一键部署脚本（Docker / PM2）<br>- 健全日志/审计：事件落盘 + S3 备份，添加 request/exec tracing | 可在 staging 连续运行 ≥72h（含快照/告警）无人工干预；生产镜像/脚本可直接交付 DevOps |
| 权限与安全 | - 对 `register_deployment` 等写接口增加 auth gating（API key / signer 签名）<br>- 限制管理端操作频次，补充操作日志 | 未授权请求默认拒绝；操作审计可追踪到人 |
| ACK fallback 说明 | - 将 listener ws 的现状/告警 fallback 写入 README / DEMO_PLAN<br>- 在前端 status bar 增加“最后 ack 时间”显示 | 演示/试点时可清晰解释 ack-only 状态 |
| QA & 文档 | - 更新 `docs/ops/DEPLOYMENT.md` → “staging & prod” 双流程<br>- 在 `docs/ops/PROGRESS.md` 建立“验收 checklist” section | 提交 operator 手册，QA 可按表执行 |

---

## 阶段 Beta · 专业交易面板 & 量化接口
**目标**：面向经理/量化团队提供专业化仓位控制界面 + 可编程接口。结合用户反馈中“缺少 TradingView 等专业工具”的痛点，升级执行链路。  
**时间建议**：3–4 周。

| 主题 | 关键工作项 | 产出 / 验收 |
| --- | --- | --- |
| TradingView 集成 | - 嵌入 TradingView Lightweight Chart 或官方 Widgets（支持 symbol 搜索、指标叠加）<br>- 支持多时间周期、盘口深度/成交量 overlay（必要时配合第三方流） | Manager “仓位执行”页提供可交互图表；查阅不同交易对时保持 500ms 内响应 |
| 高级下单工具 | - 扩展 ExecPanel：限价、止盈/止损、Reduce-Only 开关、滑点/杠杆预设模板<br>- 添加订单草稿（草稿模式、快速重复下单） | 支持提交限价单，并在后端落地 Risk 校验；交互遵循专业交易平台习惯 |
| 量化 API（MVP） | - 提供 REST + WebSocket：行情推送、账户持仓、下单接口（可重用现有 `/exec/*`）<br>- 鉴权机制（API key + 签名），限流/速率控制 | 发布 `Quant Trading API` v0 文档，回归测试覆盖常见 4xx/429 场景 |
| 风险合规 | - 增加 per-vault 风控模板（最大仓位、单笔最大杠杆、自定义白名单）<br>- 告警扩展：滑点过大、订单被拒次数、NAV 与标的偏离 | `/status` 反映风险模板，告警可推送多渠道（Webhook + 邮件/Slack） |
| 前端体验 | - Manager 控制台改造 tab：Trading / Risk / Activity / Settings<br>- 详情页展示实时仓位、PnL（可视化 equity 曲线、仓位构成） | 核心页面达到 Trading 体验期望，用户可在单页完成监控及调仓 |

---

## 阶段 Gamma · 多市场接入 & 私募增强
**目标**：支持多 venue、多品种策略组合；引入隐私与合规能力（WhisperFi 等）。  
**时间建议**：4–6 周（视集成情况）。

- **跨市场适配器**：扩展 Router 支持 Polymarket / 美股代理 / 贵金属 / 期权；配置化 `venue_whitelist` 与 `execution_channel`。  
- **策略组合与再平衡**：允许新 vault 引用其他 vault 的份额，自动化调仓；提供再平衡/超限提醒。  
- **WhisperFi 集成**：私募交易记录加密上链 + 审计密钥机制；私募投资者通过证明访问绩效。  
- **风控深化**：引入风险引擎（VAR、敞口限额、对冲比率），对多市场组合统一估值。  
- **指标与报表**：支持 Merkle NAV commitment、定期对账报告、可自定义 KPI Dashboard。

验收：至少 1 个新 venue 在测试网成功跑通（下单→回写→告警）；私募流程可在 Demo 中展示“加密交易 + 审计凭证”。

---

## 阶段 Delta · 商业化与运营体系
聚焦商业模式与运营工具搭建，可并行启动：

- **费用与收益结算**：绩效分成计提/分配、平台服务费、奖励机制；自动生成报表。  
- **用户增长与合规**：KYC/AML、邀请制私募、合规牌照/法律咨询。  
- **监控与 SRE**：集中日志、指标（Prometheus/Grafana）、警报升级。  

---

## 附录：已识别痛点与对应规划
| 痛点 | 规划解决阶段 | 备注 |
| --- | --- | --- |
| Listener 无 ws 填单、解释困难 | Alpha | 保留 ack fallback，补充监控/日志 |
| Manager 执行界面不够专业 | Beta | TradingView、快捷指令、风控模板 |
| 量化团队缺 API | Beta | REST/WS + 鉴权，配合风控限额 |
| 多 venue / 多资产需求 | Gamma | 适配器 + 风控引擎 |
| 私募隐私/审计 | Gamma | WhisperFi / 零知识凭证 |
| 商业化、结算体系 | Delta | 费用模型、对账报表、KPI |

> 提示：上述阶段并非严格串行，可视资源并行推进；每阶段结束建议进行回顾，更新路线图。
