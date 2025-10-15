from __future__ import annotations

import argparse
import json

from app.cli import cmd_build_open, cmd_build_close, cmd_nav, cmd_rpc_ping
from app.hyper_client import RPCInfo, HyperHTTP


def test_cmd_build_open(capsys):
    args = argparse.Namespace(symbol="ETH", size=1.0, side="buy", reduce=True, leverage=5.0, api="https://api")
    cmd_build_open(args)
    out = json.loads(capsys.readouterr().out)
    assert out["type"] == "open" and out["reduce_only"] is True and out["leverage"] == 5.0


def test_cmd_build_close(capsys):
    args = argparse.Namespace(symbol="BTC", size=0.5, api="https://api")
    cmd_build_close(args)
    out = json.loads(capsys.readouterr().out)
    assert out == {"type": "close", "symbol": "BTC", "size": 0.5}


def test_cmd_nav(capsys):
    args = argparse.Namespace(cash=100.0, positions='{"ETH":0.1}', prices='{"ETH":2000.0}')
    cmd_nav(args)
    out = json.loads(capsys.readouterr().out)
    assert abs(out["nav"] - 300.0) < 1e-9


def test_cmd_rpc_ping(monkeypatch, capsys):
    def fake_rpc_ping(self):
        return RPCInfo(chain_id=998, block_number=123, gas_price_wei=100)

    monkeypatch.setattr(HyperHTTP, "rpc_ping", fake_rpc_ping)
    args = argparse.Namespace(api="https://api", rpc="https://rpc")
    cmd_rpc_ping(args)
    out = json.loads(capsys.readouterr().out)
    assert out["chainId"] == 998 and out["blockNumber"] == 123 and out["gasPriceWei"] == 100

