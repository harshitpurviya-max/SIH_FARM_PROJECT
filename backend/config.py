from datetime import date
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str 
    redis_url: str = "redis://localhost:6379/0"
    auth_secret: str = "change-me-in-production"
    sms_mode: str = "demo"
    sms_provider: str = "mock"
    eta_fallback_minutes: int = 15
    demo_price_per_tonne: Decimal = Decimal("1000.00")
    demo_start_date: date = date(2026, 9, 5)
    demo_end_date: date = date(2026, 9, 17)
    max_booking_quintals: Decimal = Decimal("200.000")
    demo_crop_msp: dict[str, Decimal] = Field(
        default_factory=lambda: {
            "Wheat": Decimal("2585"),
            "Maize": Decimal("2410"),
            "Moong": Decimal("8780"),
            "Gram": Decimal("5875"),
            "Masur": Decimal("7000"),
            "Mustard": Decimal("6200"),
            "Soybean": Decimal("4300"),
            "Rice": Decimal("2300"),
            "Cotton": Decimal("6500"),
        }
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @staticmethod
    def crop_msp(crop_name: str | None) -> Decimal:
        if not crop_name:
            return Decimal("0")
        return Settings().demo_crop_msp.get(crop_name.strip().title(), Decimal("0"))


settings = Settings()
