from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict

import httpx

from .hyper_client import HyperHTTP, DEFAULT_API, DEFAULT_RPC
from .hyper_exec import HyperExecClient, Order
from .exec_service import ExecService
from .positions import get_profile, set_profile
from .soak import run_soak, file_sink
from .quant_keys import list_keys as quant_list_keys, update_keys as quant_update_keys, resolve_env_file as quant_env_file


def cmd_rpc_ping(args: argparse.Namespace) -> None:
    http = HyperHTTP(api_base=args.api, rpc_url=args.rpc)
    info = http.rpc_ping()
    print(json.dumps({
        "rpc": http.rpc_url,
        "chainId": info.chain_id,
        "blockNumber": info.block_number,
        "gasPriceWei": info.gas_price_wei,
    }, indent=2))


def cmd_build_open(args: argparse.Namespace) -> None:
    cli = HyperExecClient(base_url=args.api)
    payload = cli.build_open_order(Order(symbol=args.symbol, size=args.size, side=args.side, reduce_only=args.reduce, leverage=args.leverage))
    print(json.dumps(payload, indent=2))


def cmd_build_close(args: argparse.Namespace) -> None:
    cli = HyperExecClient(base_url=args.api)
    payload = cli.build_close_order(args.symbol, size=args.size)
    print(json.dumps(payload, indent=2))


def cmd_nav(args: argparse.Namespace) -> None:
    positions: Dict[str, float] = json.loads(args.positions)
    prices: Dict[str, float] = json.loads(args.prices)
    nav = HyperExecClient.pnl_to_nav(cash=args.cash, positions=positions, index_prices=prices)
    print(json.dumps({"nav": nav}, indent=2))


def cmd_quant_order(args: argparse.Namespace) -> None:
    base = args.backend.rstrip("/")
    headers = {}
    if args.key:
        headers["X-Quant-Key"] = args.key
    timeout = getattr(args, "timeout", 15.0)
    if args.close:
        payload: Dict[str, object] = {"symbol": args.symbol, "vault": args.vault, "venue": args.venue}
        if args.size is not None:
            payload["size"] = args.size
        url = f"{base}/api/v1/quant/orders/close"
    else:
        if args.size is None or args.size <= 0:
            raise SystemExit("--size must be > 0 for open orders")
        payload = {
            "symbol": args.symbol,
            "size": args.size,
            "side": args.side,
            "vault": args.vault,
            "venue": args.venue,
            "reduce_only": args.reduce_only,
            "order_type": args.order_type,
        }
        if args.limit_price is not None:
            payload["limit_price"] = args.limit_price
        if args.time_in_force:
            payload["time_in_force"] = args.time_in_force
        if args.leverage is not None:
            payload["leverage"] = args.leverage
        if args.stop_loss is not None:
            payload["stop_loss"] = args.stop_loss
        if args.take_profit is not None:
            payload["take_profit"] = args.take_profit
        url = f"{base}/api/v1/quant/orders/open"
    resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError:
        print(f"[quant-order] error {resp.status_code}: {resp.text}")
        raise SystemExit(1)
    print(json.dumps(resp.json(), indent=2))


def _print_quant_keys(env_file: Path, keys: list[str]) -> None:
    if not keys:
        print(f"{env_file}: (empty)")
        return
    print(f"{env_file}: {', '.join(keys)}")


def cmd_quant_keys(args: argparse.Namespace) -> None:
    env_file = quant_env_file(args.env_file)
    ops_requested = any(
        [
            args.add,
            args.remove,
            args.set_keys,
            args.generate is not None,
        ]
    )
    if args.set_keys and (args.add or args.remove or (args.generate and args.generate > 0)):
        raise SystemExit("--set cannot be combined with --add/--remove/--generate")
    if not ops_requested and not args.list:
        raise SystemExit("specify --list, --add, --remove, --set, or --generate")
    if not ops_requested and args.list:
        keys = quant_list_keys(env_file)
        _print_quant_keys(env_file, keys)
        return
    generated = max(args.generate or 0, 0)
    updated = quant_update_keys(
        env_file,
        add=args.add,
        remove=args.remove,
        set_keys=args.set_keys,
        generate=generated,
    )
    _print_quant_keys(env_file, updated)


