# VaultCraft v0

可验证的人类交易员金库平台（Public 透明 + Private 不公开持仓）。本仓库包含：
- 合约（Solidity）：最小金库 `Vault`（ERC20 份额、最短锁定、HWM 绩效费、Public/Private、适配器白名单、可暂停）
- 测试：Foundry（Solidity 高覆盖）与 Hardhat（JS/TS 生态）
- 后端（Python/uv）：指标计算与最小 API（年化、波动、Sharpe、最大回撤、恢复期）
- 文档：PRD 与技术方案（docs/）

演示链：Hyper Testnet（chainId 998，EVM RPC https://rpc.hyperliquid-testnet.xyz/evm）。

---

## 架构总览

```mermaid
flowchart LR
  subgraph Dapp
    Web[前端/SDK]
  end

  subgraph Chain[EVM L2 Testnet]
    V[Vault 4626 简化]
    A1[Adapter: Spot DEX]
    A2[Adapter: Perps (占位)]
    V -- execute(adapter,data) --> A1
    V -- execute(adapter,data) --> A2
  end

  subgraph Backend[Backend (FastAPI)]
    IDX[事件索引/快照]
    MET[指标计算]
    API[只读 API]
  end

  Web <--> API
  Web --> V
  IDX --> MET --> API
```

---

## 用户交互流程

Public（公募，持仓透明）
```mermaid
sequenceDiagram
  participant U as 投资者
  participant FE as 前端
  participant V as Vault(公开)

  U->>FE: 浏览金库列表 (含AUM/指标)
  FE->>V: 读取持仓/交易/净值
  U->>V: 申购(实时净值)
  Note over V: 份额铸造
  U->>V: 赎回(解锁后)
  Note over V: 份额销毁→资金返回
```

Private（私募，不公开持仓）
```mermaid
sequenceDiagram
  participant U as 投资者(白名单)
  participant FE as 前端
  participant V as Vault(私募)

  U->>FE: 浏览金库摘要(不含持仓/交易)
  U->>FE: 通过白名单/门票加入
  U->>V: 申购(实时净值)
  FE->>V: 查看 NAV/PnL 曲线与绩效指标
  U->>V: 赎回(解锁后)
```

---

## 路线与取舍

- v0 只实现必要特性：最短锁定、HWM 绩效费、公募透明、私募不公开持仓、白名单资产与适配器、可暂停。
- 计划中：
  - [ ] 锁定周期费率曲线
  - [ ] Reduce-Only 模式
  - [ ] 容量/拥挤/风险函数
  - [ ] 批量窗口（Batching Window）
  - [ ] 私有路由与 AA（Gasless）
  - [ ] 期权与 RWA 适配器
  - [ ] Manager 质押与削减（Manager Staking & Slashing）
  - [ ] Manager 持仓上限曲线

---

## 统一环境变量（根目录 .env）

仅使用仓库根目录 `.env` 进行统一配置（后端/前端/Hardhat 共用）。示例见 `.env.example`。

后端（FastAPI / Exec / 行情）关键参数：
- HYPER_API_URL=https://api.hyperliquid-testnet.xyz
- HYPER_RPC_URL=https://rpc.hyperliquid-testnet.xyz/evm
- ENABLE_HYPER_SDK=1                      # SDK 优先行情
- ENABLE_LIVE_EXEC=0                      # 实单开关（1=开启）
- HYPER_TRADER_PRIVATE_KEY=0x...          # 或 PRIVATE_KEY=0x...
- EXEC_ALLOWED_SYMBOLS=BTC,ETH            # 允许交易对
- EXEC_MIN_LEVERAGE=1.0 / EXEC_MAX_LEVERAGE=50.0
- EXEC_MAX_NOTIONAL_USD=1000000000        # 名义金额上限
- EXEC_MIN_NOTIONAL_USD=10                # 名义金额下限（Hyper最小下单$10）
- APPLY_DRY_RUN_TO_POSITIONS=1            # dry-run 是否回写 positions
- APPLY_LIVE_TO_POSITIONS=1               # live exec 是否回写 positions
- POSITIONS_FILE=deployments/positions.json
- ENABLE_SNAPSHOT_DAEMON=0 / SNAPSHOT_INTERVAL_SEC=15
- EVENT_LOG_FILE=logs/events.jsonl        # 可选，事件追加写

前端（Next.js）关键参数：
- NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
- NEXT_PUBLIC_RPC_URL=https://rpc.hyperliquid-testnet.xyz/evm
- NEXT_PUBLIC_ENABLE_DEMO_TRADING=0       # 演示下单面板开关
  (钱包按钮默认显示，无需额外开关)

Hardhat（部署/脚本）关键参数：
- HYPER_RPC_URL=https://rpc.hyperliquid-testnet.xyz/evm
- PRIVATE_KEY=0x...                       # 测试网私钥（小额）

## 快速开始（Backend）

推荐配置：Python 3.10+ & uv

```
cd apps/backend
uv venv
uv pip install -q pytest pytest-cov
uv run pytest -q
uv run uvicorn app.main:app --reload
```

如遇 `pytest` 未找到，请先执行 `uv pip install -q pytest` 再 `uv run pytest -q`。

