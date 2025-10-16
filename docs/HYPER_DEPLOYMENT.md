# Hyper Testnet 部署与联调步骤（Exec Service v1）

本手册指导如何配置 Hyper Testnet（chainId 998）、验证 RPC、运行后端 Demo CLI、准备 Exec Service 环境，并与前端/合约演示联动。

---

## 1. 网络与 RPC

- 链：Hyper Testnet（chainId 998）
- RPC：`https://rpc.hyperliquid-testnet.xyz/evm`
- REST：`https://api.hyperliquid-testnet.xyz`

验证 RPC：
```
cd hardhat
npm run ping:hyper
# 输出示例：{"network":"hyperTestnet","chainId":998,"blockNumber":...,"gasPrice":"..."}
```

---

## 2. 环境变量（后端）

- `HYPER_RPC_URL`（可选，默认上面 Testnet RPC）
- `HYPER_API_URL`（默认 Testnet REST）
- `HYPER_API_KEY` / `HYPER_API_SECRET`（如需私有接口/服务账号）
- `ENABLE_HYPER_SDK`（默认 false）：启用官方 Python SDK 作为行情优先数据源（只读）
- `PRICE_TIMEOUT`（默认 5s）：行情请求超时
- 其他：`EXEC_LIMITS`（额度/频次/白名单），按需定义

启用 SDK（推荐）步骤：
```
cd apps/backend
uv venv
uv add hyperliquid-python-sdk
# 验证安装
uv run python -c "import hyperliquid, hyperliquid.info; print('OK')"
# Windows PowerShell 设置 env（或写入 .env）
$env:ENABLE_HYPER_SDK="1"
```

---

## 3. 后端与 Demo CLI（只读/干运行）

运行（Windows PowerShell）：
```
cd apps/backend
uv venv
# 启动 REST API（默认端口 8000）
uv run uvicorn app.main:app --reload --port 8000
# 另一个终端运行 Demo CLI
uv run python -m app.cli rpc-ping
uv run python -m app.cli build-open ETH 0.1 buy --leverage 5
uv run python -m app.cli build-close ETH --size 0.1
uv run python -m app.cli nav --cash 1000 --positions '{"ETH":0.2,"BTC":-0.1}' --prices '{"ETH":3000,"BTC":60000}'
```

说明：
- `rpc-ping`：检测 RPC 可用性（chainId、区块、gas）
- `build-open/close`：构造下单/平仓 payload（干运行，不落地）
- `nav`：从现金 + 头寸 + 指数价计算 NAV（仅演示会计口径）

---

## 4. Exec Service（v1 计划）

- 集成 Hyper Python SDK（或 REST/WS）：
  - open/close/reduce 下单接口（服务账号）
  - WS 监听成交，汇总账户权益
- 会计：`NAV = 现金腿 + Σ(持仓权益)`
- 承诺：周期性生成 NAV 快照 hash（上链/链下皆可），供前端和审计复核
- API：
  - `GET /api/v1/metrics/:vault`（KPI）
  - `GET /api/v1/nav/:vault`（NAV 时间序列）
  - `GET /api/v1/events/:vault`（事件）

---

## 5. 与合约/前端联动

- 合约：Vault 在 Base 或 HyperEVM 部署，前端读链（ps/totalAssets/isPrivate/lock/perfFeeP）
- 前端：私募仅显示 NAV/PnL（不显示持仓）；公募显示持仓（如接入 Adapter）
- 后端：聚合 NAV 与指标，前端调用展示

Demo Registry（演示金库目录）：
- 当前 `/api/v1/vaults` 返回内置的演示列表（私募/公募若干）用于前端渲染
- 部署到测试网后，可在 `deployments/hyper-testnet.json` 中维护 pairs/参数
- 后续版本会将注册表迁移到轻量数据库或链上事件索引，保持接口不变
  - Demo NAV 计算：后端内置两个示例地址 `0x1234...5678` 与 `0x8765...4321` 的现金+头寸配置，用于 `/api/v1/nav/:id` 计算演示 NAV；也可直接传入任意地址按默认配置计算

维护头寸（Positions）用于 NAV 计算：
- 文件：`deployments/positions.json`（可通过环境变量 `POSITIONS_FILE` 指定路径）
- 结构示例：
```
{
  "0x1234...5678": {
    "cash": 1000000,
    "positions": { "BTC": 0.1, "ETH": 2.0 },
    "denom": 1000000
  }
}
```
- CLI 管理：
```
cd apps/backend
uv run python -m app.cli positions:get 0x1234...5678
uv run python -m app.cli positions:set 0x1234...5678 '{"cash":1000000,"positions":{"BTC":0.2},"denom":1000000}'
```

---

## 6. 注意事项

- 测试前请先检查 Hyper 测试网 agent 钱包与 API 权限
- Demo 环境优先 dry-run（构造 payload、不真实下单）
- 需要真实下单时务必用小额测试资金，并启用额度/频次限权
```
常用 API（本地）
- GET http://127.0.0.1:8000/health
- GET http://127.0.0.1:8000/api/v1/markets
- GET http://127.0.0.1:8000/api/v1/price?symbols=BTC,ETH
- GET http://127.0.0.1:8000/api/v1/vaults
- GET http://127.0.0.1:8000/api/v1/vaults/0x1234...5678
```
