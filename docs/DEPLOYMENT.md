# VaultCraft 部署手册（Hardhat）

本文档涵盖：准备环境、配置 .env、编译、部署到测试网、常见问题与验证步骤。

---

## 0. 准备环境

- Node.js ≥ 18, npm ≥ 9（Windows 已就绪）
- 测试网 RPC：
  - Base Sepolia: https://sepolia.base.org (ChainId 84532)
  - Arbitrum Sepolia: https://sepolia-rollup.arbitrum.io/rpc (ChainId 421614)
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

编辑 `.env`：

```
RPC_URL=https://sepolia.base.org
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
- baseSepolia / arbitrumSepolia 由 hardhat.config.ts 预置；都共用 `RPC_URL` 和 `PRIVATE_KEY`

---

## 3. 编译与单元测试

```
npx hardhat compile
npx hardhat test
```

---

## 4. 部署

Base Sepolia：
```
npm run deploy:baseSepolia
```

Arbitrum Sepolia：
```
npm run deploy:arbitrumSepolia
```

输出包含：
- MockERC20 资产地址（若未提供 ASSET_ADDRESS）
- Vault 合约地址（admin=deployer, manager=INIT_MANAGER, guardian=INIT_GUARDIAN）

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
