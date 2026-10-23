"""Creative generation Tools exposed through the shared Agent Runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
from typing import Any

from agents.agent_harness import StaticToolSource, ToolBinding
from agents.agent_harness.core.interfaces import (
    ReplayPolicy,
    RiskLevel,
    ToolDefinition,
    ToolEffect,
    ToolResult,
    ToolSchema,
)
from agents.agent_harness.core.security import redact_sensitive_text
from agents.tools.creative_media.contracts import CreativeAssetStore
from agents.tools.creative_media.agnes_client import (
    AgnesMediaClient,
    MediaProviderError,
)


_IMAGE_PERMISSION = "creative.generate"
_READ_PERMISSION = "ads.read"
_MAX_PROMPT_CHARS = 4000
_MAX_ASSET_NAME_CHARS = 120
_IMAGE_ASPECT_RATIOS = (
    "1:1", "4:3", "3:2", "16:9", "9:16", "2:3", "3:4", "21:9",
)
_VIDEO_ASPECT_RATIOS = ("16:9", "9:16", "1:1")


@dataclass(frozen=True)
class _CreativeToolSpec:
    name: str
    description: str
    action: str
    resource_type: str
    intent_types: tuple[str, ...]
    intent_aliases: tuple[str, ...]
    schema: ToolSchema
    permission: str
    timeout_seconds: int
    effect: ToolEffect = ToolEffect.INTERNAL_WRITE
    risk: RiskLevel = RiskLevel.MEDIUM
    replay: ReplayPolicy = ReplayPolicy.UNSAFE


@dataclass(frozen=True)
class _CreativeDependencies:
    configuration_provider: Callable[[str], Mapping[str, Any]]
    asset_store: CreativeAssetStore
    permission: str
    read_permission: str
    client_factory: Callable[[Mapping[str, Any]], Any]


@dataclass(frozen=True)
class _ImageRequest:
    prompt: str
    size: str
    aspect_ratio: str
    name: str


@dataclass(frozen=True)
class _VideoRequest:
    prompt: str
    aspect_ratio: str
    duration_seconds: int
    resolution: str
    name: str


@dataclass(frozen=True)
class _GeneratedImage:
    content: bytes
    media_type: str
    extension: str


class _InvalidGeneratedImage(ValueError):
    """The provider returned an unexpected image payload."""


class _CreativeGenerationExecutor:
    def __init__(
        self,
        purpose: str,
        configuration_provider: Callable[[str], Mapping[str, Any]],
        asset_store: Any,
        client_factory: Callable[[Mapping[str, Any]], Any],
    ) -> None:
        self.purpose = purpose
        self.configuration_provider = configuration_provider
        self.asset_store = asset_store
        self.client_factory = client_factory

    def execute(self, context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            tenant_id, user_id = _trusted_scope(context)
            configuration = self.configuration_provider(self.purpose)
            client = self.client_factory(configuration)
        except PermissionError as error:
            return ToolResult.error(str(error))
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ToolResult.error(
                _model_setup_message(self.purpose)
            )
        if self.purpose == "image_generation":
            return self._generate_image(
                client,
                arguments,
                configuration=configuration,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        return self._submit_video(
            client,
            arguments,
            configuration=configuration,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    def _generate_image(
        self,
        client: Any,
        arguments: Mapping[str, Any],
        *,
        configuration: Mapping[str, Any],
        tenant_id: str,
        user_id: str,
    ) -> ToolResult:
        try:
            request = _image_request(arguments)
            output = _single_generated_image(
                client.generate_image(
                    request.prompt,
                    request.size,
                    request.aspect_ratio,
                ),
            )
            row = self.asset_store.put(
                output.content,
                filename=(
                    f"{_filename_stem(request.name)}.{output.extension}"
                ),
                media_type=output.media_type,
                tenant_id=tenant_id,
                user_id=user_id,
                metadata=_image_metadata(request, configuration),
            )
        except MediaProviderError as error:
            return ToolResult.error(_generation_error_message(error.code))
        except _InvalidGeneratedImage:
            return ToolResult.error("图片模型返回了无效或不支持的素材格式。")
        except ValueError:
            return ToolResult.error("图片提示词、尺寸或比例无效，请调整后重试。")
        except OSError:
            return ToolResult.error("图片生成失败或素材无法安全保存，请检查模型配置后重试。")
        return ToolResult.ok({
            "asset_id": row["asset_id"],
            "status": "ready",
            "image_assets": [_image_result(row, request.name, output.media_type)],
        })

    def _submit_video(
        self,
        client: Any,
        arguments: Mapping[str, Any],
        *,
        configuration: Mapping[str, Any],
        tenant_id: str,
        user_id: str,
    ) -> ToolResult:
        try:
            request = _video_request(arguments)
        except ValueError:
            return ToolResult.error("视频提示词、时长、尺寸或比例无效，请调整后重试。")
        try:
            pending = self._create_pending_video(
                request,
                configuration,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except (OSError, ValueError):
            return ToolResult.error("无法在素材库中登记视频任务，请稍后重试。")
        try:
            job = client.submit_video(
                request.prompt,
                aspect_ratio=request.aspect_ratio,
                duration_seconds=request.duration_seconds,
                resolution=request.resolution,
            )
        except MediaProviderError as error:
            return self._mark_submit_failed(
                pending, error.code, tenant_id, user_id,
            )
        except (KeyError, OSError, TypeError, ValueError):
            return self._mark_submit_failed(
                pending, "video_job_invalid", tenant_id, user_id,
            )
        return self._record_video_submission(
            job,
            pending,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    def _record_video_submission(
        self,
        job: Mapping[str, Any],
        pending: Mapping[str, Any],
        *,
        tenant_id: str,
        user_id: str,
    ) -> ToolResult:
        if str(job.get("status") or "processing") == "failed":
            try:
                self._update_video_status(
                    pending,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    metadata={"status": "failed", "error_code": "video_job_failed"},
                )
            except (KeyError, OSError, TypeError, ValueError):
                return self._mark_submit_failed(
                    pending, "video_job_failed", tenant_id, user_id,
                )
            return ToolResult.error("视频模型未能创建任务，请检查提示词与模型配置。")
        try:
            self._update_video_status(
                pending,
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={
                    "status": "processing",
                    "provider_job_id": str(job["video_id"]),
                },
            )
        except (KeyError, OSError, TypeError, ValueError):
            return self._mark_submit_failed(
                pending, "video_job_invalid", tenant_id, user_id,
            )
        return ToolResult.ok({
            "asset_id": pending["asset_id"],
            "status": "processing",
            "message": "视频生成任务已提交。完成后可查询该素材，任务期间不会重复创建。",
        })

    def _create_pending_video(
        self,
        request: _VideoRequest,
        configuration: Mapping[str, Any],
        *,
        tenant_id: str,
        user_id: str,
    ) -> Mapping[str, Any]:
        return self.asset_store.create_pending(
            filename=f"{_filename_stem(request.name)}.mp4",
            media_type="video/mp4",
            tenant_id=tenant_id,
            user_id=user_id,
            metadata=_video_metadata(request, configuration),
        )

    def _update_video_status(
        self,
        pending: Mapping[str, Any],
        *,
        tenant_id: str,
        user_id: str,
        metadata: Mapping[str, Any],
    ) -> None:
        self.asset_store.update(
            pending["asset_id"],
            tenant_id=tenant_id,
            user_id=user_id,
            metadata=metadata,
        )

    def _mark_submit_failed(
        self,
        pending: Any,
        error_code: str,
        tenant_id: str,
        user_id: str,
    ) -> ToolResult:
        if isinstance(pending, Mapping) and pending.get("asset_id"):
            try:
                self.asset_store.update(
                    pending["asset_id"],
                    tenant_id=tenant_id,
                    user_id=user_id,
                    metadata={
                        "status": "failed",
                        "error_code": _safe_error_code(error_code),
                    },
                )
            except (KeyError, OSError, TypeError, ValueError):
                return ToolResult.error(
                    "视频提交失败，且任务状态无法写入素材库；请先检查素材库状态，再决定是否重试。",
                )
        return ToolResult.error(_generation_error_message(error_code))


class _CheckVideoExecutor:
    def __init__(
        self,
        configuration_provider: Callable[[str], Mapping[str, Any]],
        asset_store: Any,
        client_factory: Callable[[Mapping[str, Any]], Any],
    ) -> None:
        self.configuration_provider = configuration_provider
        self.asset_store = asset_store
        self.client_factory = client_factory

    def execute(self, context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            tenant_id, user_id = _trusted_scope(context)
            asset = self.asset_store.get(
                arguments.get("asset_id"),
                tenant_id=tenant_id,
                user_id=user_id,
                include_content=False,
            )
        except PermissionError as error:
            return ToolResult.error(str(error))
        except FileNotFoundError:
            return ToolResult.error("该创意素材不存在或无权访问。")
        return self._resolve_asset(asset, tenant_id=tenant_id, user_id=user_id)

    def _resolve_asset(
        self,
        asset: Any,
        *,
        tenant_id: str,
        user_id: str,
    ) -> ToolResult:
        if asset.metadata.get("kind") != "video":
            return ToolResult.error("指定素材不是视频生成任务。")
        status = str(asset.metadata.get("status") or "")
        if status == "ready":
            return ToolResult.ok(_video_result(asset.metadata))
        if status == "failed":
            return ToolResult.error(_generation_error_message(
                str(asset.metadata.get("error_code") or "video_job_failed"),
            ))
        provider_job_id = str(asset.metadata.get("provider_job_id") or "")
        if not provider_job_id:
            return ToolResult.error("视频任务尚未获得上游任务编号，请稍后重试查询。")
        result = self._poll_video(asset, provider_job_id)
        return self._save_poll_result(
            asset,
            result,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    def _poll_video(
        self,
        asset: Any,
        provider_job_id: str,
    ) -> Mapping[str, Any] | ToolResult:
        try:
            configuration = self.configuration_provider("video_generation")
            if (
                _safe_model_name(configuration) != str(asset.metadata.get("model") or "")
                or _model_endpoint_hash(configuration)
                != str(asset.metadata.get("model_endpoint_hash") or "")
            ):
                return ToolResult.error(
                    "当前视频模型与任务创建时不同，请先切回原视频模型再查询。"
                )
            client = self.client_factory(configuration)
            return client.poll_video(provider_job_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return ToolResult.error("视频任务查询失败，请检查视频模型配置后重试。")

    def _save_poll_result(
        self,
        asset: Any,
        result: Mapping[str, Any] | ToolResult,
        *,
        tenant_id: str,
        user_id: str,
    ) -> ToolResult:
        if isinstance(result, ToolResult):
            return result
        result_status = str(result.get("status") or "")
        if result_status == "processing":
            return ToolResult.ok({
                "asset_id": asset.metadata["asset_id"],
                "status": "processing",
                "message": "视频仍在生成中，可稍后再次查询。",
            })
        if result_status != "completed":
            return self._save_failed_status(
                asset,
                result,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        return self._save_completed_video(
            asset,
            result,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    def _save_failed_status(
        self,
        asset: Any,
        result: Mapping[str, Any],
        *,
        tenant_id: str,
        user_id: str,
    ) -> ToolResult:
        error_code = _safe_error_code(str(result.get("error") or "video_job_failed"))
        try:
            self.asset_store.update(
                asset.metadata["asset_id"],
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={"status": "failed", "error_code": error_code},
            )
        except (KeyError, OSError, TypeError, ValueError):
            return ToolResult.error("视频失败状态暂时无法保存，请稍后重试查询。")
        return ToolResult.error(_generation_error_message(error_code))

    def _save_completed_video(
        self,
        asset: Any,
        result: Mapping[str, Any],
        *,
        tenant_id: str,
        user_id: str,
    ) -> ToolResult:
        try:
            completed = self.asset_store.complete(
                asset.metadata["asset_id"],
                result["content"],
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={"status": "ready"},
            )
        except (KeyError, OSError, TypeError, ValueError):
            return ToolResult.error("视频已生成，但素材保存失败，请稍后重试查询。")
        return ToolResult.ok(_video_result(completed))


class _ListAssetsExecutor:
    def __init__(self, asset_store: Any) -> None:
        self.asset_store = asset_store

    def execute(self, context: Any, arguments: dict[str, Any]) -> ToolResult:
        try:
            tenant_id, user_id = _trusted_scope(context)
            rows = self.asset_store.list(
                tenant_id=tenant_id,
                user_id=user_id,
                limit=int(arguments.get("limit", 20)),
            )
        except PermissionError as error:
            return ToolResult.error(str(error))
        except (ValueError, OSError):
            return ToolResult.error("创意素材库暂时无法读取。")
        safe_rows = [
            _asset_result(item)
            for item in rows
            if isinstance(item, Mapping)
        ]
        safe_rows = [item for item in safe_rows if item]
        return ToolResult.ok({
            "count": len(safe_rows),
            "assets": safe_rows,
            "image_assets": [
                item for item in safe_rows
                if item["kind"] == "image" and item["status"] == "ready"
            ],
            "video_assets": [
                item for item in safe_rows
                if item["kind"] == "video" and item["status"] == "ready"
            ],
            "data_status": "local",
        })


def creative_media_tool_source(
    *,
    configuration_provider: Callable[[str], Mapping[str, Any]],
    asset_store: CreativeAssetStore,
    required_permission: str = _IMAGE_PERMISSION,
    read_permission: str = _READ_PERMISSION,
    client_factory: Callable[[Mapping[str, Any]], Any] = AgnesMediaClient,
) -> StaticToolSource:
    """Create the trusted image/video Tool Source for the single Agent Runtime."""
    if not callable(configuration_provider):
        raise TypeError("configuration_provider must be callable")
    if asset_store is None:
        raise TypeError("asset_store is required")
    permission = str(required_permission or "").strip()
    read_permission = str(read_permission or "").strip()
    if not permission or not read_permission:
        raise ValueError("creative Tool permissions are required")
    dependencies = _CreativeDependencies(
        configuration_provider=configuration_provider,
        asset_store=asset_store,
        permission=permission,
        read_permission=read_permission,
        client_factory=client_factory,
    )
    bindings = [
        _image_binding(dependencies),
        _video_binding(dependencies),
        _video_check_binding(dependencies),
        _asset_list_binding(dependencies),
    ]
    return StaticToolSource("advertising:creative-media", bindings)


def _image_binding(dependencies: _CreativeDependencies) -> ToolBinding:
    spec = _CreativeToolSpec(
        name="creative_generate_image",
        description=(
            "按用户明确要求生成一张广告图片并保存到当前用户的创意素材库。"
            "先依据 creative-production Skill 写出具体、可执行且不含虚假产品主张的提示词；"
            "用户未提供产品事实时只使用抽象场景，不添加功效、价格、证言或品牌标识。"
        ),
        action="generate",
        resource_type="creative_image",
        intent_types=("creative_generate",),
        intent_aliases=(
            "生成广告图片", "制作广告图片", "做一张创意图", "生成图片素材",
            "生成产品广告图", "帮我生成图片", "生成图片", "图片",
            "画个图", "画一张图", "绘制图片",
            "create an ad image", "generate a creative image",
        ),
        schema=_image_schema(),
        permission=dependencies.permission,
        timeout_seconds=500,
    )
    return _generation_binding("image_generation", spec, dependencies)


def _video_binding(dependencies: _CreativeDependencies) -> ToolBinding:
    spec = _CreativeToolSpec(
        name="creative_submit_video",
        description=(
            "按用户明确要求提交一条广告视频生成任务，立即返回持久化 asset_id；"
            "生成是异步的，必须稍后用 creative_check_video 查询状态，不得重复提交任务。"
        ),
        action="generate",
        resource_type="creative_video",
        intent_types=("creative_generate",),
        intent_aliases=(
            "生成广告视频", "制作广告视频", "做一个创意视频", "生成视频素材",
            "帮我生成视频", "生成视频", "视频",
            "create an ad video", "generate a creative video",
        ),
        schema=_video_schema(),
        permission=dependencies.permission,
        timeout_seconds=500,
    )
    return _generation_binding("video_generation", spec, dependencies)


def _video_check_binding(dependencies: _CreativeDependencies) -> ToolBinding:
    spec = _CreativeToolSpec(
        name="creative_check_video",
        description=(
            "查询当前用户自己的视频生成任务状态；processing 时返回 asset_id，"
            "completed 时保存视频并返回可播放素材。只接受素材库中的 asset_id。"
        ),
        action="check",
        resource_type="creative_video_job",
        intent_types=("creative_video_status",),
        intent_aliases=(
            "查询视频生成进度", "检查视频任务", "视频生成好了没",
            "查询创意视频状态", "check video generation status",
        ),
        schema=ToolSchema(
            properties={
                "asset_id": {
                    "type": "string",
                    "minLength": 32,
                    "maxLength": 32,
                    "description": "视频生成任务对应的创意素材 ID",
                },
            },
            required=["asset_id"],
            additional_properties=False,
        ),
        permission=dependencies.permission,
        timeout_seconds=500,
    )
    definition = _definition(spec)
    executor = _CheckVideoExecutor(
        dependencies.configuration_provider,
        dependencies.asset_store,
        dependencies.client_factory,
    )
    return ToolBinding(definition, executor)


def _asset_list_binding(dependencies: _CreativeDependencies) -> ToolBinding:
    spec = _CreativeToolSpec(
        name="creative_list_assets",
        description="查询当前可信身份拥有的广告创意素材，不查询其他用户或租户。",
        action="list",
        resource_type="creative_asset",
        intent_types=("creative_asset_list",),
        intent_aliases=(
            "查询创意素材", "查看生成的图片", "查看生成的视频",
            "列出我的创意", "list my creative assets",
        ),
        schema=ToolSchema(
            properties={
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 20,
                    "description": "最多返回的素材数量",
                },
            },
            additional_properties=False,
        ),
        permission=dependencies.read_permission,
        timeout_seconds=15,
        effect=ToolEffect.READ,
        risk=RiskLevel.LOW,
        replay=ReplayPolicy.SAFE,
    )
    definition = _definition(spec)
    return ToolBinding(definition, _ListAssetsExecutor(dependencies.asset_store))


def _generation_binding(
    purpose: str,
    spec: _CreativeToolSpec,
    dependencies: _CreativeDependencies,
) -> ToolBinding:
    definition = _definition(spec)
    executor = _CreativeGenerationExecutor(
        purpose,
        dependencies.configuration_provider,
        dependencies.asset_store,
        dependencies.client_factory,
    )
    return ToolBinding(definition, executor)


def _definition(spec: _CreativeToolSpec) -> ToolDefinition:
    return ToolDefinition(
        name=spec.name,
        skill="creative-production",
        namespace="creative_media",
        description=spec.description,
        input_schema=spec.schema,
        action=spec.action,
        resource_type=spec.resource_type,
        intent_types=list(spec.intent_types),
        intent_aliases=list(spec.intent_aliases),
        skill_refs=["creative-production"],
        risk_level=spec.risk,
        effect_class=spec.effect,
        replay_policy=spec.replay,
        traits=[
            "creative_generation",
            "private_media",
            "bounded_output",
            (
                "billable_external_service"
                if spec.effect != ToolEffect.READ
                else "read_only"
            ),
        ],
        timeout_seconds=spec.timeout_seconds,
        max_output_bytes=16_000,
        required_permissions=[spec.permission],
        scope_required=False,
        result_items_key="assets",
        contract_version="1.0.0",
        live_support=False,
    )


def _image_schema() -> ToolSchema:
    return ToolSchema(
        properties={
            "prompt": {
                "type": "string",
                "minLength": 1,
                "maxLength": _MAX_PROMPT_CHARS,
                "description": "Creative direction based on verified product facts",
            },
            "size": {
                "type": "string",
                "enum": ["1K", "2K", "3K", "4K"],
                "default": "2K",
                "description": "Generated image resolution; Flash models support up to 2K",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": list(_IMAGE_ASPECT_RATIOS),
                "default": "1:1",
                "description": "Generated image aspect ratio",
            },
            "name": {
                "type": "string",
                "maxLength": _MAX_ASSET_NAME_CHARS,
                "description": "Short display name for the generated asset",
            },
        },
        required=["prompt"],
        additional_properties=False,
    )


def _video_schema() -> ToolSchema:
    return ToolSchema(
        properties={
            "prompt": {
                "type": "string",
                "minLength": 1,
                "maxLength": _MAX_PROMPT_CHARS,
                "description": "Short video brief with scene, motion and product constraints",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": list(_VIDEO_ASPECT_RATIOS),
                "default": "16:9",
                "description": "Video canvas orientation",
            },
            "duration_seconds": {
                "type": "integer",
                "minimum": 4,
                "maximum": 12,
                "default": 5,
                "description": "Video duration in seconds",
            },
            "resolution": {
                "type": "string",
                "enum": ["720P", "1080P"],
                "default": "720P",
                "description": "Agnes Video 2.5 resolution; Flash supports 720P",
            },
            "name": {
                "type": "string",
                "maxLength": _MAX_ASSET_NAME_CHARS,
                "description": "Short display name for the generated asset",
            },
        },
        required=["prompt"],
        additional_properties=False,
    )


def _image_request(arguments: Mapping[str, Any]) -> _ImageRequest:
    return _ImageRequest(
        prompt=_validated_prompt(arguments.get("prompt")),
        size=str(arguments.get("size") or "2K"),
        aspect_ratio=str(arguments.get("aspect_ratio") or "1:1"),
        name=_asset_name(arguments.get("name"), "广告创意图片"),
    )


def _single_generated_image(outputs: Any) -> _GeneratedImage:
    if not isinstance(outputs, list) or len(outputs) != 1:
        raise _InvalidGeneratedImage("image provider returned invalid output")
    output = outputs[0]
    if not isinstance(output, Mapping):
        raise _InvalidGeneratedImage("image provider returned invalid output")
    media_type = str(output.get("media_type") or "")
    extension = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
    }.get(media_type)
    content = output.get("content")
    if not extension or not isinstance(content, bytes):
        raise _InvalidGeneratedImage("image provider returned unsupported media")
    return _GeneratedImage(content, media_type, extension)


def _image_metadata(
    request: _ImageRequest,
    configuration: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "image",
        "status": "ready",
        "name": request.name,
        "prompt": redact_sensitive_text(request.prompt),
        "model": _safe_model_name(configuration),
        "image_size": request.size,
        "aspect_ratio": request.aspect_ratio,
    }


def _image_result(
    row: Mapping[str, Any],
    name: str,
    media_type: str,
) -> dict[str, Any]:
    asset_id = str(row["asset_id"])
    return {
        "id": asset_id,
        "asset_id": asset_id,
        "name": name,
        "url": _asset_url(asset_id),
        "media_type": media_type,
    }


def _video_request(arguments: Mapping[str, Any]) -> _VideoRequest:
    duration = arguments.get("duration_seconds", 5)
    if isinstance(duration, bool):
        raise ValueError("video duration must be an integer")
    return _VideoRequest(
        prompt=_validated_prompt(arguments.get("prompt")),
        aspect_ratio=str(arguments.get("aspect_ratio") or "16:9"),
        duration_seconds=int(duration),
        resolution=str(arguments.get("resolution") or "720P").upper(),
        name=_asset_name(arguments.get("name"), "广告创意视频"),
    )


def _video_metadata(
    request: _VideoRequest,
    configuration: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "video",
        "status": "submitting",
        "name": request.name,
        "prompt": redact_sensitive_text(request.prompt),
        "model": _safe_model_name(configuration),
        "model_endpoint_hash": _model_endpoint_hash(configuration),
        "aspect_ratio": request.aspect_ratio,
        "quality": request.resolution,
        "duration_seconds": request.duration_seconds,
    }


def _trusted_scope(context: Any) -> tuple[str, str]:
    metadata = getattr(context, "metadata", None)
    metadata = metadata if isinstance(metadata, Mapping) else {}
    scope = getattr(context, "scope", None)
    scope = scope if isinstance(scope, Mapping) else {}
    principal = scope.get("principal")
    tenant_id = str(
        getattr(principal, "tenant_id", None)
        or metadata.get("principal_tenant_id")
        or ""
    ).strip()
    user_id = str(
        getattr(principal, "user_id", None)
        or getattr(context, "user_id", None)
        or ""
    ).strip()
    if not tenant_id or not user_id:
        raise PermissionError("创意素材操作缺少可信的用户或租户身份。")
    if len(tenant_id) > 256 or len(user_id) > 256:
        raise PermissionError("创意素材操作身份无效。")
    return tenant_id, user_id


def _validated_prompt(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("creative prompt must be text")
    prompt = value.strip()
    if not prompt or len(prompt) > _MAX_PROMPT_CHARS:
        raise ValueError("creative prompt is empty or too long")
    return prompt


def _asset_name(value: Any, default: str) -> str:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        raise ValueError("asset name must be text")
    name = redact_sensitive_text(value.strip())
    if not name or len(name) > _MAX_ASSET_NAME_CHARS:
        raise ValueError("asset name is empty or too long")
    return name


def _filename_stem(value: str) -> str:
    result = "".join(
        character if character.isalnum() or character in "-_ " else "_"
        for character in value
    ).strip(" ._")
    return (result or "creative")[:80]


def _asset_url(asset_id: Any) -> str:
    return f"/creative/assets/{str(asset_id)}"


def _safe_model_name(configuration: Any) -> str:
    if not isinstance(configuration, Mapping):
        return ""
    return redact_sensitive_text(str(configuration.get("model") or ""))[:160]


def _model_endpoint_hash(configuration: Any) -> str:
    if not isinstance(configuration, Mapping):
        return ""
    endpoint = str(configuration.get("base_url") or "").strip()
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest() if endpoint else ""


def _safe_error_code(value: str) -> str:
    cleaned = "".join(
        character for character in str(value or "").lower()
        if character.isalnum() or character in "_-"
    )
    return cleaned[:80] or "creative_generation_failed"


def _generation_error_message(error_code: str) -> str:
    safe_code = _safe_error_code(error_code)
    messages = {
        "media_provider_request_failed": "媒体模型请求失败，请检查模型密钥、接口地址和额度。",
        "media_provider_auth_failed": (
            "Agnes 媒体服务拒绝了 API Key 或模型权限（HTTP 401/403）；"
            "请确认该密钥有效并已开通视频生成权限。"
        ),
        "media_provider_quota_exceeded": (
            "Agnes 返回额度或计费限制（HTTP 402）；请检查当前媒体模型的可用额度。"
        ),
        "media_provider_endpoint_not_found": (
            "Agnes 媒体接口或模型路由未找到（HTTP 404）；请检查服务端接口配置。"
        ),
        "media_provider_request_rejected": (
            "Agnes 拒绝了视频参数或提示词（HTTP 400/409/422）；"
            "请检查时长、720P 分辨率、画幅比例和提示词。"
        ),
        "media_provider_rate_limited": (
            "Agnes 返回限流或额度不足（HTTP 429）；请稍后重试或检查免费额度。"
        ),
        "media_provider_timeout": (
            "Agnes 媒体请求超时，上游是否已接收任务无法确认；"
            "请先查看执行记录，避免重复提交。"
        ),
        "media_provider_connection_failed": (
            "无法连接 Agnes 媒体服务，请检查网络连接后重试。"
        ),
        "media_provider_unavailable": (
            "Agnes 媒体服务暂时不可用（HTTP 5xx），请稍后重试。"
        ),
        "media_provider_video_queue_full": (
            "Agnes 视频生成队列已满（video_queue_full / HTTP 503），"
            "这是上游容量限制，不是本地 Key 或接口配置错误。"
            "系统已对明确未受理的队列满响应按退避策略自动重试；"
            "本次仍未获得上游任务编号，请稍后重新发起。"
        ),
        "media_provider_response_invalid": "媒体模型返回了无法识别的结果。",
        "media_provider_response_too_large": "媒体模型响应超过大小限制，未保存素材。",
        "media_result_url_unsafe": "媒体模型返回了不安全的下载地址，已拒绝下载。",
        "video_result_url_unsafe": "视频模型返回了不安全的下载地址，已拒绝下载。",
        "media_result_too_large": "生成的视频超过素材大小上限，未保存。",
        "video_result_too_large": "生成的视频超过素材大小上限，未保存。",
        "video_provider_job_failed": "视频模型任务失败，请调整提示词后重试。",
        "video_provider_download_failed": "视频生成完成，但下载素材失败。",
        "video_job_invalid": "视频模型返回的任务信息无效。",
        "video_provider_unavailable": "视频生成服务暂时不可用，请稍后重试。",
    }
    if safe_code in messages:
        return messages[safe_code]
    return "创意生成失败，请检查模型配置、提示词和服务状态后重试。"


def _model_setup_message(purpose: str) -> str:
    if purpose == "image_generation":
        return (
            "请先在“模型与密钥”中配置免费的 Agnes Image 2.5 Flash，"
            "并填写 Agnes API Key。"
        )
    return (
        "请先在“模型与密钥”中配置限时免费的 Agnes Video 2.5 Flash，"
        "并填写 Agnes API Key。"
    )


def _asset_result(row: Mapping[str, Any]) -> dict[str, Any]:
    asset_id = str(row.get("asset_id") or "")
    kind = str(row.get("kind") or "")
    status = str(row.get("status") or "")
    if len(asset_id) != 32 or kind not in {"image", "video"}:
        return {}
    result = {
        "id": asset_id,
        "asset_id": asset_id,
        "kind": kind,
        "name": redact_sensitive_text(
            str(row.get("name") or row.get("filename") or "创意素材")
        )[:_MAX_ASSET_NAME_CHARS],
        "status": status,
        "media_type": str(row.get("media_type") or ""),
    }
    if status == "ready":
        result["url"] = _asset_url(asset_id)
    return result


def _video_result(metadata: Mapping[str, Any]) -> dict[str, Any]:
    row = _asset_result(metadata)
    return {
        "asset_id": row.get("asset_id"),
        "status": row.get("status"),
        "video_assets": [row] if row else [],
    }


__all__ = ["creative_media_tool_source"]
