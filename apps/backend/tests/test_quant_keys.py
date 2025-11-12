from __future__ import annotations

from pathlib import Path

from app.quant_keys import list_keys, update_keys


def test_quant_keys_add_remove(tmp_path):
    env_file = Path(tmp_path) / ".env"
    assert list_keys(env_file) == []

    update_keys(env_file, add=["alpha", "beta"])
    assert list_keys(env_file) == ["alpha", "beta"]

    update_keys(env_file, add=["beta", "gamma"])
    assert list_keys(env_file) == ["alpha", "beta", "gamma"]

    update_keys(env_file, remove=["beta"])
    assert list_keys(env_file) == ["alpha", "gamma"]

    update_keys(env_file, set_keys=["omega", "omega", "alpha"])
    assert list_keys(env_file) == ["omega", "alpha"]


def test_quant_keys_generate(tmp_path):
    env_file = Path(tmp_path) / ".env"
    result = update_keys(env_file, add=["seed"], generate=2)
    assert len(result) == 3
    assert result[0] == "seed"
    generated = result[1:]
    assert all(len(k) >= 10 for k in generated)
