import asyncio
import base64

import httpx
import pytest

from comfyshop_official_worker.atlas_cloud import (
    ATLAS_ROOT,
    Atlas,
    AtlasSpec,
    InlineOutput,
    MediaBinding,
    RunError,
)

REFERENCE_URL = "https://cdn.example/reference.png"


def test_prompt_length_excludes_trailing_flags_without_changing_payload():
    spec = AtlasSpec(
        model="midjourney/v8.2/text-to-image",
        operation="image",
        parameters={"prompt": "prompt"},
        required_text=["prompt"],
        text_max_lengths={"prompt": 1024},
        text_flag_suffix_parameters={"prompt"},
    )
    prompt = "x" * 1024 + " --no text --raw"
    assert spec.payload({"prompt": prompt})["prompt"] == prompt
    with pytest.raises(RunError, match="最多 1024"):
        spec.payload({"prompt": "x" + prompt})
    with pytest.raises(RunError, match="最多 1024"):
        spec.payload({"prompt": "x" * 1024 + " -- x"})
    with pytest.raises(RunError, match="请填写提示词"):
        spec.payload({"prompt": " --raw"})


def test_duration_respects_resolution_and_integer_frame_rate_ranges():
    spec = AtlasSpec.model_validate(
        {
            "model": "ltx/ltx-2.5-fast/text-to-video",
            "operation": "video",
            "parameters": {"duration": "seconds", "resolution": "resolution", "fps": "fps"},
            "choice_bounds": {
                "duration": [
                    {
                        "parameter": "resolution",
                        "ranges": {"1440p": [6, 10], "4k": [6, 10]},
                        "exceptions": [-1],
                    },
                    {
                        "parameter": "fps",
                        "ranges": {"48": [6, 10], "50": [6, 10]},
                        "exceptions": [-1],
                    },
                ]
            },
        }
    )
    assert spec.payload({"seconds": 20, "resolution": "1080p", "fps": 25})["duration"] == 20
    assert spec.payload({"seconds": -1, "resolution": "4k", "fps": 50})["duration"] == -1
    for resolution, fps in (("1440p", 24), ("720p", 48), ("1080p", 50)):
        with pytest.raises(RunError, match="duration 必须在 6 至 10"):
            spec.payload({"seconds": 12, "resolution": resolution, "fps": fps})


def test_video_flags_reject_only_the_documented_conflicts():
    spec = AtlasSpec(
        model="luma/ray-3.2/text-to-video",
        operation="video",
        parameters={name: name for name in ("duration", "resolution", "loop", "hdr")},
        forbidden_combinations=[
            {"loop": True, "duration": [10]},
            {"loop": True, "hdr": True},
            {"hdr": True, "duration": [10]},
            {"hdr": True, "resolution": ["540p"]},
        ],
    )
    for values in (
        {"duration": 5, "resolution": "540p", "loop": True, "hdr": False},
        {"duration": 5, "resolution": "1080p", "hdr": True},
        {"duration": 10, "resolution": "720p", "hdr": False},
    ):
        assert spec.payload(values) == {"model": spec.model, **values}
    for values in (
        {"loop": True, "duration": 10},
        {"loop": True, "hdr": True},
        {"hdr": True, "duration": 10},
        {"hdr": True, "resolution": "540p"},
    ):
        with pytest.raises(RunError, match="参数组合"):
            spec.payload(values)


@pytest.mark.parametrize(
    ("mime", "content"),
    [
        ("audio/mp4", b"\x00\x00\x00\x14ftypM4A \x00\x00\x00\x00isom"),
        ("audio/ogg", b"OggS\x00" + bytes(22)),
    ],
)
def test_audio_reference_accepts_m4a_and_ogg_base64(mime, content):
    binding = MediaBinding(
        kind="audio",
        fields=["driving_audio"],
        external_sources_field="driving_audio_source",
        allow_raw_base64=True,
        content_types=["audio/mp4", "audio/ogg", "audio/mpeg"],
    )
    encoded = base64.b64encode(content).decode("ascii")
    for source in (encoded, f"data:{mime};base64,{encoded}"):
        assert binding.external_sources("audio", source, alpha_requirement=None) == [source]
    with pytest.raises(RunError, match="Base64 音频格式不受支持"):
        binding.external_sources(
            "audio", f"data:audio/mpeg;base64,{encoded}", alpha_requirement=None
        )


