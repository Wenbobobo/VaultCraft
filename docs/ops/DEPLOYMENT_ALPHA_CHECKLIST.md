## Alpha 阶段部署 & 稳定性自查清单

目标：在进入 Beta 前，让系统具备“可在 staging/试点环境稳定运行 72h”的能力。以下条目按模块划分，可在每次部署/回归时逐步勾选。

---

### 1. 环境与配置
- [ ] `.env.staging` / `.env.production` 模板齐备，并与 README 配套更新。
- [ ] `DEPLOYMENT_API_TOKEN` 已设置，前端演示/正式环境对其使用策略明确（演示可带 `NEXT_PUBLIC_DEPLOYMENT_KEY`，正式环境不暴露）。
- [ ] 告警配置：`ALERT_WEBHOOK_URL`、冷却/阈值均按目标环境设定；演练一次电话/短信。
- [ ] Staging/Prod 部署脚本（Docker Compose 或 PM2）完成，包含健康检查和日志目录规范。

### 2. 安全与鉴权
- [ ] `/api/v1/register_deployment` 必须带 `X-Deployment-Key`；无 token 时返回 401。
- [ ] 其他写接口（positions:set、exec-open/close 等）鉴权策略明确，最小权限原则检视。
- [ ] 管理端操作日志化（至少本地文件或集中 log 收集）并附时间、调用者、payload。

### 3. 监控与可观测性
- [ ] `/api/v1/status` 返回 `lastAckTs` + listener/ws 状态；前端 StatusBar 正常显示。
- [ ] ack fallback 说明已更新至 README/DEMO_PLAN，团队能解释“只见 ack，无 ws 推送”的原因。
- [ ] 日志输出到集中存储（如 Loki/Elasticsearch 或文件 + 日志轮转），预警渠道接入 Slack/邮件/Webhook。
- [ ] 快照守护与告警线程运行 ≥72h，无内存泄漏/异常关停，日志无高频错误。

### 4. 功能回归
- [ ] Manager：部署 → 配置（白名单/锁期/绩效费）→ Exec → 读取风险信息，全流程成功。
- [ ] Investor：浏览 → 申购 → Portfolio 显示份额/余额 → Shock → 告警到达。
- [ ] Listener/Status：执行后事件流包含 `source:"ack"`，StatusBar 显示最新 ack 时间；若 Hyper Testnet 无 ws 填单，能用 `/status` + ack 说明观测情况。
- [ ] 数据精度：Discover/Portfolio 的 AUM、钱包余额等与链上数值一致，无 “固定 0”/假数据展示。

### 5. 文档与沟通
- [ ] `docs/product/ROADMAP.md` Alpha 条目全部转为 “✅”；仍开放项留在 Beta 表格。
- [ ] README 更新部署流程、告警、权限说明；演示脚本 `DEMO_PLAN.md` 对应最新 UI/提示。
- [ ] 运维人员/试点经理已掌握新流程（可附操作录像或说明书）。

完成以上清单后，即可进入 Beta 阶段（TradingView / 量化接口等）详细实现与调研工作。
