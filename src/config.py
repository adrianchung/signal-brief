from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    @model_validator(mode="after")
    def _require_at_least_one_llm_key(self) -> "Settings":
        if not self.anthropic_api_key and not self.gemini_api_key:
            raise ValueError("At least one of ANTHROPIC_API_KEY or GEMINI_API_KEY must be set")
        return self

    # HN filtering
    min_score: int = 150
    top_n_stories: int = 10
    # Stored as CSV strings — pydantic-settings v2 JSON-parses list[str] from dotenv,
    # which breaks comma-separated values. Use .keyword_list / .schedule_time_list instead.
    keywords: str = "kubernetes,MCP,AI agents,GKE,agentic,LLM,open source AI,Claude"
    schedule_times: str = "08:00,17:00"

    # Alerting
    alert_channel: Optional[str] = None  # "slack", "ntfy", or "sms"; falls back to first available

    # Slack
    slack_webhook_url: Optional[str] = None

    # Ntfy
    ntfy_topic: Optional[str] = None
    ntfy_base_url: str = "https://ntfy.sh"
    ntfy_priority: int = 3  # 1=min 2=low 3=default 4=high 5=urgent

    # Twilio SMS
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    twilio_to_number: Optional[str] = None

    @property
    def keyword_list(self) -> list[str]:
        return [k.strip() for k in self.keywords.split(",") if k.strip()]

    @property
    def schedule_time_list(self) -> list[str]:
        return [t.strip() for t in self.schedule_times.split(",") if t.strip()]

    @property
    def enabled_deliverers(self) -> list[str]:
        channels = []
        if self.slack_webhook_url:
            channels.append("slack")
        if self.ntfy_topic:
            channels.append("ntfy")
        if all([self.twilio_account_sid, self.twilio_auth_token, self.twilio_from_number, self.twilio_to_number]):
            channels.append("sms")
        return channels
