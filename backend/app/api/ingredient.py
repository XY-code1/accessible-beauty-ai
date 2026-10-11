"""
无界美妆 - 成分查询API
GET /api/ingredient
"""
from fastapi import APIRouter, Query
from typing import List, Optional
from app.models import Ingredient, IngredientQueryResponse
from app.services.knowledge_base import IngredientStore
import os

router = APIRouter()

# 全局知识库实例
_ingredient_store: IngredientStore = None


def get_ingredient_store() -> IngredientStore:
    """获取或创建知识库"""
    global _ingredient_store
    
    if _ingredient_store is None:
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", 
            "ingredients.json"
        )
        _ingredient_store = IngredientStore(data_path)
    
    return _ingredient_store


@router.get("/ingredient", response_model=IngredientQueryResponse)
async def search_ingredients(
    keyword: str = Query(default="", description="搜索关键词"),
    limit: int = Query(default=10, ge=1, le=50, description="返回数量限制")
) -> IngredientQueryResponse:
    """
    成分模糊查询接口
    
    支持按名称、中文名、类别、功效进行模糊搜索
    """
    try:
        store = get_ingredient_store()
        
        # 执行搜索
        ingredients = store.search(keyword=keyword, limit=limit)
        
        return IngredientQueryResponse(
            success=True,
            ingredients=ingredients,
            total=len(ingredients)
        )
        
    except Exception as e:
        return IngredientQueryResponse(
            success=False,
            ingredients=[],
            total=0
        )


@router.get("/ingredient/all", response_model=IngredientQueryResponse)
async def list_all_ingredients(
    limit: int = Query(default=20, ge=1, le=100, description="返回数量限制")
) -> IngredientQueryResponse:
    """
    获取所有成分列表
    """
    try:
        store = get_ingredient_store()
        ingredients = store.get_all()[:limit]
        
        return IngredientQueryResponse(
            success=True,
            ingredients=ingredients,
            total=len(ingredients)
        )
        
    except Exception as e:
        return IngredientQueryResponse(
            success=False,
            ingredients=[],
            total=0
        )


@router.get("/ingredient/{ingredient_id}", response_model=Optional[Ingredient])
async def get_ingredient(ingredient_id: str) -> Optional[Ingredient]:
    """
    根据ID获取单个成分详情
    """
    try:
        store = get_ingredient_store()
        return store.get_by_id(ingredient_id)
        
    except Exception:
        return None
