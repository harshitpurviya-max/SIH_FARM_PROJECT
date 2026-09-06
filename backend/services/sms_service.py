import logging
from abc import ABC, abstractmethod

from ..config import settings

logger = logging.getLogger(__name__)


class SMSService(ABC):
    @abstractmethod
    def send_sms(self, phone_number: str, message: str) -> str:
        """Return a delivery status without coupling procurement to a provider."""


class DemoSMSService(SMSService):
    def send_sms(self, phone_number: str, message: str) -> str:
        logger.info("DEMO SMS to %s: %s", phone_number, message)
        return "DEMO_SENT"


class ProviderSMSService(SMSService):
    def send_sms(self, phone_number: str, message: str) -> str:
        raise RuntimeError(f"SMS provider '{settings.sms_provider}' is not configured")


def get_sms_service() -> SMSService:
    return DemoSMSService() if settings.sms_mode.lower() == "demo" else ProviderSMSService()