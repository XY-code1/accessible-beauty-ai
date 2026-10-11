import base64
import io
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from app.services import ocr_service
from app.services.ocr_service import ImageTooLargeError, OcrResult, OcrService


def encoded_image(size=(1, 1), image_format="PNG"):
    output = io.BytesIO()
    Image.new("RGB", size).save(output, format=image_format)
    return base64.b64encode(output.getvalue()).decode("ascii")


@pytest.fixture
def service(monkeypatch):
    """Provide an OCR service with availability, decoding, and preprocessing stubbed."""
    monkeypatch.setattr(OcrService, "_check_ocr_availability", lambda self: True)
    service = OcrService([])
    monkeypatch.setattr(service, "_decode_image", lambda data: object())
    monkeypatch.setattr(service, "_preprocess_image", lambda image: image)
    return service


@pytest.mark.parametrize("return_matches", [True, False])
@pytest.mark.parametrize("failure", ["import", "initialization", "recognition"])
def test_ocr_failure_returns_unavailable_warning(service, monkeypatch, failure, return_matches):
    """Verify OCR import, initialization, and recognition failures degrade gracefully."""
    engine = Mock()
    constructor = Mock(return_value=engine)
    if failure == "import":
        monkeypatch.setitem(sys.modules, "paddleocr", None)
    else:
        monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=constructor))
        if failure == "initialization":
            constructor.side_effect = RuntimeError("initialization failed")
        else:
            engine.ocr.side_effect = RuntimeError("recognition failed")

    assert service.process_image(encoded_image(), return_matches) == OcrResult(
        [], [], ["OCR不可用"], success=False
    )


@pytest.mark.parametrize("result, texts", [(None, []), ([[]], []), ([[[None, ("成分", 0.99)]]], ["成分"])])
def test_successful_ocr_preserves_results_without_unavailable_warning(service, monkeypatch, result, texts):
    """Verify successful OCR, including empty results, produces no failure warning."""
    engine = Mock()
    engine.ocr.return_value = result
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=Mock(return_value=engine)))

    assert service.process_image(encoded_image()) == OcrResult(texts, [], [])


def test_paddleocr_is_lazily_loaded_once_and_reused(service, monkeypatch):
    """Verify text extraction initializes PaddleOCR once and reuses the engine."""
    engine = Mock()
    engine.ocr.return_value = [[]]
    constructor = Mock(return_value=engine)
    monkeypatch.setitem(
        sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=constructor)
    )

    service._extract_text(object())
    service._extract_text(object())

    constructor.assert_called_once_with(
        lang="ch", use_angle_cls=True, show_log=False
    )
    assert engine.ocr.call_count == 2


def test_unexpected_processing_error_is_sanitized(service, monkeypatch):
    """Verify unexpected processing failures return a warning without internal details."""
    monkeypatch.setattr(
        service, "_decode_image", Mock(side_effect=RuntimeError("secret path"))
    )

    result = service.process_image(encoded_image())

    assert result.success is False
    assert result.warnings == ["IMAGE_PROCESS_FAILED: 图片处理失败，请稍后重试"]
    assert "secret path" not in result.warnings[0]


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_pixel_limit_rejects_compressed_images_before_decoding(service, monkeypatch, image_format):
    monkeypatch.setattr(ocr_service, "MAX_IMAGE_PIXELS", 4)
    decoder = Mock()
    preprocessor = Mock()
    monkeypatch.setattr(service, "_decode_image", decoder)
    monkeypatch.setattr(service, "_preprocess_image", preprocessor)
    encoded = encoded_image((3, 2), image_format)
    assert len(base64.b64decode(encoded)) < 1024

    with pytest.raises(ImageTooLargeError):
        service.process_image(encoded)

    decoder.assert_not_called()
    preprocessor.assert_not_called()


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_image_at_pixel_limit_reaches_ocr(service, monkeypatch, image_format):
    monkeypatch.setattr(ocr_service, "MAX_IMAGE_PIXELS", 4)
    extractor = Mock(return_value=[])
    monkeypatch.setattr(service, "_extract_text", extractor)

    assert service.process_image(encoded_image((2, 2), image_format)).success is True
    extractor.assert_called_once()


@pytest.mark.parametrize("size", [(3, 1), (3, 2)])
def test_pillow_decompression_bombs_use_the_size_error(service, monkeypatch, size):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 2)
    decoder = Mock()
    monkeypatch.setattr(service, "_decode_image", decoder)

    with pytest.raises(ImageTooLargeError):
        service.process_image(encoded_image(size))

    decoder.assert_not_called()


@pytest.mark.parametrize("invalid_header", [False, True])
def test_invalid_image_is_a_failed_result(service, monkeypatch, invalid_header):
    monkeypatch.setattr(service, "_decode_image", Mock(return_value=None))
    encoded = "aW1hZ2U=" if invalid_header else encoded_image()

    result = service.process_image(encoded)

    assert result.success is False
    assert result.texts == []
    assert result.matched == []
    assert result.warnings
