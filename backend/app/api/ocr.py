"""
无界美妆 - OCR成分识别API
POST /api/ocr/ingredient
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from app.models import OcrIngredientRequest, OcrIngredientResponse
from app.services.ocr_service import ImageTooLargeError, OcrService
from app.services.knowledge_base import IngredientStore
import base64
import binascii
import logging
import os

router = APIRouter()

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MiB of decoded image data
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

logger = logging.getLogger(__name__)


def _error(status_code: int, code: str, message: str) -> HTTPException:
    """构造包含稳定错误代码和公开消息的 HTTP 异常。"""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _detect_image_type(contents: bytes) -> Optional[str]:
    """根据文件头识别 PNG、JPEG 或 WebP 类型；未知类型返回 None。"""
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contents.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(contents) >= 12 and contents.startswith(b"RIFF") and contents[8:12] == b"WEBP":
        return "image/webp"
    return None


def _validate_image(contents: bytes, declared_type: Optional[str] = None) -> str:
    """返回文件头识别的类型；大小超限、类型不支持或声明不符时抛出 HTTP 异常。"""
    if len(contents) > MAX_IMAGE_SIZE:
        raise _error(413, "IMAGE_TOO_LARGE", "图片超过 10 MiB 大小限制")

    detected_type = _detect_image_type(contents)
    if detected_type is None:
        raise _error(415, "UNSUPPORTED_IMAGE_TYPE", "仅支持 PNG、JPEG 或 WebP 图片")
    if declared_type and declared_type.lower() not in ALLOWED_IMAGE_TYPES:
        raise _error(415, "UNSUPPORTED_IMAGE_TYPE", "仅支持 PNG、JPEG 或 WebP 图片")
    if declared_type and declared_type.lower() != detected_type:
        raise _error(415, "IMAGE_TYPE_MISMATCH", "图片内容与声明类型不一致")
    return detected_type

# 全局OCR服务实例
_ocr_service: OcrService = None


def get_ocr_service() -> OcrService:
    """获取或创建OCR服务"""
    global _ocr_service
    
    if _ocr_service is None:
        # 加载成分知识库
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", 
            "ingredients.json"
        )
        ingredient_store = IngredientStore(data_path)
        ingredients_data = [ing.model_dump() for ing in ingredient_store.get_all()]
        
        _ocr_service = OcrService(ingredients_data)
    
    return _ocr_service


@router.post("/ocr/ingredient", response_model=OcrIngredientResponse)
async def recognize_ingredients(request: OcrIngredientRequest) -> OcrIngredientResponse:
    """
    OCR成分识别接口
    
    上传产品图片，识别其中的美妆成分
    """
    try:
        if len(request.imageBase64) > 4 * ((MAX_IMAGE_SIZE + 2) // 3):
            raise _error(413, "IMAGE_TOO_LARGE", "图片超过 10 MiB 大小限制")
        try:
            image_data = base64.b64decode(request.imageBase64, validate=True)
        except (binascii.Error, ValueError):
            raise _error(422, "INVALID_IMAGE_BASE64", "图片数据不是有效的 Base64 编码")
        _validate_image(image_data)

        service = get_ocr_service()
        
        # 处理图片
        result = service.process_image(
            image_base64=request.imageBase64,
            return_matches=request.returnMatches
        )
        
        return OcrIngredientResponse(
            success=result.success,
            recognizedTexts=result.texts,
            matchedIngredients=result.matched,
            warnings=result.warnings,
            message=(f"识别完成，发现 {len(result.matched)} 个成分" if result.success
                     else "OCR_PROCESS_FAILED: OCR处理失败，请稍后重试")
        )
        
    except ImageTooLargeError:
        raise _error(413, "IMAGE_TOO_LARGE", "图片超过 1600 万像素限制")
    except HTTPException:
        raise
    except Exception:
        logger.exception("OCR JSON request failed")
        return OcrIngredientResponse(
            success=False,
            recognizedTexts=[],
            matchedIngredients=[],
            warnings=[],
            message="OCR_PROCESS_FAILED: OCR处理失败，请稍后重试"
        )


@router.post("/ocr/ingredient/file", response_model=OcrIngredientResponse)
async def recognize_ingredients_file(
    file: UploadFile = File(..., description="产品图片文件"),
    skin_tags: Optional[str] = Form(default=None, description="用户肤质标签，逗号分隔")
) -> OcrIngredientResponse:
    """
    OCR成分识别接口 - 文件上传方式
    
    上传产品图片文件，识别其中的美妆成分
    """
    try:
        # 读取文件内容
        contents = await file.read(MAX_IMAGE_SIZE + 1)
        _validate_image(contents, file.content_type)
        
        # 转换为Base64
        image_base64 = base64.b64encode(contents).decode("utf-8")
        
        # 调用OCR服务
        service = get_ocr_service()
        result = service.process_image(
            image_base64=image_base64,
            return_matches=True
        )
        
        # 如果提供了肤质标签，检查警告
        if skin_tags and result.success:
            tags = [t.strip() for t in skin_tags.split(",")]
            ingredient_warnings = service.check_warnings(result.matched, tags)
            result.warnings.extend(ingredient_warnings)
        
        return OcrIngredientResponse(
            success=result.success,
            recognizedTexts=result.texts,
            matchedIngredients=result.matched,
            warnings=result.warnings,
            message=(f"识别完成，发现 {len(result.matched)} 个成分" if result.success
                     else "OCR_UPLOAD_FAILED: 文件处理失败，请稍后重试")
        )
        
    except ImageTooLargeError:
        raise _error(413, "IMAGE_TOO_LARGE", "图片超过 1600 万像素限制")
    except HTTPException:
        raise
    except Exception:
        logger.exception("OCR upload request failed")
        return OcrIngredientResponse(
            success=False,
            recognizedTexts=[],
            matchedIngredients=[],
            warnings=[],
            message="OCR_UPLOAD_FAILED: 文件处理失败，请稍后重试"
        )
