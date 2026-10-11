"""
无界美妆 - 意图识别API
POST /api/intent
"""
from fastapi import APIRouter
import logging
from app.models import IntentRequest, IntentResponse, BeautyParameters
from app.services.plan_engine import IntentEngine

router = APIRouter()
logger = logging.getLogger(__name__)

# 全局意图引擎实例
_intent_engine = IntentEngine()


@router.post("/intent", response_model=IntentResponse)
async def parse_intent(request: IntentRequest) -> IntentResponse:
    """
    意图识别接口
    
    将用户自然语言输入解析为美妆参数
    预留LLM位，失败静默降级到规则匹配
    """
    try:
        # 调用意图引擎解析
        params, confidence = _intent_engine.parse(request.query)
        
        if params is None or confidence < 0.3:
            # 降级：使用默认参数
            params = BeautyParameters(
                scene="daily",
                style="natural",
                intensity="medium"
            )
            confidence = 0.0
            
            return IntentResponse(
                success=True,
                parameters=params,
                confidence=confidence,
                fallback=True,
                message="使用默认参数（规则匹配失败）"
            )
        
        # LLM增强位（预留）
        # TODO: 在此接入LLM进行更精确的意图解析
        # if use_llm:
        #     params = await llm_enhance(request.query, params)
        
        return IntentResponse(
            success=True,
            parameters=params,
            confidence=confidence,
            fallback=False,
            message="意图解析成功"
        )
        
    except Exception:
        logger.exception("Intent parsing failed; using defaults")
        # 静默降级
        default_params = BeautyParameters(
            scene="daily",
            style="natural",
            intensity="medium"
        )
        
        return IntentResponse(
            success=True,
            parameters=default_params,
            confidence=0.0,
            fallback=True,
            message="INTENT_FALLBACK: 解析失败，已使用默认参数"
        )
