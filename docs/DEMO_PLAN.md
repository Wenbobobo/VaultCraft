## 黑客松评审 Demo 计划（GUI 优先）

目标：用最少“讲解文字 + 最多 GUI 画面”完成 5–8 分钟演示。

### 1) 预演准备（仅 GUI 所需）
- 根 `.env`（统一配置）：
  - HYPER_RPC_URL / HYPER_API_URL
  - PRIVATE_KEY（或 HYPER_TRADER_PRIVATE_KEY）+ ADDRESS（可选，仅用于监听回写）
  - ENABLE_HYPER_SDK=1；ENABLE_LIVE_EXEC=1（如需实单）；ENABLE_USER_WS_LISTENER=1（如需回写）；ENABLE_SNAPSHOT_DAEMON=1（可选）
  - EXEC_ALLOWED_SYMBOLS=BTC,ETH（风控白名单）
- 余额：ADDRESS 有 Hyper Testnet gas
- 启动：后台 `uvicorn app.main:app --reload --port 8000`；前台 `pnpm dev`（apps/vaultcraft-frontend）
- 检查：前端页头 StatusBar（或 `/api/v1/status`）显示 Mode、SDK、Listener、Snapshot、chainId/block
 - 钱包按钮：未接入钱包时，将根 `.env` 中 `NEXT_PUBLIC_ENABLE_WALLET=0` 隐藏“Connect Wallet”，避免误触。

（CLI 仅作为排障备用，不进入评审脚本）

### 2) 演示剧本（全 GUI）
1. 首页（Discover）
   - 价值主张：Public 透明与 Private 不披露；筛选/排序（Sharpe/AUM/Return）
   - 状态条：Live/Dry-run、SDK、Listener、Snapshot 与 chainId/block
2. 详情页（Vault Detail）
   - KPI 区：AUM / Unit NAV / Return / Sharpe / MDD
   - NAV 曲线：随快照/NAV 序列更新（/nav_series）
   - 事件流（Transactions）：exec_open/exec_close/fill/rejected/error 清晰标注
3. 受控执行（Exec 标签）
   - GUI 点击：选择 `ETH`、`size=0.1`、`Buy` → 预检查（/pretrade）通过 → 发送
   - 即刻反馈：事件流出现 `exec_open`（ack 或 dry_run），随后（可选）`fill`；曲线更新
   - 再次点击 `Close size=0.1`，事件与曲线更新

旁白要点：
- 私募透明边界：Private 仅展示 NAV/绩效，不披露持仓；Public 可扩展展示持仓
- 受控执行：风险白名单/杠杆范围/名义上限；一键切换 Live/Dry-run；全在 .env 控制
- 稳定性：行情有重试 + last‑good；Listener 有重连；快照守护提供平滑曲线

### 3) 兜底方案（现场网络/权限异常时）
- 若 Listener 不可用：仍可用 ack→positions 回写→快照 完成闭环；对观众无感
- 若钱包连接不可用：隐藏“连接钱包”交互（`NEXT_PUBLIC_ENABLE_WALLET=0`），保留 Exec 面板（后端受控）
- 若 RPC 波动：/status 观察网络；/events /nav_series 可人工验证数据
