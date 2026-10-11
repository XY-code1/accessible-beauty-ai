"""
无界美妆 - FastAPI 主应用
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.api import intent, plan, ingredient, ocr
from app.models import HealthResponse

# 创建FastAPI应用
app = FastAPI(
    title="无界美妆 API",
    description="无障碍美妆推荐后端服务 - 眉妆闭环与公共接口",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(intent.router, prefix="/api", tags=["意图识别"])
app.include_router(plan.router, prefix="/api", tags=["方案生成"])
app.include_router(ingredient.router, prefix="/api", tags=["成分查询"])
app.include_router(ocr.router, prefix="/api", tags=["OCR识别"])


@app.get("/", tags=["首页"])
async def root():
    """首页"""
    return {
        "name": "无界美妆 API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse, tags=["健康检查"])
async def health_check() -> HealthResponse:
    """健康检查接口"""
    return HealthResponse(
        status="healthy",
        version=app.version,
        timestamp=time.time()
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"服务器内部错误: {str(exc)}",
            "detail": str(exc) if app.debug else None
        }
    )


# 启动信息
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
