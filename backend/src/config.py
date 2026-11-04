"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_DIR = REPO_ROOT / "backend" / "data" / "faiss"
DEFAULT_DOCS_DIR = REPO_ROOT / "sample_documents"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Engineering Knowledge Assistant"
    app_version: str = "0.1.0"
    environment: str = "development"

    # Retrieval
    # FastEmbed ONNX MiniLM — same family as all-MiniLM-L6-v2, no PyTorch runtime.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    faiss_index_dir: Path = DEFAULT_INDEX_DIR
    sample_docs_dir: Path = DEFAULT_DOCS_DIR
    retrieval_top_k: int = 4
    retrieval_score_threshold: float = 0.25
    chunk_size: int = 800
    chunk_overlap: int = 120
    max_context_chars: int = 6000

    # Tavily
    tavily_api_key: str | None = None
    tavily_max_results: int = 3
    tavily_search_depth: str = "basic"

    # LLM provider: auto | openai | azure
    # auto = OpenAI platform if OPENAI_API_KEY is set, else Azure OpenAI.
    llm_provider: str = "auto"

    # OpenAI platform (platform.openai.com credits / API keys)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Azure OpenAI (Azure Container Apps / cloud deployments)
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment: str = "gpt-5-mini"
    # gpt-5-mini uses many completion tokens as hidden reasoning; keep headroom.
    llm_max_tokens: int = 8000
    llm_temperature: float = 0.2
    estimated_input_cost_per_1k: float = 0.00015
    estimated_output_cost_per_1k: float = 0.0006

    # LangSmith
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "engineering-knowledge-assistant"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # API / budgets
    request_timeout_seconds: float = 60.0
    rate_limit_per_minute: int = 20
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"])

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def azure_configured(self) -> bool:
        return bool(self.azure_openai_api_key and self.azure_openai_endpoint)

    @property
    def llm_configured(self) -> bool:
        return self.resolved_llm_provider is not None

    @property
    def resolved_llm_provider(self) -> str | None:
        provider = (self.llm_provider or "auto").lower().strip()
        if provider == "openai":
            return "openai" if self.openai_configured else None
        if provider == "azure":
            return "azure" if self.azure_configured else None
        # auto
        if self.openai_configured:
            return "openai"
        if self.azure_configured:
            return "azure"
        return None

    @property
    def tavily_configured(self) -> bool:
        return bool(self.tavily_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
