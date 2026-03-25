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
    min_score: int = 10
    top_n_stories: int = 10
    # Stored as CSV strings — pydantic-settings v2 JSON-parses list[str] from dotenv,
    # which breaks comma-separated values. Use .keyword_list / .schedule_time_list instead.
    keywords: str = "kubernetes,MCP,model context protocol,AI agents,GKE,agentic,LLM,open source AI,Claude"
    schedule_times: str = "08:00,17:00"

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

    # Error alerting — channel to use for failure notifications (ntfy, slack, sms)
    # If unset, falls back to the first available configured channel.
    alert_channel: Optional[str] = None

    # Email delivery (opt-in) — requires EMAIL_TO + EMAIL_FROM + one transport
    email_to: Optional[str] = None
    email_from: Optional[str] = None
    sendgrid_api_key: Optional[str] = None  # SendGrid REST transport
    smtp_host: Optional[str] = None          # SMTP transport (alternative to SendGrid)
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None

    # LLM provider fallback — tried automatically if the primary provider fails
    fallback_provider: Optional[str] = None

    # Gemini model fallback chain — tried in order on transient errors before escalating to fallback_provider
    gemini_models: str = "gemini-3-flash-preview,gemini-2.5-pro,gemini-2.5-flash"

    # Include HN discussion thread URL alongside article URL in briefs (opt-in)
    include_hn_discussion: bool = False

    # Additional sources
    enable_ai_tracker: bool = False
    enable_stocks: bool = False
    stock_tickers: str = "NVDA,MSFT,GOOGL,AAPL,META"
    stock_move_threshold: float = 3.0
    ai_tracker_hours_back: int = 24
    ai_tracker_extra_feeds: str = ""  # CSV of "name=url" pairs

    # Cross-run deduplication
    dedup_window_days: int = 7
    seen_stories_path: str = "data/seen_stories.json"

    # Run history
    history_path: str = "data/runs.jsonl"
    history_retention_days: int = 30

    @property
    def gemini_model_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]

    @property
    def stock_ticker_list(self) -> list[str]:
        return [t.strip().upper() for t in self.stock_tickers.split(",") if t.strip()]

    @property
    def ai_tracker_extra_feed_list(self) -> list[tuple[str, str]]:
        """Parse ``"Name=url,Name2=url2"`` into ``[(name, url), ...]``."""
        result = []
        for item in self.ai_tracker_extra_feeds.split(","):
            item = item.strip()
            if "=" in item:
                name, _, url = item.partition("=")
                if name.strip() and url.strip():
                    result.append((name.strip(), url.strip()))
        return result

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
