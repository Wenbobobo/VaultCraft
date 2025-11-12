# 多市场适配器技术方案（Gamma 阶段）

目标：在保持 Vault 内核与 Exec Service 架构不变的前提下，把 Hyper Perps 以外的市场（美股、贵金属、多 venue）纳入统一的 Router/Adapter + Exec pipeline，确保：

- **统一下单票据**：前端/Quant API 提交的订单无需关心 venue 细节，只需指定 `venue` + `symbol` + 订单参数。
- **风险与合规**：每个 vault 有清晰的 `venue_whitelist`、`symbol_whitelist`、杠杆/名义限制，由 `/api/v1/status` & `/api/v1/vaults/:id/risk` 暴露。
- **估值路径**：后台 `PriceRouter` 支持 per venue 的指数价/公允价回落链，NAV 计算与告警统一。
- **可扩展适配器**：链上 Router/Adapter（未来）与 Off-venue Exec Service（当前）都能通过同一接口扩展新市场。

---

## 1. 候选市场与调研摘要

| Venue | 覆盖资产 | 演示/Testnet | 接入方式 | 备注 |
| --- | --- | --- | --- | --- |
| **Hyper Perps** | BTC、ETH（持续扩充） | Hyper Testnet (chainId 998) | 现有 Hyper SDK / REST | 作为 “hyper” 参考实现，保留当前驱动 |
| **Synthetix Perps v3** | ETH、BTC、XAU、XAG、AAPL、TSLA 等 | Sepolia / Base Sepolia / OP Goerli | REST + smart wallet（Account abstraction） | 适合演示“黄金/美股”场景；需签名 + keeper 撮合，demo 可用 mock driver |
| **Polymarket (CLOB)** | 事件合约，可映射美元资产或 ETF | MATIC (mainnet) + 模拟 API | HTTP streaming (private API) | 用于展示“另类资产”执行；短期先做 off-chain mock adapter |
| **CMX Gold Mock Venue** | 现货黄金 (XAU) | 本地 deterministic order book | 内置 Python driver | 便于离线 demo：由 PriceRouter 拉 Chainlink XAU price，Exec driver 记录 position，事件写回 |

### Hyper Perps（现状）
- 已有 `HyperExecClient` + `HyperSDKDriver`；继续使用 `venue="hyper"`。
- 价格：`PriceRouter.get_index_prices` 先取 SDK mids，再回退 REST/演示价。

### Synthetix Perps（黄金/美股）
- Testnet：`https://perps-v3.testnet.synthetix.io`（支持 sXAU、sAAPL 等）。
- 交互：提交订单需 `Account` + `PerpsMarketProxy` 调用；对 MVP，可通过后台 driver 调用官方 REST Relayer（demo 模式）。
- 估值：使用 Synthetix 提供的 `markets/<symbol>/index-price`，或 Chainlink feed。
- 限制：资金费与 keeper 费用，需要最小保证金；Demo 走 dry-run 模式。

### Polymarket / 其它 CLOB
- 目标是展示“多 venue”结构，短期以内置 mock driver + 快照数据为主，后续替换为真实 API。
- 价格：Polymarket 提供 websockets；无外网时 fallback 为本地样本。

---

## 2. 扩展接口（高层）

### 2.1 `Order` 扩展
```python
@dataclass
class Order:
    symbol: str
    size: float
    side: str
    venue: str = "hyper"   # 新增
    reduce_only: bool = False
    leverage: float | None = None
    order_type: str = "market"
    ...
```
- 默认 `venue="hyper"`；Exec Panel 与 Quant API 可选 `synthetix`, `polymarket`, `mock-gold` 等。

### 2.2 Exec Service 路由
```
ExecService.open(vault, order):
    driver = self._resolve_driver(order.venue)
    self._validate(order, venue=order.venue)
    return driver.open(order)
```

- `_resolve_driver`：按 venue 查表。初期包含
  - `hyper`: 现有 Hyper SDK driver
  - `synthetix`: 新增 `SynthetixPerpsDriver`（demo: 构造 deterministic ack）
  - `mock_gold`: `MockGoldDriver`（记录头寸 + ack）
