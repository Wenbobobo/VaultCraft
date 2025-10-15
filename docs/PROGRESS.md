# 进度跟踪与交接说明（PROGRESS & HANDOFF）

## 当前进度（2025-10-15 17:00）

- 文档
  - PRD v0（docs/PRD.md）；Tech Design（docs/TECH_DESIGN.md）；架构解析（docs/ARCHITECTURE.md）；前端规范（docs/FRONTEND_SPEC.md）；配置清单（docs/CONFIG.md）；Hyper 集成（docs/HYPER_INTEGRATION.md）；Hyper 部署（docs/HYPER_DEPLOYMENT.md）
- 合约（Hardhat + Foundry）
  - Vault（ERC20 shares，最短锁定、HWM 绩效费、私募白名单、适配器白名单、可暂停）
  - Hardhat 测试 + 覆盖率：Vault.sol statements 85.71%，branches 51.16%，functions 77.78%，lines 100%
  - 任务与脚本：whitelist/adapter/lock/fee/deposit、token:mint、vault:create-private、ping、seed
- 后端（FastAPI skeleton + 工具）
  - 指标计算（metrics）单测通过
  - Hyper Exec facade（build_open/close，NAV 计算）；Demo CLI（rpc-ping/build-open/build-close/nav）
- 前端（Next.js+Tailwind）
  - Demo 读取链上数据：ps、totalAssets、lock、perfFee、totalSupply、isPrivate
  - 暂停进一步 UI 开发，交由设计实现；已提供详细前端规范与开发清单

## 待办（按优先级）

- P0（立即）
  - 确认 Hyper Testnet agent/keys（如需）→ 后端 Exec Service 打通只读行情（SDK/REST）
  - 增加后端接口：/metrics/:vault、/nav/:vault（读取存储或临时计算）
- P1（短期）
  - Exec Service：open/close/reduce（受 env 开关控制，默认 dry-run），WS 监听成交回执并记录
  - NAV 承诺生成与（可选）上链快照脚本
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

