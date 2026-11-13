"""InferSchedule's OpenAI-compatible contract, using the native SDK client."""

from collections.abc import AsyncIterator
from typing import Any

from openjiuwen.core.foundation.llm import ModelClientConfig
from openjiuwen.core.foundation.llm.model_clients.openai_model_client import OpenAIModelClient

from meta_agent.errors import MetaAgentError
from meta_agent.spec.platform import InferScheduleConfig


def platform_error(error: Exception) -> MetaAgentError:
    current: BaseException | None = error
    seen: set[int] = set()
    code = "META_PLATFORM_INFERENCE"
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        status = getattr(current, "status_code", None)
        if status in {401, 403}:
            code = "META_PLATFORM_AUTH"
            break
        if status == 429:
            code = "META_PLATFORM_RATE_LIMIT"
            break
        if isinstance(status, int) and status >= 500:
            code = "META_PLATFORM_UNAVAILABLE"
            break
        if "Timeout" in type(current).__name__:
            code = "META_PLATFORM_TIMEOUT"
            break
        current = current.__cause__ or current.__context__
    return MetaAgentError(code, "InferSchedule request failed")


class InferScheduleClient(OpenAIModelClient):  # type: ignore[misc]
    """Only normalize failures; chat, SSE, authentication and usage stay native."""

    __client_name__ = "MetaInferSchedule"

    async def invoke(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return await super().invoke(*args, **kwargs)
        except Exception as error:
            raise platform_error(error) from error

    async def stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        try:
            async for chunk in super().stream(*args, **kwargs):
                yield chunk
        except Exception as error:
            raise platform_error(error) from error


class InferScheduleModelAdapter:
    def __init__(self, config: InferScheduleConfig) -> None:
        self.config = config

    def configure(self, model: Any) -> Any:
        model = model.model_copy(deep=True)
        endpoint = self.config.endpoint
        model.model_client_config = ModelClientConfig(
            client_provider=InferScheduleClient.__client_name__,
            api_base=endpoint if endpoint.endswith("/v1") else endpoint + "/v1",
            api_key=self.config.api_key,
            timeout=self.config.timeout,
            stream_first_chunk_timeout=self.config.timeout,
            stream_idle_timeout=self.config.timeout,
        )
        return model

    def get_model(self, model: Any) -> Any:
        return self.configure(model).build()
