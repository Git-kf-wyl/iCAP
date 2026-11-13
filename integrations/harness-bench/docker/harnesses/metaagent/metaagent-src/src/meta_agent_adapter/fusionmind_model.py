"""Native OpenJiuwen Model Client over the explicit platform transport seam."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from openjiuwen.core.foundation.llm import AssistantMessage, BaseModelClient
from openjiuwen.core.foundation.llm.schema.message_chunk import AssistantMessageChunk
from pydantic import ValidationError

from meta_agent.errors import BootError, MetaAgentError, UnsupportedCapabilityError
from meta_agent_adapter.inference import (
    InferenceRequest,
    current_inference_context,
    get_inference_transport,
)


class FusionMindModelClient(BaseModelClient):  # type: ignore[misc]
    """Import before package loading to register client_provider: FusionMind."""

    __client_name__ = "FusionMind"

    def _validate_config(self) -> None:
        # UDS credentials and discovery belong to the transport, not a pretend
        # HTTP api_base/api_key. BaseModelClient explicitly permits this override.
        name = getattr(self.model_client_config, "transport_name", "fusionmind")
        if not isinstance(name, str) or not name.strip():
            raise BootError("META_PLATFORM_BINDING", "transport_name must be a nonempty string")
        self.transport = get_inference_transport(name)

    def _request(self, messages: Any, *, stream: bool, **kwargs: Any) -> InferenceRequest:
        timeout = kwargs.pop("timeout", None)
        payload = self._build_request_params(
            messages=messages,
            tools=kwargs.pop("tools", None),
            temperature=kwargs.pop("temperature", None),
            top_p=kwargs.pop("top_p", None),
            model=kwargs.pop("model", None),
            stop=kwargs.pop("stop", None),
            max_tokens=kwargs.pop("max_tokens", None),
            stream=stream,
            **kwargs,
        )
        return InferenceRequest(
            call_id=uuid4().hex,
            payload=payload,
            timeout_s=timeout if timeout is not None else self.model_client_config.timeout,
            context=current_inference_context(),
        )

    @staticmethod
    def _reply(data: Any, *, stream: bool) -> Any:
        try:
            if not isinstance(data, dict) or not (
                {"content", "tool_calls", "usage_metadata", "finish_reason"} & data.keys()
            ):
                raise ValueError("Expected a normalized native reply")
            if data.get("role", "assistant") != "assistant":
                raise ValueError("Expected an assistant reply")
            model = AssistantMessageChunk if stream else AssistantMessage
            return model.model_validate(data)
        except (ValueError, ValidationError) as error:
            raise MetaAgentError(
                "META_PLATFORM_RESPONSE", "Transport must return normalized AssistantMessage fields"
            ) from error

    async def invoke(self, messages: Any, **kwargs: Any) -> Any:
        request = self._request(messages, stream=False, **kwargs)
        try:
            reply = await self.transport.invoke(request)
        except MetaAgentError:
            raise
        except Exception as error:
            raise MetaAgentError("META_PLATFORM_INFERENCE", "Platform inference failed") from error
        return self._reply(reply, stream=False)

    async def stream(self, messages: Any, **kwargs: Any) -> AsyncIterator[Any]:
        request = self._request(messages, stream=True, **kwargs)
        iterator = None
        try:
            iterator = self.transport.stream(request)
            async for reply in iterator:
                yield self._reply(reply, stream=True)
        except MetaAgentError:
            raise
        except Exception as error:
            raise MetaAgentError("META_PLATFORM_INFERENCE", "Platform streaming failed") from error
        finally:
            close = getattr(iterator, "aclose", None)
            if close is not None:
                await close()

    async def generate_image(self, *args: Any, **kwargs: Any) -> Any:
        raise UnsupportedCapabilityError(
            "META_PLATFORM_MEDIA_UNSUPPORTED", "Image generation is not bound"
        )

    async def generate_speech(self, *args: Any, **kwargs: Any) -> Any:
        raise UnsupportedCapabilityError(
            "META_PLATFORM_MEDIA_UNSUPPORTED", "Speech generation is not bound"
        )

    async def generate_video(self, *args: Any, **kwargs: Any) -> Any:
        raise UnsupportedCapabilityError(
            "META_PLATFORM_MEDIA_UNSUPPORTED", "Video generation is not bound"
        )
