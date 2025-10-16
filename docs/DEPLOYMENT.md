# VaultCraft 部署手册（Hardhat）

本文档涵盖：准备环境、配置 .env、编译、部署到测试网、常见问题与验证步骤。

---

## 0. 准备环境（Hyper Testnet 优先）

- Node.js ≥ 18, npm ≥ 9（Windows 已就绪）
- 测试网 RPC：
  - Hyper Testnet EVM: https://rpc.hyperliquid-testnet.xyz/evm (ChainId 998)
  - 更多参考 docs\HYPER_INTEGRATION.md, docs\HYPER_DEPLOYMENT.md
- 部署私钥：建议新建小额热钱包，切勿使用生产私钥

---

## 1. 安装依赖

```
cd hardhat
npm install
```

---

## 2. 配置环境变量

复制示例并填写：

```
Copy-Item .env.example .env
```

编辑 `.env`（Hyper Testnet 推荐）：

```
HYPER_RPC_URL=https://rpc.hyperliquid-testnet.xyz/evm
PRIVATE_KEY=0xYOUR_PRIVATE_KEY
# 可选：管理与守护者地址、是否私募、绩效费、锁定天数
#INIT_MANAGER=0x...
#INIT_GUARDIAN=0x...
#ASSET_ADDRESS=0x...   # 若不填，脚本会部署 MockERC20
#IS_PRIVATE=false
#PERF_FEE_BPS=1000
#LOCK_DAYS=1
```

网络选择说明：
- hyperTestnet / baseSepolia / arbitrumSepolia 由 hardhat.config.ts 预置；
- hyperTestnet 使用 `HYPER_RPC_URL`；其它网络可继续沿用 `RPC_URL`

---

## 3. 编译与单元测试

```
npx hardhat compile
npx hardhat test
```

---

## 4. 部署（后端 / 前端）

Hyper Testnet：
```
npm run deploy:hyperTestnet
```

<!-- Base Sepolia：
```
npm run deploy:baseSepolia
```
Arbitrum Sepolia：
```
npm run deploy:arbitrumSepolia
``` -->

输出包含：
- MockERC20 资产地址（若未提供 ASSET_ADDRESS）
- Vault 合约地址（admin=deployer, manager=INIT_MANAGER, guardian=INIT_GUARDIAN）

---

### 4.1 后端（只读 API）

```
cd apps/backend
uv venv
uv run uvicorn app.main:app --reload --port 8000
```

常用：
- 健康检查 `GET /health`
- 市场与价格：`GET /api/v1/markets`、`GET /api/v1/price?symbols=BTC,ETH`
- 金库与详情：`GET /api/v1/vaults`、`GET /api/v1/vaults/:id`

可选：启用 Hyper 官方 SDK 作为行情源（见 docs/HYPER_DEPLOYMENT.md 第 2 节）。

### 4.2 前端（apps/vaultcraft-frontend）

```
cd apps/vaultcraft-frontend
copy .env.example .env.local
# 编辑 .env.local 中 NEXT_PUBLIC_BACKEND_URL 指向后端
pnpm i
pnpm dev
```

页面：
- `/` Discover：展示公募/私募金库列表（默认从后端 API 获取，失败回退本地示例）
- `/vault/[id]`：展示 KPI 与 NAV 曲线（调用后端 metrics/nav 接口）

## 4.3 快速创建私募金库（Task）

无需单独脚本，直接用 Hardhat Task：

```
# 创建私募金库（默认部署 MockERC20，设置绩效费与锁定期，并批量白名单）
npx hardhat vault:create-private --network baseSepolia \
  --perf 1000 --lock 1 \
  --whitelist 0xInvestor1,0xInvestor2

# 指定已有资产、经理/守护者
npx hardhat vault:create-private --network baseSepolia \
  --asset 0xYourAsset --manager 0xMgr --guardian 0xGua \
  --perf 1000 --lock 1 --whitelist 0xInvestor

# MockERC20 铸币（用于测试）
npx hardhat token:mint --network baseSepolia \
  --token 0xMockToken --to 0xYourAddr --amount 1000

# 存入金库（自动 approve 后 deposit）
npx hardhat vault:deposit --network baseSepolia \
  --vault 0xVault --asset 0xToken --amount 100
```

---

## 5. 部署后验证（手动）

- 读取 `ps()`：应为 1e18（初始净值 1）
- 向 Vault 批准并 `deposit` 若干资产，`ps()` 应保持不变
- 过锁定期后 `redeem`，份额减少、资产到账
- 如为私募：非白名单地址 `deposit` 应被拒绝

---

## 6. 与前端/后端联调

- 将部署地址写入前端/后端配置（待前端脚手架完成）
- 后端可订阅事件：Deposit/Withdraw/PerformanceFeeMinted/NavSnapshot

---

## 7. 常见问题

- Error HHE3: No Hardhat config file found
  - 请 `cd hardhat` 再运行 `npx hardhat ...`
- Gas 报错
  - 测试币不足，请先在相应测试网水龙头领取
- 无法连接 RPC
  - 检查 RPC_URL 是否正确，防火墙/代理是否阻断

---

## 8. 后续（非 v0）

- 加入 Router/Adapters 更丰富的协议支持
- 引入私有/批量路由（CoW/Protect）、AA 限权
- perps 适配器（Synthetix/Hyper/GMX/Vertex/Aevo）
- DAO 治理与参数时间锁
