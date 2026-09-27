from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AIOps Platform"
    debug: bool = False

    # Data providers — set USE_MOCK_PROVIDERS=true for local dev without cluster
    use_mock_providers: bool = False
    kubernetes_namespace: str = "default"

    prometheus_url: str = (
        "http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090"
    )
    dcgm_exporter_url: str = (
        "http://nvidia-dcgm-exporter.gpu-operator.svc.cluster.local:9400"
    )
    loki_url: str = ""
    qdrant_url: str = ""

    database_url: str = "postgresql://aiops:aiops@postgres:5432/aiops"

    # Orchestrator
    auto_enrich_on_alert: bool = True
    seed_demo_incident: bool = False

    # LLM agent (vLLM OpenAI-compatible API)
    agent_enabled: bool = True
    llm_api_url: str = "http://aiops-llm.local/"
    llm_model: str = "hebrew"
    llm_api_key: str = ""
    openai_api_key: str = ""  # alias fallback

    # ArgoCD settings
    argocd_server: str="http://argo.local"
    argocd_token: str="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhcmdvY2QiLCJzdWIiOiJhdXRvbWF0aW9uLWJvdDphcGlLZXkiLCJuYmYiOjE3OTA0MjE2MzEsImlhdCI6MTc5MDQyMTYzMSwianRpIjoiYjM0OWFkMTktMDA1OS00NGQ0LTgxNTQtYzUzMWQ1N2U2M2IyIn0.pgYw6jv7cA5iEjZuX0Pnw47Wb-g5hOKHz6JgN6-zxoM"
    argocd_verify_ssl: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def effective_llm_api_key(self) -> str:
        return self.llm_api_key or self.openai_api_key or "not-needed"

    @property
    def uses_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


settings = Settings()
