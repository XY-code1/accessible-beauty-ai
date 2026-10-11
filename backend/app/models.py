"""
无界美妆 - 数据模型定义
严格对齐 PRD 第9章契约
"""
from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# ==================== 枚举定义 ====================

class Side(str, Enum):
    """左右侧标识"""
    LEFT = "left"
    RIGHT = "right"


class Verdict(str, Enum):
    """方向判断结果"""
    CLOSE = "close"      # 接近目标
    HIGH = "high"        # 偏高
    LOW = "low"          # 偏低
    UNKNOWN = "unknown"   # 无法判断


class Step(str, Enum):
    """眉妆步骤枚举"""
    SETUP = "setup"           # 准备
    SHAPE = "shape"           # 修整眉形
    FILL = "fill"             # 填充
    DEFINE = "define"         # 勾勒轮廓
    SET = "set"               # 定妆


class Scene(str, Enum):
    """场景枚举"""
    DAILY = "daily"           # 日常
    WORK = "work"             # 职场
    PARTY = "party"           # 派对
    DATE = "date"             # 约会


class Style(str, Enum):
    """风格枚举"""
    NATURAL = "natural"       # 自然
    MATTE = "matte"           # 哑光
    GLOW = "glow"             # 缎光
    BOLD = "bold"             # 立体


class Intensity(str, Enum):
    """浓度枚举"""
    LIGHT = "light"          # 淡
    MEDIUM = "medium"         # 中
    FULL = "full"            # 浓


# ==================== 核心数据模型 ====================

class BeautyParameters(BaseModel):
    """美妆参数 - 眉妆推荐输入"""
    scene: Scene = Field(..., description="使用场景")
    style: Style = Field(..., description="妆效风格")
    intensity: Intensity = Field(..., description="浓度偏好")
    side: Optional[Side] = Field(default=None, description="侧别(left/right)")
    
    class Config:
        use_enum_values = True


class BeautyProfile(BaseModel):
    """用户画像"""
    skinType: str = Field(default="normal", description="肤质")
    skinTone: str = Field(default="medium", description="肤色")
    skinTags: List[str] = Field(default_factory=list, description="肤质标签列表")
    browShape: str = Field(default="natural", description="原生眉形")
    
    class Config:
        use_enum_values = True


class Ingredient(BaseModel):
    """美妆成分"""
    id: str = Field(..., description="成分唯一标识")
    name: str = Field(..., description="成分名称")
    nameZh: str = Field(..., description="中文名称")
    category: Literal["着色", "养护", "定型"] = Field(..., description="成分类别(着色/养护/定型)")
    description: str = Field(..., description="成分描述")
    benefits: List[str] = Field(default_factory=list, description="功效")
    cautionGroups: List[Literal["acne", "dry", "retinol", "sensitive"]] = Field(
        default_factory=list, 
        description="注意人群标签(acne/dry/retinol/sensitive)"
    )
    
    class Config:
        use_enum_values = True


class PlanStep(BaseModel):
    """方案步骤"""
    step: Step = Field(..., description="步骤类型")
    name: str = Field(..., description="步骤名称")
    duration: int = Field(..., description="预估时长(秒)")
    essential: bool = Field(..., description="是否为必要步骤")
    omittedReason: Optional[str] = Field(default=None, description="省略理由(当essential=false时)")
    replacedBy: Optional[str] = Field(default=None, description="替换原因(当有成分替换时)")
    products: List[str] = Field(default_factory=list, description="推荐产品类型")
    tips: List[str] = Field(default_factory=list, description="操作提示")
    
    class Config:
        use_enum_values = True


# ==================== 请求/响应模型 ====================

class IntentRequest(BaseModel):
    """意图识别请求"""
    query: str = Field(..., description="用户自然语言输入")
    profile: Optional[BeautyProfile] = Field(default=None, description="用户画像")


class IntentResponse(BaseModel):
    """意图识别响应"""
    success: bool = Field(..., description="是否成功")
    parameters: Optional[BeautyParameters] = Field(default=None, description="解析出的美妆参数")
    confidence: float = Field(default=0.0, description="置信度")
    fallback: bool = Field(default=False, description="是否使用降级方案")
    message: Optional[str] = Field(default=None, description="状态消息")


class PlanRequest(BaseModel):
    """方案生成请求"""
    parameters: BeautyParameters = Field(..., description="美妆参数")
    profile: Optional[BeautyProfile] = Field(default=None, description="用户画像")


class PlanResponse(BaseModel):
    """方案生成响应"""
    success: bool = Field(..., description="是否成功")
    steps: List[PlanStep] = Field(default_factory=list, description="眉妆步骤列表")
    totalDuration: int = Field(default=0, description="总时长(秒)")
    omittedCount: int = Field(default=0, description="省略步骤数")
    message: Optional[str] = Field(default=None, description="状态消息")


class IngredientQueryRequest(BaseModel):
    """成分查询请求"""
    keyword: str = Field(..., description="查询关键词")
    limit: int = Field(default=10, description="返回数量限制")


class IngredientQueryResponse(BaseModel):
    """成分查询响应"""
    success: bool = Field(..., description="是否成功")
    ingredients: List[Ingredient] = Field(default_factory=list, description="匹配的成分列表")
    total: int = Field(default=0, description="总数")


class OcrIngredientRequest(BaseModel):
    """OCR成分识别请求"""
    imageBase64: str = Field(..., description="Base64编码的图片数据")
    returnMatches: bool = Field(default=True, description="是否返回匹配结果")
    skinTags: Optional[List[str]] = Field(default=None, description="用户肤质标签列表，用于生成警告")


class OcrIngredientResponse(BaseModel):
    """OCR成分识别响应"""
    success: bool = Field(..., description="是否成功")
    recognizedTexts: List[str] = Field(default_factory=list, description="识别的文字列表")
    matchedIngredients: List[Ingredient] = Field(default_factory=list, description="匹配到的成分")
    warnings: List[str] = Field(default_factory=list, description="警告信息(注意人群)")
    message: Optional[str] = Field(default=None, description="状态消息")
    unavailable: bool = Field(default=False, description="OCR 功能是否不可用（依赖缺失等）")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="版本号")
    timestamp: float = Field(..., description="时间戳")