@pytest.mark.parametrize(
    ("mime", "header"),
    [
        ("video/mp4", b"\x00\x00\x00\x14ftypmp42\x00\x00\x00\x00mp42"),
        ("video/quicktime", b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  "),
        ("video/webm", b"\x1a\x45\xdf\xa3\x87\x42\x82\x84webm"),
    ],
)
def test_base64_video_requires_matching_supported_container(mime, header):
    binding = MediaBinding(
        kind="video",
        fields=["video"],
        external_sources_field="video_source",
        allow_raw_base64=True,
        content_types=["video/mp4", "video/quicktime", "video/webm"],
    )
    encoded = base64.b64encode(header).decode("ascii")
    data_uri = f"data:{mime};base64,{encoded}"
    for source in (encoded, data_uri):
        assert binding.external_sources("video", source, alpha_requirement=None) == [source]

    wrong_mime = "video/webm" if mime != "video/webm" else "video/mp4"
    with pytest.raises(RunError, match="Base64 视频格式不受支持"):
        binding.external_sources(
            "video", f"data:{wrong_mime};base64,{encoded}", alpha_requirement=None
        )
    with pytest.raises(RunError, match="视频地址"):
        binding.model_copy(update={"allow_raw_base64": False}).external_sources(
            "video", data_uri, alpha_requirement=None
        )


def test_image_reference_passes_through_an_oss_temporary_url_when_enabled():
    binding = MediaBinding(
        kind="image",
        fields=["image"],
        external_sources_field="image_source",
        external_urls_only=True,
        allow_oss_references=True,
    )
    source = "oss://example-bucket/uploads/reference.png"
    assert binding.external_sources("image", source, alpha_requirement=None) == [source]
    with pytest.raises(RunError, match="图片地址"):
        binding.external_sources("image", "oss://example-bucket/", alpha_requirement=None)
    with pytest.raises(RunError, match="图片地址"):
        binding.model_copy(update={"allow_oss_references": False}).external_sources(
            "image", source, alpha_requirement=None
        )


@pytest.mark.parametrize(
    ("value", "expected", "error"),
    [
        (" first scene \r\n\n second scene ", ["first scene", "second scene"], None),
        ("\n".join(["scene"] * 6), ["scene"] * 6, None),
        (None, None, "至少需要 1 项"),
        (" \n\t", None, "至少需要 1 项"),
        ("\n".join(["scene"] * 7), None, "最多 6 项"),
    ],
)
def test_required_text_array_preserves_scene_order(value, expected, error):
    spec = AtlasSpec.model_validate(
        {
            "model": "atlascloud/wan-2.2-turbo/infinite-image-to-video",
            "operation": "video",
            "parameters": {},
            "text_arrays": {"prompt": {"field": "prompt", "min_items": 1, "max_items": 6}},
        }
    )
    if error:
        with pytest.raises(RunError, match=error):
            spec.payload({"prompt": value})
    else:
        assert spec.payload({"prompt": value})["prompt"] == expected


@pytest.mark.parametrize(
    "body",
    [
        {"url": REFERENCE_URL},
        {"data": {"url": REFERENCE_URL}},
        {"data": {"download_url": REFERENCE_URL}},
    ],
)
def test_upload_accepts_atlas_url_shapes(tmp_path, body):
    image = tmp_path / "reference.png"
    image.write_bytes(b"reference image fixture")

    async def run():
        async with httpx.AsyncClient(
            base_url=ATLAS_ROOT,
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)),
        ) as client:
            assert await Atlas(client).upload(image, image.name, "image/png") == REFERENCE_URL

    asyncio.run(run())


