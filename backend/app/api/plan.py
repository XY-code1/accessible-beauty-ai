"""
无界美妆 - 方案生成API
POST /api/plan
"""
from fastapi import APIRouter
from app.models import PlanRequest, PlanResponse
from app.services.plan_engine import PlanEngine
from app.services.knowledge_base import IngredientStore
import logging
import os
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)

# 全局规则引擎实例
_plan_engine: Optional[PlanEngine] = None


def get_plan_engine() -> PlanEngine:
    """获取或创建规则引擎"""
    global _plan_engine
    
    if _plan_engine is None:
        # 加载成分知识库
        data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ingredients.json")
        ingredient_store = IngredientStore(data_path)
        ingredients_data = [ing.model_dump() for ing in ingredient_store.get_all()]
        
        _plan_engine = PlanEngine(ingredients_data)
    
    return _plan_engine


@router.post("/plan", response_model=PlanResponse)
async def generate_plan(request: PlanRequest) -> PlanResponse:
    """
    眉妆方案生成接口
    
    根据美妆参数和用户画像生成完整的眉妆步骤方案
    """
    try:
        engine = get_plan_engine()
        
        # 调用规则引擎生成方案
        steps, total_duration, omitted_count = engine.generate_plan(
            params=request.parameters,
            profile=request.profile
        )
        
        return PlanResponse(
            success=True,
            steps=steps,
            totalDuration=total_duration,
            omittedCount=omitted_count,
            message="方案生成成功"
        )
        
    except Exception:
        logger.exception("Plan generation failed")
        return PlanResponse(
            success=False,
            steps=[],
            totalDuration=0,
            omittedCount=0,
            message="PLAN_GENERATION_FAILED: 方案生成失败，请稍后重试"
        )


@router.get("/plan/steps")
async def list_steps():
    """
    获取所有可用步骤定义
    """
    from app.services.plan_engine import ALL_STEPS_CONFIG
    
    return {
        "success": True,
        "steps": [
            {
                "step": step.value,
                "name": config["name"],
                "duration": config["duration"],
                "essential": config["essential"],
                "products": config["products"],
                "tips": config["tips"]
            }
            for step, config in ALL_STEPS_CONFIG.items()
        ]
    }

