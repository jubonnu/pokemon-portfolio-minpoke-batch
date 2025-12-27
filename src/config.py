"""設定ファイル"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """アプリケーション設定"""

    # Supabase Settings
    supabase_url: str = Field(..., description="SupabaseプロジェクトURL")
    supabase_key: str = Field(..., description="Supabase Anon Key")

    # API Settings
    base_url: str = Field(
        default="https://pokeca-chart.com", description="ベースURL"
    )
    wp_api_url: str = Field(
        default="https://pokeca-chart.com/wp-json/wp/v2",
        description="WordPress REST API URL",
    )

    # Scraping Settings
    concurrent_requests: int = Field(
        default=10, description="同時リクエスト数"
    )
    request_delay: float = Field(
        default=0.1, description="リクエスト間の遅延（秒）"
    )
    batch_size: int = Field(
        default=100, description="DBバッチ挿入サイズ"
    )
    wp_per_page: int = Field(
        default=100, description="WordPress APIのper_page"
    )

    # Retry Settings
    max_retries: int = Field(default=3, description="最大リトライ回数")
    retry_delay: float = Field(default=1.0, description="リトライ遅延（秒）")

    # Timeout
    request_timeout: int = Field(default=30, description="リクエストタイムアウト（秒）")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

