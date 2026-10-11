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
