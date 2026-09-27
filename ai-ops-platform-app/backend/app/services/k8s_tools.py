"""Kubernetes data retrieval — real in-cluster API with mock fallback."""

from datetime import datetime, timezone
import logging

from app.config import settings
from app.models.schemas import K8sState
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class K8sTools:
    """Fetch pod status, events, and logs from Kubernetes API."""

    def __init__(self, namespace: str | None = None) -> None:
        self.namespace = namespace or settings.kubernetes_namespace
        self._core_api = None
        self._apps_api = None
        self._available = False
        self._ApiException = Exception
        if not settings.use_mock_providers:
            self._init_client()

    def _init_client(self) -> None:
        try:


            self._ApiException = ApiException
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()
            self._core_api = client.CoreV1Api()
            self._apps_api = client.AppsV1Api()
            self._available = True
            logger.info("Kubernetes client initialized")
        except Exception as exc:
            logger.warning("Kubernetes client unavailable (%s) — using mock K8s data", exc)

    async def get_pod_status(self, pod_name: str, namespace: str | None = None) -> K8sState:
        ns = namespace or self.namespace
        if not self._available or pod_name in ("", "unknown-pod"):
            return self._mock_pod_status(pod_name, ns)

        try:
            pod = self._core_api.read_namespaced_pod(name=pod_name, namespace=ns)
            restarts = sum(
                (cs.restart_count or 0)
                for cs in (pod.status.container_statuses or [])
            )
            pod_status = pod.status.phase or "Unknown"
            for cs in pod.status.container_statuses or []:
                if cs.state and cs.state.waiting and cs.state.waiting.reason:
                    pod_status = cs.state.waiting.reason
                    break

            health_check = ""
            for cs in pod.status.container_statuses or []:
                if cs.state and cs.state.waiting:
                    health_check = f"{cs.name}: {cs.state.waiting.reason} — {cs.state.waiting.message or ''}"
                    break
                if cs.last_state and cs.last_state.terminated:
                    term = cs.last_state.terminated
                    health_check = f"{cs.name}: exit {term.exit_code} — {term.reason or ''}"

            ready_replicas = await self._deployment_replicas(pod, ns)

            return K8sState(
                pod_name=pod_name,
                pod_status=pod_status,
                restarts=restarts,
                deployment_ready_replicas=ready_replicas,
                health_check=health_check.strip(),
                namespace=ns,
            )
        except self._ApiException as exc:
            if exc.status == 404:
                return K8sState(
                    pod_name=pod_name,
                    pod_status="NotFound",
                    health_check=f"Pod {pod_name} not found in namespace {ns}",
                    namespace=ns,
                )
            logger.error("K8s get_pod_status error: %s", exc)
            return self._mock_pod_status(pod_name, ns)

    async def _deployment_replicas(self, pod, ns: str) -> str:
        owner_refs = pod.metadata.owner_references or []
        for ref in owner_refs:
            if ref.kind == "ReplicaSet":
                try:
                    rs = self._apps_api.read_namespaced_replica_set(
                        name=ref.name, namespace=ns
                    )
                    for rs_ref in rs.metadata.owner_references or []:
                        if rs_ref.kind == "Deployment":
                            dep = self._apps_api.read_namespaced_deployment(
                                name=rs_ref.name, namespace=ns
                            )
                            ready = dep.status.ready_replicas or 0
                            desired = dep.spec.replicas or 0
                            return f"{ready}/{desired}"
                except Exception:
                    pass
        return ""

    async def get_pod_node(self, pod_name: str, namespace: str | None = None) -> str:
        ns = namespace or self.namespace
        if not self._available or pod_name in ("", "unknown-pod"):
            return ""
        try:
            pod = self._core_api.read_namespaced_pod(name=pod_name, namespace=ns)
            return pod.spec.node_name or ""
        except Exception:
            return ""

    async def pod_requests_gpu(self, pod_name: str, namespace: str | None = None) -> bool:
        ns = namespace or self.namespace
        if not self._available or pod_name in ("", "unknown-pod"):
            return False
        try:
            pod = self._core_api.read_namespaced_pod(name=pod_name, namespace=ns)
            for container in pod.spec.containers:
                resources = container.resources
                if not resources:
                    continue
                for resource_dict in (resources.limits or {}, resources.requests or {}):
                    for key in resource_dict:
                        if "gpu" in key.lower():
                            return True
            return False
        except Exception:
            return False

    async def get_k8s_events(self, pod_name: str, namespace: str | None = None) -> list[str]:
        ns = namespace or self.namespace
        if not self._available:
            return self._mock_events(pod_name, ns)

        try:
            events = self._core_api.list_namespaced_event(
                namespace=ns,
                field_selector=f"involvedObject.name={pod_name}",
            )
            lines = []
            for ev in sorted(events.items, key=lambda e: e.last_timestamp or e.event_time, reverse=True)[:10]:
                ts = ev.last_timestamp or ev.event_time
                ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts else "unknown"
                lines.append(f"{ev.type} {ev.reason} {ts_str} {ev.source.component} {ev.message}")
            return lines or [f"No recent events for pod {pod_name} in {ns}"]
        except Exception as exc:
            logger.error("K8s get_k8s_events error: %s", exc)
            return self._mock_events(pod_name, ns)

    async def fetch_pod_logs(
        self, pod_name: str, namespace: str | None = None, tail_lines: int = 100
    ) -> list[str]:
        ns = namespace or self.namespace
        if not self._available or pod_name in ("", "unknown-pod"):
            return self._mock_logs(pod_name, ns)

        try:
            log_text = self._core_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=ns,
                tail_lines=tail_lines,
                timestamps=True,
            )
            lines = [line for line in log_text.strip().splitlines() if line.strip()]
            return lines[-tail_lines:] if lines else [f"No logs available for {pod_name}"]
        except Exception as exc:
            logger.error("K8s fetch_pod_logs error: %s", exc)
            return [f"Failed to fetch logs: {exc}"]

    async def delete_pod(self, pod_name: str, namespace: str | None = None) -> tuple[bool, str]:
        ns = namespace or self.namespace
        if not self._available or pod_name in ("", "unknown-pod"):
            msg = f"Mock mode active — simulated pod deletion for {pod_name} in {ns}"
            logger.info(msg)
            return True, msg
        try:
            self._core_api.delete_namespaced_pod(name=pod_name, namespace=ns)
            msg = f"Successfully deleted pod {pod_name} in namespace {ns}"
            logger.info(msg)
            return True, msg
        except Exception as exc:
            if getattr(exc, "status", None) == 404 or "NotFound" in str(exc):
                msg = f"Pod {pod_name} was already deleted or not found in namespace {ns}"
                logger.info(msg)
                return True, msg
            msg = f"Failed to delete pod {pod_name} in namespace {ns}: {exc}"
            logger.error(msg)
            return False, msg

    async def rollback_deployment(self, deployment_name: str, namespace: str | None = None) -> tuple[bool, str]:
        ns = namespace or self.namespace
        if not self._available or not deployment_name or deployment_name == "unknown-service":
            msg = f"Mock mode active — simulated deployment rollback for {deployment_name} in {ns}"
            logger.info(msg)
            return True, msg
        try:
            # Trigger rollout restart by patching pod template annotation
            body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": datetime.now(timezone.utc).isoformat()
                            }
                        }
                    }
                }
            }
            self._apps_api.patch_namespaced_deployment(name=deployment_name, namespace=ns, body=body)
            msg = f"Successfully triggered rollout restart for deployment {deployment_name} in namespace {ns}"
            logger.info(msg)
            return True, msg
        except Exception as exc:
            msg = f"Failed to rollback deployment {deployment_name} in namespace {ns}: {exc}"
            logger.error(msg)
            return False, msg

    def _mock_pod_status(self, pod_name: str, ns: str) -> K8sState:
        return K8sState(
            pod_name=pod_name,
            pod_status="Unknown (mock)",
            restarts=0,
            deployment_ready_replicas="",
            health_check="Kubernetes API unavailable — enable in-cluster config or set USE_MOCK_PROVIDERS=false",
            namespace=ns,
        )

    def _mock_events(self, pod_name: str, ns: str) -> list[str]:
        return [f"No K8s events (mock) pod={pod_name} ns={ns}"]

    def _mock_logs(self, pod_name: str, ns: str) -> list[str]:
        return [f"No logs (mock) pod={pod_name} ns={ns}"]


k8s_tools = K8sTools()
