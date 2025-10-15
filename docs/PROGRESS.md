# 进度跟踪与交接说明（PROGRESS & HANDOFF）

## 当前进度（2025-10-15 19:05）

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
  - 后端测试：合计 23 个全部通过（`uv run pytest -q`）
- 前端（Next.js+Tailwind）
  - 集成新设计骨架（apps/vaultcraft-frontend），对接后端 API：
    - Discover 列表：调用 `/api/v1/vaults`（失败回退到本地示例）
    - 详情页：调用 `/api/v1/vaults/:id`、`/api/v1/nav/:id` 渲染 KPI 与 NAV 图
    - 新增 `lib/config.ts`（`NEXT_PUBLIC_BACKEND_URL`）与 `lib/api.ts`
    - `PerformanceChart` 支持以 props 传入数据

## 待办（按优先级）

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

- Base Sepolia：见 deployments/base-sepolia.json（已部署 Vault/MockERC20）#预定废弃
- Hyper Testnet：见 deployments/hyper-testnet.json（chainId 998，RPC 已配置）
- Hardhat .env：RPC_URL、PRIVATE_KEY、（可选）HYPER_RPC_URL、ASSET_ADDRESS 等
- Web：NEXT_PUBLIC_RPC_URL（只读），NEXT_PUBLIC_BACKEND_URL（后端）
- Backend：HYPER_API_URL、HYPER_RPC_URL、HYPER_API_KEY/SECRET（可选）

## 交接要点

- 安全：默认 dry-run；需要真实下单时开启 env 开关且小额测试
- 文档入口：README.md → 参考文档链接
- 脚本入口：hardhat/package.json scripts；apps/backend/app/cli.py（uv run）
- 代码风格：TDD 优先；前端按 docs/FRONTEND_SPEC.md 组件与交互实现
