from fastapi import FastAPI

from .metrics import compute_metrics

app = FastAPI(title="VaultCraft v0 API")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/metrics")
def metrics_endpoint(nav_series: list[float]):
    """Compute basic metrics from a NAV series (daily)."""
    return compute_metrics(nav_series)

