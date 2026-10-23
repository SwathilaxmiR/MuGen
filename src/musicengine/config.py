"""All runtime settings come from the environment (see .env.example)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://music:music@localhost:5432/music"

    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "music"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    presign_ttl_s: int = 86400

    api_token: str = ""  # empty = auth disabled (local dev only)
    rate_limit_per_min: int = 30
    max_queue: int = 50

    worker_concurrency: int = 2
    job_timeout_s: int = 900
    max_attempts: int = 3
    heartbeat_stale_s: int = 60
    poll_interval_s: float = 0.5

    renderer: str = "fluidsynth"  # fluidsynth | numpy | mock
    renderer_fallback: str = "numpy"
    fluidsynth_bin: str = "fluidsynth"
    fluidsynth_timeout_s: int = 120
    soundfont_path: str = "/opt/soundfonts/FluidR3_GM.sf2"
    ffmpeg_bin: str = "ffmpeg"

    interpreter: str = "rules"  # rules | llm | mock
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-5-5"
    llm_api_key: str = ""
    llm_timeout_s: float = 15.0

    callback_secret: str = "change-me"
    callback_timeout_s: float = 5.0

    min_section_gap_s: float = 1.5
    min_duration_s: float = 5.0
    max_duration_s: float = 300.0
    target_lufs_default: float = -16.0
    tp_ceiling_dbtp: float = -1.5
    lufs_tol: float = 0.5
    duck_db: float = 12.0
    duck_attack_ms: float = 120.0
    duck_release_ms: float = 500.0
    duck_bridge_gap_s: float = 0.6
    max_narration_mb: int = 50
    narration_fetch_timeout_s: float = 20.0
    allow_private_urls: bool = False  # SSRF guard for narration_url / callback_url; tests only

    cost_per_cpu_second: float = 0.0000134  # override with your server's $/vCPU-second
    fault_inject: str = ""  # test only: render_primary_fail | render_timeout | llm_fail
    log_level: str = "INFO"
    web_dist_dir: str = ""  # built web UI to serve at /; default <repo>/web/dist when it exists


@lru_cache
def get_settings() -> Settings:
    return Settings()
