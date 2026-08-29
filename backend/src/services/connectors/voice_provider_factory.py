from .base_connector import BaseVoiceConnector
from .retell_voice_connector import RetellVoiceConnector
from ...core.config import settings

class VoiceProviderFactory:
    @staticmethod
    def get_provider(provider_name: str = None) -> BaseVoiceConnector:
        """
        Instantiates and returns the correct Voice provider connector.
        Defaults to Retell but is ready for dynamic expansion (e.g. Vapi).
        """
        if provider_name is None:
            # Fallback to settings or environment variable
            provider_name = getattr(settings, "VOICE_PROVIDER", "retell").lower()
            
        if provider_name == "retell":
            return RetellVoiceConnector()
        else:
            # Fallback/Default provider
            return RetellVoiceConnector()
