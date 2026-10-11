import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.ocr_service import OcrService


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(OcrService, "_check_ocr_availability", lambda self: True)
    service = OcrService([])
    monkeypatch.setattr(service, "_decode_image", lambda data: object())
    monkeypatch.setattr(service, "_preprocess_image", lambda image: image)
    return service


@pytest.mark.parametrize("return_matches", [True, False])
@pytest.mark.parametrize("failure", ["import", "initialization", "recognition"])
def test_ocr_failure_returns_unavailable_warning(service, monkeypatch, failure, return_matches):
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

    assert service.process_image("aW1hZ2U=", return_matches) == ([], [], ["OCR不可用"])


@pytest.mark.parametrize("result, texts", [(None, []), ([[]], []), ([[[None, ("成分", 0.99)]]], ["成分"])])
def test_successful_ocr_preserves_results_without_unavailable_warning(service, monkeypatch, result, texts):
    engine = Mock()
    engine.ocr.return_value = result
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=Mock(return_value=engine)))

    assert service.process_image("aW1hZ2U=") == (texts, [], [])


def test_paddleocr_is_lazily_loaded_once_and_reused(service, monkeypatch):
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
    monkeypatch.setattr(
        service, "_decode_image", Mock(side_effect=RuntimeError("secret path"))
    )

    _, _, warnings = service.process_image("aW1hZ2U=")

    assert warnings == ["IMAGE_PROCESS_FAILED: 图片处理失败，请稍后重试"]
    assert "secret path" not in warnings[0]
