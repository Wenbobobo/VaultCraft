from __future__ import annotations

import secrets
from pathlib import Path
from typing import Iterable, List, Tuple

ENV_VAR = "QUANT_API_KEYS"


def _repo_root() -> Path:
    root = Path(__file__).resolve().parent
    for _ in range(10):
        if (root / ".git").exists() or (root / "README.md").exists():
            return root
        if root.parent == root:
            break
        root = root.parent
    return root


def resolve_env_file(path: str | None = None) -> Path:
    if path:
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path.cwd() / p
        return p
    return (_repo_root() / ".env").resolve()


def _read_env_lines(env_file: Path) -> List[str]:
    if not env_file.exists():
        return []
    return env_file.read_text(encoding="utf-8").splitlines()


def _write_env_lines(env_file: Path, lines: List[str]) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines).rstrip() + "\n"
    env_file.write_text(content, encoding="utf-8")


def _split_keys(value: str) -> List[str]:
    stripped = value.strip().strip('"').strip("'")
    if not stripped:
        return []
    return [k.strip() for k in stripped.split(",") if k.strip()]


def _parse_quant_line(lines: List[str]) -> Tuple[List[str], int | None]:
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        left, right = line.split("=", 1)
        if left.strip() == ENV_VAR:
            return _split_keys(right), idx
    return [], None


def list_keys(env_file: Path) -> List[str]:
    lines = _read_env_lines(env_file)
    keys, _ = _parse_quant_line(lines)
    return keys


def _dedupe(seq: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in seq:
        token = item.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def _set_line(lines: List[str], value: str, idx: int | None) -> List[str]:
    new_line = f"{ENV_VAR}={value}"
    if idx is None:
        lines.append(new_line)
        return lines
    lines[idx] = new_line
    return lines


def _generate_key() -> str:
    return secrets.token_urlsafe(24)


def update_keys(
    env_file: Path,
    *,
    add: Iterable[str] | None = None,
    remove: Iterable[str] | None = None,
    set_keys: Iterable[str] | None = None,
    generate: int = 0,
) -> List[str]:
    lines = _read_env_lines(env_file)
    current, idx = _parse_quant_line(lines)
    if set_keys is not None:
        target = _dedupe(set_keys)
    else:
        target = list(current)
        if add:
            for key in add:
                token = key.strip()
                if token and token not in target:
                    target.append(token)
        if remove:
            drop = {k.strip() for k in remove if k.strip()}
            target = [k for k in target if k not in drop]
        for _ in range(max(generate, 0)):
            target.append(_generate_key())
        target = _dedupe(target)
    joined = ",".join(target)
    lines = _set_line(lines, joined, idx)
    _write_env_lines(env_file, lines)
    return target
