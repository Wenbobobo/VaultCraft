# 进度跟踪与交接说明（PROGRESS & HANDOFF）

## 当前进度（最新）

- 文档
  - PRD v0（docs/PRD.md）；Tech Design（docs/TECH_DESIGN.md）；架构解析（docs/ARCHITECTURE.md）；前端规范（docs/FRONTEND_SPEC.md）；配置清单（docs/CONFIG.md）；Hyper 集成（docs/HYPER_INTEGRATION.md）；Hyper 部署（docs/HYPER_DEPLOYMENT.md）
- 合约（Hardhat + Foundry）
  - Vault（ERC20 shares，最短锁定、HWM 绩效费、私募白名单、适配器白名单、可暂停）
  - Hardhat 测试 + 覆盖率：Vault.sol statements 85.71%，branches 51.16%，functions 77.78%，lines 100%
  - 任务与脚本：whitelist/adapter/lock/fee/deposit、token:mint、vault:create-private、ping、seed
- 后端（FastAPI + 工具）
  - 新增 API：GET `/api/v1/metrics/:address`、GET `/api/v1/nav/:address`、GET `/api/v1/events/:address`
    - 支持通过 `series` 查询参数喂入 NAV（测试/演示用）；生产接入存储/索引器
  - HyperHTTP 增强：`get_markets()`、`get_index_prices(symbols)`（测试用 monkeypatch，无需外网）
  - HyperExec 增强：杠杆区间校验（`min_leverage/max_leverage`）、`build_reduce_only()`
  - 新增 API：GET `/api/v1/markets`、GET `/api/v1/price?symbols=`、GET `/api/v1/vaults`、GET `/api/v1/vaults/:id`
    - `markets` 从 `deployments/hyper-testnet.json` 读取配置对（BTC/ETH 5x 缺省）；`price` 采用 Hyper REST 助手（失败则回退确定性演示价格）
  - 新增价格路由：优先官方 Python SDK（启用需 `ENABLE_HYPER_SDK=1`），失败回落 REST，再回落演示价格
  - 后端测试：全部通过（`uv run pytest -q`）。修复了因 SDK 覆盖导致的价格端点单测不稳定：在测试 monkeypatch `HyperHTTP.get_index_prices` 时优先走 REST，且应用启动清空价格/NAV 缓存以保证确定性。
- 前端（Next.js+Tailwind）
  - 集成设计骨架并对接后端 API：
    - Discover：`/api/v1/vaults`（失败回退本地示例）
    - 详情：`/api/v1/vaults/:id`、`/api/v1/nav_series/:id` 渲染 KPI 与 NAV 曲线
    - 新增 `StatusBar`（/status）、`EventsFeed`（/events）、可选 `ExecPanel`（/pretrade + /exec）
  - P0 修复：移除 `mockVault.*` 残留（统一 `vault.*`），避免 Hydration 报错；默认显示“Connect Wallet”按钮（Header/Hero）。
  - 导航调整：新增 Browse 页面（搜索/排序），About 跳转仓库；默认显示钱包按钮（Header/ Hero）。
  - Portfolio：改为真实链上读取 `balanceOf/ps/nextRedeemAllowed`，支持 Withdraw。
  - Manager：新增 /manager 页面，浏览器内一键部署 Vault（读取后端提供的 Hardhat Artifact），以及参数管理与白名单设置。

## 需求更新与排序（来自最新演示）

- 已知问题（详见 docs/ISSUES.md）：
  - Hydration mismatch：已修复 `mockVault`；如有其他警告，排查随机/时间依赖并改用 CSR。

### P0（Demo 必需）
- [x] 详情页残留与 Hydration 修复；统一 CSR/SSR 数据
- [x] Exec 面板与事件流 UX 提示（错误映射、loading、过滤、自动滚动）
- [x] 文档打磨：统一 env、部署步骤与排错（余额不足、私钥格式）
- [x] 钱包连接与链切换（Header，EIP‑1193）
- [x] Deposit 真实交互（approve + deposit）
- [x] 公募持仓历史（事件重建）与风险参数可视化（/status）
- [x] Shock 模拟（写入 NAV 低值快照）

### P1（短期加分）
- 私募邀请码 UI（演示）与前端 gating；实白名单通过 Hardhat 预操作
- Listener（WS）回写落地与前端标注（"fill via listener"）
- UI polish（进一步空态/骨架、图表/事件时间对齐）
 - Manager 扩展：Adapter 管理、Guardian/Manager 变更、部署记录写回。

- P0（立即）
  - 为 `/api/v1/nav/:address` 接入真实 NAV 数据源（简单版：后端注册表中的头寸 + 价格 → `pnl_to_nav` 计算），并增加内存/SQLite 缓存
  - 补充 `/api/v1/vaults` 数据来源（从 deployments 或后端注册表），保留私募不披露持仓的约束
- P1（短期）
  - Exec Service：open/close/reduce（env 开关，默认 dry-run），并记录成交事件到后端存储（仅展示 NAV，不披露私募持仓）
  - NAV 快照与（可选）上链快照任务；后端分页与窗口化返回 NAV 序列
  - Hardhat：添加基于 Exec 的 mock 测试（不依赖真实网络）
- P2（后续）
  - 容量/拥挤函数、批量窗口、告警通道、Manager Console（参数调整、白名单、限权）
  - 跨链只读会计 → 桥接/消息 Orchestrator（v2）
  - 私募邀请码签名校验与服务端管理
  - 在线创建 Vault 表单化（替代 Hardhat 任务）

## 环境与配置

- Hyper Testnet：见 deployments/hyper-testnet.json（chainId 998，RPC 已配置）
- 统一 env：仅根 `.env`，参数与说明见 README 与 docs/DEPLOYMENT.md

## 交接要点（给后续开发者）

- 安全：默认 dry-run；需要真实下单时开启 ENABLE_LIVE_EXEC=1 且小额测试
- 文档：README“统一环境变量”、docs/DEPLOYMENT.md（私钥格式与余额排错）、docs/DEMO_PLAN.md（评审脚本）
- 入口：Hardhat（部署）、FastAPI（后端）、Next.js（前端）
- 故障：insufficient funds（给 ADDRESS 充测试币）；私钥格式（0x+64hex）；SSR/Hydration 与 `mockVault` 残留（详见 docs/ISSUES.md）
