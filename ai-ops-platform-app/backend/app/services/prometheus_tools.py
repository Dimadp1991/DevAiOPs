"""Prometheus and DCGM GPU metrics — real HTTP queries with mock fallback."""

import logging
from typing import Any

import httpx

from app.config import settings
from app.models.schemas import GpuMetrics

logger = logging.getLogger(__name__)


class PrometheusTools:
    """Query Prometheus for container and DCGM GPU metrics."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.prometheus_url).rstrip("/")
        self.dcgm_url = settings.dcgm_exporter_url.rstrip("/")

    def _use_mock(self) -> bool:
        return settings.use_mock_providers or not self.base_url

    async def query_prometheus(self, promql: str) -> dict[str, Any]:
        if self._use_mock():
            return {"status": "mock", "data": {"result": []}}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/query",
                    params={"query": promql},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("Prometheus query failed (%s): %s", promql[:80], exc)
            return {"status": "error", "data": {"result": []}, "error": str(exc)}

    def _scalar_from_result(self, data: dict[str, Any]) -> float | None:
        results = data.get("data", {}).get("result", [])
        if not results:
            return None
        try:
            return float(results[0]["value"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    async def get_gpu_metrics(
        self, pod_name: str = "", node_name: str = "", namespace: str = "default"
    ) -> GpuMetrics | None:
        if self._use_mock():
            return None

        # GPU utilization query
        util_queries = [
            "custom_gpu_utilization_percent",
            f'custom_gpu_utilization_percent{{pod="{pod_name}"}}' if pod_name else "",
            f'DCGM_FI_DEV_GPU_UTIL{{pod="{pod_name}",namespace="{namespace}"}}' if pod_name else "",
            "avg(DCGM_FI_DEV_GPU_UTIL)",
        ]
        util = None
        for q in util_queries:
            if not q:
                continue
            util = self._scalar_from_result(await self.query_prometheus(q))
            if util is not None:
                break

        # GPU device model info
        gpu_model = ""
        info_data = await self.query_prometheus("gpu_device_info_info")
        results = info_data.get("data", {}).get("result", [])
        if results and "metric" in results[0]:
            gpu_model = results[0]["metric"].get("model", "")

        # GPU VRAM memory bytes
        used_bytes = self._scalar_from_result(
            await self.query_prometheus("custom_gpu_memory_used_bytes")
        )
        if used_bytes is None and pod_name:
            used_bytes = self._scalar_from_result(
                await self.query_prometheus(f'DCGM_FI_DEV_FB_USED{{pod="{pod_name}"}}')
            )

        total_bytes = self._scalar_from_result(
            await self.query_prometheus("custom_gpu_memory_total_bytes")
        )

        # Convert bytes to MB if bytes query returned data
        vram_used_mb = (used_bytes / (1024 * 1024)) if used_bytes is not None else 0.0
        vram_total_mb = (total_bytes / (1024 * 1024)) if total_bytes is not None else 0.0

        # GPU temperature & power usage
        temp_celsius = self._scalar_from_result(
            await self.query_prometheus("custom_gpu_temperature_celsius")
        )
        power_watts = self._scalar_from_result(
            await self.query_prometheus("custom_gpu_power_usage_watts")
        )

        xid_errors: list[int] = []
        xid_data = await self.query_prometheus(
            f'DCGM_FI_DEV_XID_ERRORS{{Hostname="{node_name}"}}' if node_name else "DCGM_FI_DEV_XID_ERRORS"
        )
        for item in xid_data.get("data", {}).get("result", []):
            try:
                val = int(float(item["value"][1]))
                if val > 0:
                    xid_errors.append(val)
            except (KeyError, ValueError, TypeError):
                continue

        if util is None and used_bytes is None and temp_celsius is None:
            return None

        return GpuMetrics(
            model=gpu_model,
            utilization_pct=round(util or 0.0, 1),
            vram_used_mb=round(vram_used_mb, 1),
            vram_total_mb=round(vram_total_mb, 1),
            temperature_celsius=round(temp_celsius, 1) if temp_celsius is not None else None,
            power_watts=round(power_watts, 2) if power_watts is not None else None,
            xid_errors=list(set(xid_errors)),
        )

    async def get_pod_metrics(self, pod_name: str, namespace: str = "default") -> dict[str, Any]:
        if self._use_mock() or pod_name in ("", "unknown-pod"):
            return {}

        cpu_q = (
            f'sum(rate(container_cpu_usage_seconds_total{{pod="{pod_name}",namespace="{namespace}",container!=""}}[5m]))'
        )
        mem_q = (
            f'sum(container_memory_rss{{pod="{pod_name}",namespace="{namespace}",container!=""}})'
        )

        cpu_val = self._scalar_from_result(await self.query_prometheus(cpu_q))
        mem_val = self._scalar_from_result(await self.query_prometheus(mem_q))

        metrics: dict[str, Any] = {}
        if cpu_val is not None:
            metrics["cpu_usage_cores"] = round(cpu_val, 2)
        if mem_val is not None:
            if mem_val > 1024**3:
                metrics["memory_rss_bytes"] = f"{mem_val / (1024**3):.1f}Gi"
            elif mem_val > 1024**2:
                metrics["memory_rss_bytes"] = f"{mem_val / (1024**2):.0f}Mi"
            else:
                metrics["memory_rss_bytes"] = f"{mem_val:.0f}"
        return metrics


prometheus_tools = PrometheusTools()
