import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL",
            "sqlite:///./vidio_agent.db",
        )
        self.OTP_EXPIRY_MINUTES: int = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))
        self.SMTP_HOST: str = os.getenv("SMTP_HOST", "")
        self.SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
        self.SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
        self.SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
        self.SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Vidio")
        self.SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"
        self.SMTP_TIMEOUT_SECONDS: int = int(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))


settings = Settings()
