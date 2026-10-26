from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    frontend_origin: str = "http://localhost:5173"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    admin_email: str = ""
    song_credit_price_pkr: int = 50
    training_credit_price_pkr: int = 150
    song_credit_price_usd: float = 0.50
    training_credit_price_usd: float = 1.00
    easypaisa_account_title: str = ""
    easypaisa_account_number: str = ""
    jazzcash_account_title: str = ""
    jazzcash_account_number: str = ""
    hbl_account_title: str = ""
    hbl_account_number: str = ""
    nayapay_account_title: str = ""
    nayapay_account_number: str = ""
    worker_prepare_url: str = ""
    worker_convert_url: str = ""
    worker_mix_url: str = ""
    worker_shared_secret: str = ""
    worker_model_probe_url: str = ""
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    environment: str = "development"
    estimated_gpu_cost_usd_per_song: float = 0.08
    max_request_bytes: int = 275_000_000

settings = Settings()
