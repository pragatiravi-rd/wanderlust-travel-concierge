import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent import generate_destination_video, GCS_BUCKET_NAME, root_agent


@pytest.mark.asyncio
async def test_generate_destination_video_success():
    mock_genai_client = MagicMock()
    mock_interaction = MagicMock()
    mock_video = MagicMock()
    mock_video.data = b"fake_mp4_video_bytes"
    mock_video.video_bytes = b"fake_mp4_video_bytes"
    mock_video.mime_type = "video/mp4"
    mock_interaction.output_video = mock_video
    mock_genai_client.interactions.create.return_value = mock_interaction

    mock_storage_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_storage_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    mock_tool_context = AsyncMock()

    with (
        patch("google.genai.Client", return_value=mock_genai_client),
        patch("google.cloud.storage.Client", return_value=mock_storage_client),
    ):
        result = await generate_destination_video(
            description="Kyoto Bamboo Forest path in morning breeze",
            tool_context=mock_tool_context,
        )

    assert "Successfully generated destination video!" in result
    assert f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/" in result
    assert result.endswith(".mp4")

    # Verify tool_context.save_artifact was called
    mock_tool_context.save_artifact.assert_called_once()
    _, kwargs = mock_tool_context.save_artifact.call_args
    assert "filename" in kwargs
    assert kwargs["filename"].startswith("destination_video_")
    assert kwargs["filename"].endswith(".mp4")

    # Verify storage upload
    mock_storage_client.bucket.assert_called_with(GCS_BUCKET_NAME)
    mock_blob.upload_from_string.assert_called_once_with(
        b"fake_mp4_video_bytes", content_type="video/mp4"
    )


def test_generate_destination_video_registered_in_root_agent():
    tool_names = [getattr(t, "__name__", str(t)) for t in root_agent.tools]
    assert "generate_destination_video" in tool_names
