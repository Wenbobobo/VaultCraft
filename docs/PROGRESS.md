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
  - P0 修复：移除 `mockVault.*` 残留（统一 `vault.*`），避免 Hydration 报错；新增 `NEXT_PUBLIC_ENABLE_WALLET` 开关，默认隐藏“Connect Wallet”按钮以避免无响应交互。

## 需求更新与排序（来自最新演示）

- 已知问题（详见 docs/ISSUES.md）：
  - Hydration mismatch：已修复 `mockVault`；如有其他警告，排查随机/时间依赖并改用 CSR。

### P0（Demo 必需）
- 最小钱包交互（可选）：当前通过开关隐藏连接按钮，保留受控 Exec 演示
- Demo 脚本/状态提示：保证 /status、/pretrade、/events、/nav_series 稳定，前端状态条与错误提示完整
- 文档打磨：统一 env、部署步骤与排错（余额不足、私钥格式）

### P1（短期加分）
- Listener（WS）回写落地与前端提示；NAV 曲线与事件时间轴对齐
- 前端钱包完善（连接/签名/链切换）与最小链上只读
- UI polish（空态、错误提示、loading skeleton）

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

## 环境与配置

- Hyper Testnet：见 deployments/hyper-testnet.json（chainId 998，RPC 已配置）
- 统一 env：仅根 `.env`，参数与说明见 README 与 docs/DEPLOYMENT.md

## 交接要点（给后续开发者）

- 安全：默认 dry-run；需要真实下单时开启 ENABLE_LIVE_EXEC=1 且小额测试
- 文档：README“统一环境变量”、docs/DEPLOYMENT.md（私钥格式与余额排错）、docs/DEMO_PLAN.md（评审脚本）
- 入口：Hardhat（部署）、FastAPI（后端）、Next.js（前端）
- 故障：insufficient funds（给 ADDRESS 充测试币）；私钥格式（0x+64hex）；SSR/Hydration 与 `mockVault` 残留（详见 docs/ISSUES.md）