---

## 快速开始（Hardhat）

要求：Node 18+（已内置）

```
cd hardhat
npm install
npx hardhat compile
npx hardhat test
```

部署到测试网（示例）
```
# 设置环境变量（示例，请替换）
$env:RPC_URL="https://sepolia.base.org"
$env:PRIVATE_KEY="0x..."  # 部署私钥，务必小额测试

# 创建简单部署脚本（scripts/deploy.ts），或使用 hardhat task
# 示例 task（伪代码）：
# const Vault = await ethers.getContractFactory("Vault")
# const vault = await Vault.deploy(asset, name, symbol, admin, manager, guardian, isPrivate, pBps, lockDays)
```

说明：Hardhat 项仅用于 JS/TS 生态的编译与最小测试；Solidity 侧高覆盖测试仍由 Foundry 提供（见下）。

---

## 常用 Hardhat 任务（部署/演示）

```
# 创建私募金库（可指定资产/经理/守护者/白名单/费率/锁期）
npx hardhat vault:create-private --network baseSepolia \
  --perf 1000 --lock 1 --whitelist 0xInvestor

# 给 MockERC20 铸币
npx hardhat token:mint --network baseSepolia \
  --token 0xMockToken --to 0xYourAddr --amount 1000

# 存入金库
npx hardhat vault:deposit --network baseSepolia \
  --vault 0xVault --asset 0xToken --amount 100

# 配置白名单/适配器/锁期/绩效费
npx hardhat vault:whitelist --network baseSepolia --vault 0xVault --user 0xU --allowed true
npx hardhat vault:set-adapter --network baseSepolia --vault 0xVault --adapter 0xA --allowed true
npx hardhat vault:set-lock --network baseSepolia --vault 0xVault --days 1
npx hardhat vault:set-perf-fee --network baseSepolia --vault 0xVault --bps 1000
```

---

## 快速开始（Web 前端）

```
cd apps/vaultcraft-frontend
pnpm i
pnpm dev
# 打开 http://localhost:3000 查看列表与详情；Transactions 标签查看事件流
```

前端已对接后端 API（metrics/nav/events）与可选链上只读；无需单独前端 .env.local，变量来自根 .env。

---

## 快速开始（Foundry，可选）

Foundry 优点：
- Solidity 原生测试（速度快、覆盖率高、不变量/模糊更便利）
- 适合合约会计、事件与边界条件的细粒度测试

安装 Foundry（建议 WSL 或参照官方文档），然后：
```
cd contracts
forge build
forge test -vvv
# 覆盖率
forge coverage --report lcov
```

---

## 测试覆盖要点

Solidity（Foundry）：
- 申购/赎回保持单位净值 PS 不变
- HWM 绩效费（铸份额）仅在 PS > HWM 时计提
- 私募白名单门控（非白名单拒绝）
- 最短锁定生效（解锁前赎回失败）
- 暂停/恢复阻断交互
- 仅经理可执行适配器；适配器需白名单
- 第三方赎回（allowance）
- 管理员参数变更与上限
- 快照事件与白名单事件发射

后端（pytest）：
- 指标计算：年化/波动/Sharpe/最大回撤与恢复期

---

## 项目结构

```
contracts/               # Solidity 源码与 Foundry 测试
  Vault.sol
  test/
    Vault.t.sol
    mocks/
    utils/

hardhat/                 # Hardhat 项（JS/TS 生态）
  contracts/             # 复制的最小合约以便编译
  test/

apps/backend/            # FastAPI + 指标
  app/
  tests/

docs/                    # PRD 与技术方案
```

---

## 研发流程（TDD）

- 优先在 Foundry 编写/运行合约单测与性质测试；
- 若需 JS/TS 生态/前端联调，使用 Hardhat（不替代 Foundry 测试）；
- 后端以 pytest 驱动指标/索引逻辑；
- 功能合入前要求：测试通过 + 关键不变量/事件覆盖。

---

## 适配 Perps（占位）

- v0 合约已提供 `execute(adapter,data)` 与适配器白名单；
- 首选接 Synthetix Perps，后续可扩 Hyper/GMX/Vertex/Aevo；
- 测试网准备：RPC、测试代币、perps 市场/保证金资产；
- 若短期无可用市场，先以 MockAdapter 演示调用链路。

---

## 迁移 HyperEVM（预留）

- Router/Adapter 解耦；
- 事件/快照格式稳定，便于在新链重放对账；
- Private 视图门控与签名门票逻辑与链无关，可复用。

---

## 参考文档

- 产品文档：docs/PRD.md（v0 范围、参数与治理矩阵、Backlog）
- 技术方案：docs/TECH_DESIGN.md（架构、接口、事件、不变量、TDD 计划）
 - 架构解析：docs/ARCHITECTURE.md（前端/后端/链上职责与数据流）
 - 前端规范：docs/FRONTEND_SPEC.md（页面/组件/接口契约/样式/交互）
 - Hyper 集成：docs/HYPER_INTEGRATION.md（v1 执行/行情集成方案）
 - 配置清单：docs/CONFIG.md（env、deployments 记录与建议）