@pytest.mark.parametrize(
    ("status", "error"),
    [
        ("completed", None),
        ("succeeded", None),
        ("timeout", "Atlas Cloud 生成超时"),
        ("failed", "Atlas Cloud 未能完成生成"),
    ],
)
def test_poll_stops_on_atlas_terminal_status(status, error):
    outputs = ["https://cdn.example/first.png", "https://cdn.example/second.png"]
    calls = 0

    def prediction(request):
        nonlocal calls
        calls += 1
        assert calls == 1
        assert request.method == "GET" and request.url.path.endswith("/prediction/prediction-1")
        result = {"status": status, "outputs": [] if error else outputs}
        return httpx.Response(200, json={"data": result})

    async def run():
        async with httpx.AsyncClient(
            base_url=ATLAS_ROOT, transport=httpx.MockTransport(prediction)
        ) as client:
            atlas = Atlas(client, poll_seconds=0)
            if error:
                with pytest.raises(RunError, match=error) as failure:
                    await atlas.outputs("prediction-1")
                assert failure.value.retryable
            else:
                assert await atlas.outputs("prediction-1") == outputs

    asyncio.run(run())


def test_parameter_object_can_replace_scalar_preset():
    spec = AtlasSpec.model_validate(
        {
            "model": "nvidia/cosmos-3-super/image-to-video",
            "operation": "video",
            "parameters": {"image_size": "size_preset"},
            "parameter_objects": {
                "image_size": {"width": "output_width", "height": "output_height"}
            },
        }
    )

    assert spec.payload({"size_preset": "landscape_16_9"})["image_size"] == "landscape_16_9"
    assert spec.payload({"size_preset": "landscape_16_9", "output_width": 768})["image_size"] == {
        "width": 768
    }
    assert spec.payload(
        {"size_preset": "landscape_16_9", "output_width": 768, "output_height": 1024}
    )["image_size"] == {"width": 768, "height": 1024}


def test_image_size_limits_apply_to_mapped_parameter_name():
    spec = AtlasSpec.model_validate(
        {
            "model": "krea-2-turbo/text-to-image",
            "operation": "image",
            "parameters": {"image_size": "size_preset"},
            "parameter_overrides": {"image_size": "custom_size"},
            "image_size_limits": {
                "parameter": "image_size",
                "min_side": 1,
                "max_side": 2048,
                "allow_auto": False,
                "preset_sizes": ["square_hd"],
                "separator": "x",
            },
        }
    )

    assert spec.payload({"size_preset": "square_hd"})["image_size"] == "square_hd"
    assert (
        spec.payload({"size_preset": "square_hd", "custom_size": "1024x768"})["image_size"]
        == "1024x768"
    )
    with pytest.raises(RunError, match="图片尺寸超出范围"):
        spec.payload({"size_preset": "square_hd", "custom_size": "2049x768"})
    with pytest.raises(RunError, match="宽x高"):
        spec.payload({"size_preset": "square_hd", "custom_size": "1024*768"})


PNG_HEADER = b"\x89PNG\r\n\x1a\n"
BASE64_PNG = base64.b64encode(PNG_HEADER).decode("ascii")


@pytest.mark.parametrize(
    ("output", "inline_format", "error"),
    [
        (f"data:image/png;base64,{BASE64_PNG}", "image", None),
        (f"data:image/png;base64,{BASE64_PNG}", None, "成品地址无效"),
        (f"data:text/html;base64,{BASE64_PNG}", "image", "Base64 图像无效"),
        ("https://", "image", "Base64 图像无效"),
        ("aGVsbG8=", "image", "Base64 图像无效"),
        (f"data:application/zip;base64,{BASE64_PNG}", "zip", "Base64 ZIP 无效"),
        (f"data:video/mp4;base64,{BASE64_PNG}", "mp4", "Base64 视频无效"),
    ],
)
def test_poll_requires_opt_in_and_valid_inline_data(output, inline_format, error):
    async def run():
        response = {"data": {"status": "completed", "outputs": [output]}}
        async with httpx.AsyncClient(
            base_url=ATLAS_ROOT,
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)),
        ) as client:
            atlas = Atlas(client, poll_seconds=0)
            if error:
                with pytest.raises(RunError, match=error):
                    await atlas.outputs("prediction-1", inline_format=inline_format)
            else:
                assert await atlas.outputs("prediction-1", inline_format=inline_format) == [
                    InlineOutput(PNG_HEADER, ".png")
                ]

    asyncio.run(run())
