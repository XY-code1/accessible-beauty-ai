import asyncio
import base64
import io
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from PIL import Image
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.api import ocr
from app.services import ocr_service as service_module
from app.services.ocr_service import OcrResult, OcrService
from main import app


client = TestClient(app)
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def ocr_service(monkeypatch):
    """Provide a mocked OCR factory and service with a small image size limit."""
    monkeypatch.setattr(ocr, "MAX_IMAGE_SIZE", 16)
    service = Mock()
    service.process_image.return_value = OcrResult([], [], [])
    factory = Mock(return_value=service)
    monkeypatch.setattr(ocr, "get_ocr_service", factory)
    return factory, service


def test_json_image_accepts_valid_png(ocr_service):
    """Verify PNG data at the size limit reaches OCR with the requested match flag."""
    factory, service = ocr_service
    contents = PNG_HEADER + b"x" * 8
    encoded = base64.b64encode(contents).decode("ascii")

    response = client.post(
        "/api/ocr/ingredient",
        json={"imageBase64": encoded, "returnMatches": False},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
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
    """Verify invalid JSON image data is rejected before OCR initialization."""
    factory, _ = ocr_service

    response = client.post("/api/ocr/ingredient", json={"imageBase64": payload})

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    factory.assert_not_called()


def test_uploaded_image_accepts_valid_png(ocr_service):
    """Verify a PNG upload at the size limit is encoded and passed to OCR."""
    factory, service = ocr_service
    contents = PNG_HEADER + b"x" * 8

    response = client.post(
        "/api/ocr/ingredient/file",
        files={"file": ("image.png", contents, "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
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
    """Verify invalid uploads return stable errors before OCR initialization."""
    factory, _ = ocr_service

    response = client.post(
        "/api/ocr/ingredient/file",
        files={"file": ("image.bin", contents, content_type)},
    )

    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    factory.assert_not_called()


def test_uploaded_image_read_is_bounded(ocr_service):
    """Verify oversized uploads read only one byte beyond the configured limit."""
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
    """Verify both OCR endpoints hide internal service errors in public responses."""
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


def post_image(contents, file_upload, image_format="PNG", return_matches=True):
    if file_upload:
        return client.post(
            "/api/ocr/ingredient/file",
            files={"file": ("image", contents, f"image/{image_format.lower()}")},
            data={"skin_tags": "sensitive"},
        )
    return client.post(
        "/api/ocr/ingredient",
        json={
            "imageBase64": base64.b64encode(contents).decode("ascii"),
            "returnMatches": return_matches,
        },
    )


@pytest.mark.parametrize("file_upload", [False, True])
@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_routes_reject_excess_pixels_before_decoding(monkeypatch, file_upload, image_format):
    monkeypatch.setattr(service_module, "MAX_IMAGE_PIXELS", 4)
    service = OcrService([])
    decoder = Mock()
    preprocessor = Mock()
    monkeypatch.setattr(service, "_decode_image", decoder)
    monkeypatch.setattr(service, "_preprocess_image", preprocessor)
    monkeypatch.setattr(ocr, "get_ocr_service", lambda: service)
    output = io.BytesIO()
    Image.new("RGB", (3, 2)).save(output, format=image_format)

    response = post_image(output.getvalue(), file_upload, image_format)

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "IMAGE_TOO_LARGE"
    decoder.assert_not_called()
    preprocessor.assert_not_called()


@pytest.mark.parametrize("file_upload, return_matches", [(False, True), (False, False), (True, True)])
@pytest.mark.parametrize("failure", ["import", "initialization", "recognition"])
def test_routes_report_ocr_unavailable_as_failure(monkeypatch, file_upload, return_matches, failure):
    service = OcrService([])
    monkeypatch.setattr(service, "_decode_image", lambda data: object())
    monkeypatch.setattr(service, "_preprocess_image", lambda image: image)
    warning_checker = Mock()
    monkeypatch.setattr(service, "check_warnings", warning_checker)
    monkeypatch.setattr(ocr, "get_ocr_service", lambda: service)
    engine = Mock()
    constructor = Mock(return_value=engine)
    if failure == "import":
        monkeypatch.setitem(sys.modules, "paddleocr", None)
    else:
        monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=constructor))
        if failure == "initialization":
            constructor.side_effect = RuntimeError("secret initialization details")
        else:
            engine.ocr.side_effect = RuntimeError("secret recognition details")
    output = io.BytesIO()
    Image.new("RGB", (1, 1)).save(output, format="PNG")

    response = post_image(output.getvalue(), file_upload, return_matches=return_matches)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["recognizedTexts"] == []
    assert body["matchedIngredients"] == []
    assert body["warnings"] == ["OCR不可用"]
    assert body["message"].startswith("OCR_")
    assert "secret" not in str(body)
    warning_checker.assert_not_called()
