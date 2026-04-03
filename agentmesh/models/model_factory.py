import os
from typing import Optional, Dict, Any

from agentmesh.common import config
from agentmesh.common.enums import ModelProvider, ModelApiBase
from agentmesh.models.llm.base_model import LLMModel
from agentmesh.models.llm.claude_model import ClaudeModel
from agentmesh.models.llm.deepseek_model import DeepSeekModel
from agentmesh.models.llm.openai_model import OpenAIModel


class ModelFactory:
    @staticmethod
    def _provider_env_prefix(provider: str) -> str:
        return str(provider or "").strip().replace("-", "_").upper()

    def _resolve_api_credentials(
        self,
        provider: str,
        model_config: Dict[str, Any],
        api_base: Optional[str],
        api_key: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Resolve api_base/api_key from explicit args -> env -> config.
        Also supports legacy aliases: baseUrl/apiKey.
        """
        provider_env = self._provider_env_prefix(provider)

        env_api_base = (
            os.environ.get(f"{provider_env}_API_BASE")
            or os.environ.get(f"{provider_env}_BASE_URL")
        )
        env_api_key = os.environ.get(f"{provider_env}_API_KEY")

        # Keep OpenAI env vars as a generic fallback for OpenAI-compatible providers.
        if not env_api_base:
            env_api_base = os.environ.get("OPENAI_API_BASE")
        if not env_api_key:
            env_api_key = os.environ.get("OPENAI_API_KEY")

        resolved_api_base = (
            api_base
            or env_api_base
            or model_config.get("api_base")
            or model_config.get("baseUrl")
        )
        resolved_api_key = (
            api_key
            or env_api_key
            or model_config.get("api_key")
            or model_config.get("apiKey")
        )
        return resolved_api_base, resolved_api_key

    def _determine_model_provider(self, model_name: str, model_provider: Optional[str] = None) -> str:
        """
        Determine the appropriate model provider based on model name and configuration.

        :param model_name: The name of the model.
        :param model_provider: Optional explicitly specified provider.
        :return: The determined model provider.
        """
        # If provider is explicitly specified, use it
        if model_provider:
            return model_provider

        # Get models configuration
        models_config = config().get("models", {})

        # Strategy 1: Check if model is listed in any provider's models list
        for provider, provider_config in models_config.items():
            provider_models = provider_config.get("models", [])
            if model_name in provider_models:
                return provider

        # Strategy 2: Determine provider based on model name prefix
        if model_name.startswith(("gpt", "text-davinci", "o1")):
            return ModelProvider.OPENAI.value
        elif model_name.startswith("claude"):
            return ModelProvider.CLAUDE.value
        elif model_name.startswith("deepseek"):
            return ModelProvider.DEEPSEEK.value
        elif model_name.startswith(("qwen", "qwq")):
            return ModelProvider.QWEN.value
        # Strategy 3: Default to openai if no match
        return ModelProvider.COMMON.value

    def get_model(self, model_name: str, model_provider: Optional[str] = None,
                  api_base: Optional[str] = None, api_key: Optional[str] = None) -> LLMModel:
        """
        Factory function to get the model instance based on the model name.

        :param model_name: The name of the model to instantiate.
        :param model_provider: Optional provider of the model (will be auto-determined if not provided).
        :param api_base: Optional API base URL. If not provided, will be loaded from config.
        :param api_key: Optional API key. If not provided, will be loaded from config.
        :return: An instance of the corresponding model.
        """
        provider = self._determine_model_provider(model_name, model_provider)

        # If api_base and api_key are not provided, load from config
        if not api_base or not api_key:
            model_config = config().get("models", {}).get(provider, {})
            api_base, api_key = self._resolve_api_credentials(
                provider=provider,
                model_config=model_config if isinstance(model_config, dict) else {},
                api_base=api_base,
                api_key=api_key,
            )

        if provider == ModelProvider.OPENAI.value:
            return OpenAIModel(model=model_name, api_base=api_base, api_key=api_key)
        elif provider == ModelProvider.CLAUDE.value:
            if not api_base or api_base == ModelApiBase.CLAUDE.value:
                return ClaudeModel(model=model_name, api_base=api_base, api_key=api_key)
            else:
                return LLMModel(model=model_name, api_base=api_base, api_key=api_key)
        elif provider == ModelProvider.DEEPSEEK.value:
            return DeepSeekModel(model=model_name, api_base=api_base, api_key=api_key)
        else:
            # Default to base LLMModel if provider is not recognized
            return LLMModel(model=model_name, api_base=api_base, api_key=api_key)