- 配置：`.env` 新增 `EXEC_ALLOWED_VENUES=hyper,mock_gold,synthetix`。

### 2.3 风控模板
- `/api/v1/status.flags.risk_template` 新增字段：
  ```json
  {
    "allowedSymbols": "BTC,ETH,XAU,AAPL",
    "allowedVenues": "hyper,mock_gold,synthetix",
    "perVenue": {
      "hyper": {"minLeverage":1,"maxLeverage":5},
      "synthetix": {"maxNotionalUsd":50000,"minNotionalUsd":50},
      "mock_gold": {"maxNotionalUsd":20000}
    }
  }
  ```
- `/api/v1/vaults/:id/risk` PUT 时允许覆写 `allowedVenues` & `perVenue`。

### 2.4 Quant API
- `/api/v1/quant/orders/open` body 支持 `venue` 字段，默认 "hyper"。
- CLI `quant-order ... --venue synthetix`。

---

## 3. 估值与持仓

- `positions.json` 增加结构：
  ```json
  {
    "vault-1": {
      "cash": 1000000,
      "positions": {
        "hyper::ETH": 1.5,
        "synthetix::XAU": -0.8,
        "mock_gold::XAU": 2.0
      }
    }
  }
  ```
- `PriceRouter.get_index_prices(symbols, venue=None)`：接受 `["hyper::ETH","synthetix::XAU"]` 或平级 `["ETH"]`（向后兼容）。
- NAV：把 symbol 拆分 venue，再选对的 price feed。

---

## 4. 开发里程碑

1. **Phase A – Backend 基础**
   - 扩展 `Order` + ExecService 路由。
   - 实作 `MockGoldDriver`（离线 XAU 市场），`SynthetixPerpsDriver`（dry-run placeholder）。
   - Risk Template 增加 `allowedVenues` & `perVenue`，API/CLI/Docs 更新。
   - Tests：`test_exec_multivenue_validation.py`、`test_quant_orders_with_venue.py`。
   - ✅ 2025-11：`mock_gold` driver + Exec Panel venue 切换、Quant/REST `venue` 参数、StatusBar `allowedVenues` 完成。

2. **Phase B – Price/NAV**
   - `PriceRouter` 支持 venue-specific feeds（Chainlink XAU、mock AAPL）。
   - `/api/v1/nav` & Status bar 显示“Venue: hyper/synthetix”。
   - Quant WS payload：`positions` 改为 `{"hyper":{"ETH":...},"synthetix":{...}}` or include `venues`.

3. **Phase C – Frontend**
   - Manager Exec 面板：symbol selector 改为 `(venue, symbol)` 联动；TradingView Tab 显示对应市场。
   - Risk tab：允许编辑 `allowedVenues` & per-venue限制。
   - Portfolio：展示分 venue 仓位。

4. **Phase D – On-chain Adapter（可选）**
   - Solidity Router 增加 `executeMulti(bytes data)` 支持 adapter id。
   - 新增 `AdapterMockGold.sol`（只在 demo 环境启用）。

---

## 5. 待确认与行动项

- [ ] 获取 Synthetix Testnet API key & Account abstraction脚本；决定是直接调用合约还是走 REST Relayer。
- [ ] 确认 Chainlink XAU feed 在 Hyper 或 Base-Sepolia 的可用性；若无则使用本地价格序列。
- [ ] Polymarket/美股 venue 的真实 API 是否可在 Demo 环境使用；若否，准备 deterministic mock。
- [ ] 讨论 `EXEC_ALLOWED_VENUES` 与 per-vault override 的 UI 提醒（StatusBar/ExecPanel）。
- [ ] 评估 Quant API 限频在多 venue 情况下的调整：例如 per-key per-venue 限额。

---

本方案作为 Gamma 阶段的工作说明书，会在实现过程中按阶段更新（加上演示命令、合约部署链接、实测数据）。后续实现将以 `mock_gold` 作为首个多市场适配器，以便快速完成端到端验证，再逐步接入 Synthetix/Polymarket 真正的 API。***
