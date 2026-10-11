"""
无界美妆 - OCR成分识别API
POST /api/ocr/ingredient
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional, List
from app.models import OcrIngredientRequest, OcrIngredientResponse, Ingredient
from app.services.ocr_service import OcrService
from app.services.knowledge_base import IngredientStore
import base64
import os

router = APIRouter()

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
        service = get_ocr_service()
        
        # 处理图片
        texts, matched, warnings = service.process_image(
            image_base64=request.imageBase64,
            return_matches=request.returnMatches
        )
        
        return OcrIngredientResponse(
            success=True,
            recognizedTexts=texts,
            matchedIngredients=matched,
            warnings=warnings,
            message=f"识别完成，发现 {len(matched)} 个成分"
        )
        
    except Exception as e:
        return OcrIngredientResponse(
            success=False,
            recognizedTexts=[],
            matchedIngredients=[],
            warnings=[],
            message=f"OCR处理失败: {str(e)}"
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
        contents = await file.read()
        
        # 转换为Base64
        image_base64 = base64.b64encode(contents).decode("utf-8")
        
        # 调用OCR服务
        service = get_ocr_service()
        texts, matched, warnings = service.process_image(
            image_base64=image_base64,
            return_matches=True
        )
        
        # 如果提供了肤质标签，检查警告
        if skin_tags:
            tags = [t.strip() for t in skin_tags.split(",")]
            ingredient_warnings = service.check_warnings(matched, tags)
            warnings.extend(ingredient_warnings)
        
        return OcrIngredientResponse(
            success=True,
            recognizedTexts=texts,
            matchedIngredients=matched,
            warnings=warnings,
            message=f"识别完成，发现 {len(matched)} 个成分"
        )
        
    except Exception as e:
        return OcrIngredientResponse(
            success=False,
            recognizedTexts=[],
            matchedIngredients=[],
            warnings=[],
            message=f"文件处理失败: {str(e)}"
        )
