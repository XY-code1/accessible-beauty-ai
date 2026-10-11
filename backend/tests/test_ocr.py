import asyncio
import base64
import io
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.api import ocr
from main import app


client = TestClient(app)
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def ocr_service(monkeypatch):
    monkeypatch.setattr(ocr, "MAX_IMAGE_SIZE", 16)
    service = Mock()
    service.process_image.return_value = ([], [], [])
    factory = Mock(return_value=service)
    monkeypatch.setattr(ocr, "get_ocr_service", factory)
    return factory, service


def test_json_image_accepts_valid_png(ocr_service):
    factory, service = ocr_service
    contents = PNG_HEADER + b"x" * 8
    encoded = base64.b64encode(contents).decode("ascii")

    response = client.post(
        "/api/ocr/ingredient",
        json={"imageBase64": encoded, "returnMatches": False},
    )

    assert response.status_code == 200
    factory.assert_called_once()
    service.process_image.assert_called_once_with(
        image_base64=encoded, return_matches=False
    )


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [
        ("not-base64!", 422, "INVALID_IMAGE_BASE64"),
        (base64.b64encode(b"not-an-image").decode("ascii"), 415, "UNSUPPORTED_IMAGE_TYPE"),
        (base64.b64encode(PNG_HEADER + b"x" * 9).decode("ascii"), 413, "IMAGE_TOO_LARGE"),
    ],
)
def test_json_image_rejects_invalid_input(ocr_service, payload, status, code):
    factory, _ = ocr_service

    response = client.post("/api/ocr/ingredient", json={"imageBase64": payload})

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    factory.assert_not_called()


def test_uploaded_image_accepts_valid_png(ocr_service):
    factory, service = ocr_service
    contents = PNG_HEADER + b"x" * 8

    response = client.post(
        "/api/ocr/ingredient/file",
        files={"file": ("image.png", contents, "image/png")},
    )

    assert response.status_code == 200
    factory.assert_called_once()
    service.process_image.assert_called_once_with(
        image_base64=base64.b64encode(contents).decode("ascii"),
        return_matches=True,
    )


@pytest.mark.parametrize(
    ("contents", "content_type", "status", "code"),
    [
        (PNG_HEADER + b"x" * 9, "image/png", 413, "IMAGE_TOO_LARGE"),
        (b"GIF89a", "image/gif", 415, "UNSUPPORTED_IMAGE_TYPE"),
        (PNG_HEADER, "image/jpeg", 415, "IMAGE_TYPE_MISMATCH"),
    ],
)
def test_uploaded_image_rejects_invalid_input(
    ocr_service, contents, content_type, status, code
):
    factory, _ = ocr_service

    response = client.post(
        "/api/ocr/ingredient/file",
        files={"file": ("image.bin", contents, content_type)},
    )

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    factory.assert_not_called()


def test_uploaded_image_read_is_bounded(ocr_service):
    upload = UploadFile(
        file=io.BytesIO(PNG_HEADER + b"x" * 20),
        headers={"content-type": "image/png"},
    )
    upload.read = AsyncMock(wraps=upload.read)

    with pytest.raises(HTTPException) as error:
        asyncio.run(ocr.recognize_ingredients_file(upload, skin_tags=None))

    assert error.value.status_code == 413
    upload.read.assert_awaited_once_with(ocr.MAX_IMAGE_SIZE + 1)
    assert upload.file.tell() == ocr.MAX_IMAGE_SIZE + 1


@pytest.mark.parametrize("file_upload", [False, True])
def test_ocr_runtime_error_is_sanitized(ocr_service, file_upload):
    _, service = ocr_service
    service.process_image.side_effect = RuntimeError("secret internal path")
    contents = PNG_HEADER + b"x"

    if file_upload:
        response = client.post(
            "/api/ocr/ingredient/file",
            files={"file": ("image.png", contents, "image/png")},
        )
    else:
        response = client.post(
            "/api/ocr/ingredient",
            json={"imageBase64": base64.b64encode(contents).decode("ascii")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "secret internal path" not in body["message"]
    assert body["message"].startswith("OCR_")
