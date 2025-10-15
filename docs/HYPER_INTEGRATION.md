# Hyper Testnet 集成方案（v1 规划）

目标：以 Hyper Testnet 作为 perps 执行与行情来源，形成“链上金库 + 链下执行 + 可验证会计”的混合范式，适配黑客松演示。

---

## 1. 角色与组件

- Exec Service（后端）
  - 与 Hyperliquid API 通信（REST/WS）
  - 管理 Session Key/API Key（服务账号）
  - 落库订单/成交回报/持仓权益，生成承诺（hash）
- Indexer（后端）
  - 读取 Vault 事件，与 Exec 数据对账
  - 周期性生成 NAV 快照，供前端展示
- 前端
  - 不直接下单（仅经理/服务），只读查看状态与 NAV

---

## 2. 执行流程（示意）

1) 经理在 Console 设定策略参数 → 服务端限权（额度/频次/白名单），生成 Session
2) Exec Service 调 Hyper API 下单（open/close/reduce）
3) 监听订单/成交回报（WS），汇总账户权益
4) Indexer/Exec 产出 NAV 快照（资产 = 现金腿 + 持仓权益），写入承诺日志（链上/链下）
5) 前端展示 NAV/PnL；私募不显示持仓明细

---

## 3. 会计与证明（MVP）

- 合成 NAV：以 Hyper 标的指数价/成交价 & 持仓 Delta 计算实时权益
- 周期性 Checkpoint：将 NAV 数值 + 数据源签名打包为承诺（hash）
- v1 可选：Merkle 证明/TEE/ZK 路线图

---

## 4. 失败与回退

- API 不可用/波动过大 → 暂停下单，仅展示 NAV
- 对账不一致 → 标记异常，冻结“增加敞口”，允许减仓与赎回

---

## 5. 开发与配置

- 环境变量（后端）
  - HYPER_API_URL / WS_URL
  - HYPER_API_KEY / SECRET（如适用）
  - EXEC_LIMITS（额度/频次）
- 测试
  - mock Hyper API 回放（录制/模拟）
  - 集成测试：下单→成交→权益→NAV 承诺→前端展示