def main() -> None:
    parser = argparse.ArgumentParser(prog="vaultcraft-cli", description="VaultCraft backend demo CLI")
    parser.set_defaults(func=lambda _: parser.print_help())
    sub = parser.add_subparsers()

    p1 = sub.add_parser("rpc-ping", help="Ping Hyper EVM RPC (chainId, block, gas)")
    p1.add_argument("--rpc", default=os.getenv("HYPER_RPC_URL", DEFAULT_RPC))
    p1.add_argument("--api", default=os.getenv("HYPER_API_URL", DEFAULT_API))
    p1.set_defaults(func=cmd_rpc_ping)

    p2 = sub.add_parser("build-open", help="Build open order payload (dry-run)")
    p2.add_argument("symbol")
    p2.add_argument("size", type=float)
    p2.add_argument("side", choices=["buy","sell"])
    p2.add_argument("--reduce", action="store_true")
    p2.add_argument("--leverage", type=float, default=None)
    p2.add_argument("--api", default=os.getenv("HYPER_API_URL", DEFAULT_API))
    p2.set_defaults(func=cmd_build_open)

    p3 = sub.add_parser("build-close", help="Build close order payload (dry-run)")
    p3.add_argument("symbol")
    p3.add_argument("--size", type=float, default=None)
    p3.add_argument("--api", default=os.getenv("HYPER_API_URL", DEFAULT_API))
    p3.set_defaults(func=cmd_build_close)

    p4 = sub.add_parser("nav", help="Compute NAV from cash + positions + index prices")
    p4.add_argument("--cash", type=float, default=0.0)
    p4.add_argument("--positions", required=True, help='JSON dict, e.g. {"ETH":0.2,"BTC":-0.1}')
    p4.add_argument("--prices", required=True, help='JSON dict, e.g. {"ETH":3000,"BTC":60000}')
    p4.set_defaults(func=cmd_nav)

    # exec:open
    def cmd_exec_open(args: argparse.Namespace) -> None:
        svc = ExecService()
        out = svc.open(args.vault, Order(symbol=args.symbol, size=args.size, side=args.side, reduce_only=args.reduce, leverage=args.leverage))
        print(json.dumps(out, indent=2))

    p5 = sub.add_parser("exec-open", help="Execute open (live if enabled, else dry-run)")
    p5.add_argument("vault")
    p5.add_argument("symbol")
    p5.add_argument("size", type=float)
    p5.add_argument("side", choices=["buy","sell"])
    p5.add_argument("--reduce", action="store_true")
    p5.add_argument("--leverage", type=float, default=None)
    p5.set_defaults(func=cmd_exec_open)

    # exec:close
    def cmd_exec_close(args: argparse.Namespace) -> None:
        svc = ExecService()
        out = svc.close(args.vault, symbol=args.symbol, size=args.size)
        print(json.dumps(out, indent=2))

    p6 = sub.add_parser("exec-close", help="Execute close (live if enabled, else dry-run)")
    p6.add_argument("vault")
    p6.add_argument("symbol")
    p6.add_argument("--size", type=float, default=None)
    p6.set_defaults(func=cmd_exec_close)

    # positions:get
    def cmd_positions_get(args: argparse.Namespace) -> None:
        prof = get_profile(args.vault)
        print(json.dumps(prof, indent=2))

    p5 = sub.add_parser("positions:get", help="Get positions profile for a vault (cash, positions, denom)")
    p5.add_argument("vault")
    p5.set_defaults(func=cmd_positions_get)

    # positions:set
    def cmd_positions_set(args: argparse.Namespace) -> None:
        profile = json.loads(args.profile)
        set_profile(args.vault, profile)
        print(json.dumps({"ok": True}, indent=2))

    p6 = sub.add_parser("positions:set", help="Set positions profile JSON for a vault")
    p6.add_argument("vault")
    p6.add_argument("profile", help='JSON, e.g. {"cash":1000000,"positions":{"BTC":0.1,"ETH":2.0},"denom":1000000}')
    p6.set_defaults(func=cmd_positions_set)

    def cmd_soak(args: argparse.Namespace) -> None:
        base = args.backend.rstrip("/")
        timeout = httpx.Timeout(args.timeout, connect=args.timeout)
        sink = file_sink(Path(args.outfile))

        with httpx.Client(base_url=base, timeout=timeout, trust_env=False) as client:
            def fetch_status():
                resp = client.get("/api/v1/status")
                resp.raise_for_status()
                return resp.json()

            def fetch_vaults():
                resp = client.get("/api/v1/vaults")
                resp.raise_for_status()
                data = resp.json()
                vaults = data.get("vaults", [])
                return [v.get("id") for v in vaults if isinstance(v, dict) and v.get("id")]

            def fetch_metrics(vault_id: str):
                resp = client.get(f"/api/v1/metrics/{vault_id}")
                resp.raise_for_status()
                return resp.json()

            summary = run_soak(
                duration_sec=args.duration,
                interval_sec=args.interval,
                fetch_status=fetch_status,
                fetch_vaults=fetch_vaults,
                fetch_metrics=fetch_metrics,
                sink=sink,
            )
        print(json.dumps(summary, indent=2))

    p7 = sub.add_parser("soak", help="Run soak monitoring loop against a running backend")
    p7.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"), help="Backend base URL")
    p7.add_argument("--duration", type=float, default=300.0, help="Duration in seconds (default 5 minutes)")
    p7.add_argument("--interval", type=float, default=30.0, help="Sampling interval in seconds")
    p7.add_argument("--outfile", default="logs/soak-report.jsonl", help="Analytics NDJSON output")
    p7.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout per request")
    p7.set_defaults(func=cmd_soak)

    async def _consume_ws(url: str, headers: Dict[str, str], outfile: Path, duration: float) -> None:
        import websockets  # type: ignore
        import asyncio

        end = time.time() + duration
        outfile.parent.mkdir(parents=True, exist_ok=True)
        async with websockets.connect(url, extra_headers=headers, ping_interval=None) as ws:
            while time.time() < end:
                msg = await asyncio.wait_for(ws.recv(), timeout=duration)
                outfile.write_text("")  # ensure file exists
                with outfile.open("a", encoding="utf-8") as fh:
                    fh.write(msg if isinstance(msg, str) else json.dumps(msg))
                    fh.write("\n")

    def cmd_quant_ws(args: argparse.Namespace) -> None:
        import asyncio
        headers = {}
        if args.key:
            headers["X-Quant-Key"] = args.key
        url = args.url or f"ws://127.0.0.1:8000/ws/quant?vault={args.vault}&interval={args.interval}"
        outfile = Path(args.outfile)

        async def run():
            try:
                await _consume_ws(url, headers, outfile, args.duration)
            except Exception as exc:
                print(f"quant ws error: {exc}")

        asyncio.run(run())

    p8 = sub.add_parser("quant-ws", help="Connect to /ws/quant and log snapshots + deltas/events")
    p8.add_argument("--url", help="Override WebSocket URL (default ws://127.0.0.1:8000/ws/quant)")
    p8.add_argument("--vault", default="_global", help="Vault id to subscribe")
    p8.add_argument("--interval", type=float, default=5.0, help="Snapshot interval seconds")
    p8.add_argument("--duration", type=float, default=60.0, help="Duration in seconds")
    p8.add_argument("--outfile", default="logs/quant-ws.log", help="Append raw JSON snapshots to this file")
    p8.add_argument("--key", help="Quant API key to pass via X-Quant-Key header")
    p8.set_defaults(func=cmd_quant_ws)

    p10 = sub.add_parser("quant-order", help="Submit quant order via backend REST (requires ENABLE_QUANT_ORDERS=1)")
    p10.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"), help="Backend base URL")
    p10.add_argument("--key", required=True, help="Quant API key (X-Quant-Key)")
    p10.add_argument("--vault", default="_global", help="Logical vault id (default _global)")
    p10.add_argument("--symbol", required=True, help="Symbol, e.g. ETH")
    p10.add_argument("--size", type=float, help="Order size (positive). Optional for --close.")
    p10.add_argument("--side", choices=["buy", "sell"], default="buy")
    p10.add_argument("--venue", default="hyper", help="Execution venue (hyper, mock_gold, ...)")
    p10.add_argument("--leverage", type=float, help="Optional leverage")
    p10.add_argument("--order-type", choices=["market", "limit"], default="market")
    p10.add_argument("--time-in-force", dest="time_in_force", help="TIF for limit orders (Gtc, Ioc, Fok)")
    p10.add_argument("--limit-price", type=float, dest="limit_price", help="Required when order-type=limit")
    p10.add_argument("--reduce-only", action="store_true", help="Mark order as reduce-only")
    p10.add_argument("--stop-loss", type=float, dest="stop_loss")
    p10.add_argument("--take-profit", type=float, dest="take_profit")
    p10.add_argument("--timeout", type=float, default=15.0)
    p10.add_argument("--close", action="store_true", help="Call /orders/close instead of open")
    p10.set_defaults(func=cmd_quant_order)

    p9 = sub.add_parser("quant-keys", help="Inspect or edit QUANT_API_KEYS inside an env file")
    p9.add_argument("--env-file", help="Path to .env (default: repo .env)")
    p9.add_argument("--list", action="store_true", help="Print keys (after mutation if any)")
    p9.add_argument("--add", nargs="+", help="Add one or more keys")
    p9.add_argument("--remove", nargs="+", help="Remove one or more keys")
    p9.add_argument("--set", nargs="+", dest="set_keys", help="Replace with the provided keys (mutually exclusive)")
    p9.add_argument("--generate", type=int, nargs="?", const=1, help="Append N random keys (default 1)")
    p9.set_defaults(func=cmd_quant_keys)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
