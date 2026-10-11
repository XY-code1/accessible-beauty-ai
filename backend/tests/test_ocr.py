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


@pytest.fixture
def ocr_service(monkeypatch):
    # Four bytes lets the limit and two oversized inputs share an encoded length.
    monkeypatch.setattr(ocr, "MAX_IMAGE_SIZE", 4)
    service = Mock()
    service.process_image.return_value = ([], [], [])
    factory = Mock(return_value=service)
    monkeypatch.setattr(ocr, "get_ocr_service", factory)
    return factory, service


@pytest.mark.parametrize("size", [0, 3, 4, 5, 6, 7])
def test_json_image_size_boundary(ocr_service, size):
    factory, service = ocr_service
    encoded = base64.b64encode(b"x" * size).decode("ascii")

    response = client.post(
        "/api/ocr/ingredient",
        json={"imageBase64": encoded, "returnMatches": False},
    )

    if size > ocr.MAX_IMAGE_SIZE:
        assert response.status_code == 413
        factory.assert_not_called()
    else:
        assert response.status_code == 200
        assert response.json()["success"] is True
        service.process_image.assert_called_once_with(
            image_base64=encoded, return_matches=False
        )


@pytest.mark.parametrize("size", [0, 3, 4, 5, 20])
def test_uploaded_image_size_boundary(ocr_service, size):
    factory, service = ocr_service
    contents = b"x" * size

    response = client.post(
        "/api/ocr/ingredient/file",
        files={"file": ("image.png", contents, "image/png")},
    )

    if size > ocr.MAX_IMAGE_SIZE:
        assert response.status_code == 413
        factory.assert_not_called()
    else:
        assert response.status_code == 200
        assert response.json()["success"] is True
        service.process_image.assert_called_once_with(
            image_base64=base64.b64encode(contents).decode("ascii"),
            return_matches=True,
        )


def test_uploaded_image_read_is_bounded(ocr_service):
    upload = UploadFile(file=io.BytesIO(b"x" * 20))
    upload.read = AsyncMock(wraps=upload.read)

    with pytest.raises(HTTPException) as error:
        asyncio.run(ocr.recognize_ingredients_file(upload, skin_tags=None))

    assert error.value.status_code == 413
    upload.read.assert_awaited_once_with(ocr.MAX_IMAGE_SIZE + 1)
    assert upload.file.tell() == ocr.MAX_IMAGE_SIZE + 1


@pytest.mark.parametrize("file_upload", [False, True])
@pytest.mark.parametrize("http_error", [False, True])
def test_ocr_error_handling(ocr_service, file_upload, http_error):
    _, service = ocr_service
    service.process_image.side_effect = (
        HTTPException(status_code=413, detail="Image too large")
        if http_error
        else RuntimeError("OCR failed")
    )

    if file_upload:
        response = client.post(
            "/api/ocr/ingredient/file",
            files={"file": ("image.png", b"x", "image/png")},
        )
    else:
        response = client.post(
            "/api/ocr/ingredient", json={"imageBase64": "eA=="}
        )

    if http_error:
        assert response.status_code == 413
        assert response.json()["detail"] == "Image too large"
    else:
        assert response.status_code == 200
        assert response.json()["success"] is False
        assert "OCR failed" in response.json()["message"]
