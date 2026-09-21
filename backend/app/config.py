from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RoundSense"
    database_url: str = "sqlite:///./roundsense.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    model_path: str = "models/round_win_model.joblib"
    history_limit: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
