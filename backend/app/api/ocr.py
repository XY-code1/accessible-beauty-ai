"""
向后兼容层：保持 app.api.ocr 可用，实际实现位于 app.routes.ocr
新代码请直接 from app.routes.ocr import ...
"""
from app.routes.ocr import *  # noqa: F401,F403
from app.routes import ocr as _routes_ocr  # noqa: F401

# 暴露所有关键符号
router = _routes_ocr.router
recognize_ingredients = _routes_ocr.recognize_ingredients
recognize_ingredients_file = _routes_ocr.recognize_ingredients_file
get_ocr_service = _routes_ocr.get_ocr_service
MAX_IMAGE_SIZE = _routes_ocr.MAX_IMAGE_SIZE
ALLOWED_IMAGE_TYPES = _routes_ocr.ALLOWED_IMAGE_TYPES
