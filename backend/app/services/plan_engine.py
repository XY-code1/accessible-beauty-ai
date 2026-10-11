"""
无界美妆 - 眉妆推荐规则引擎
三层规则：基础步骤映射 -> 最低复杂度裁剪 -> 成分触发替换
"""
from typing import List, Dict, Tuple, Optional
from app.models import (
    BeautyParameters, BeautyProfile, PlanStep, Step, Scene, Style, Intensity
)


# ==================== 基础步骤配置 ====================

# 完整眉妆步骤定义
ALL_STEPS_CONFIG = {
    Step.SETUP: {
        "name": "眉部准备",
        "duration": 60,
        "essential": True,
        "products": ["眉梳", "棉签"],
        "tips": ["用眉梳顺着眉毛生长方向梳理", "如有需要可用棉签清理杂毛"]
    },
    Step.SHAPE: {
        "name": "修整眉形",
        "duration": 120,
        "essential": True,
        "products": ["眉刀", "眉镊", "眉剪"],
        "tips": ["根据脸型选择适合的眉形", "不要过度修整保持自然感"]
    },
    Step.FILL: {
        "name": "眉粉填充",
        "duration": 90,
        "essential": True,
        "products": ["眉粉", "眉刷"],
        "tips": ["从眉头到眉尾由浅入深", "少量多次避免下手过重"]
    },
    Step.DEFINE: {
        "name": "勾勒轮廓",
        "duration": 60,
        "essential": True,
        "products": ["眉笔", "眉胶"],
        "tips": ["用眉笔填补眉毛空隙", "眉胶可打造立体持久效果"]
    },
    Step.SET: {
        "name": "定妆持妆",
        "duration": 30,
        "essential": True,
        "products": ["眉膏", "眉毛雨衣"],
        "tips": ["轻扫眉粉定妆", "可用眉毛雨衣防水防脱"]
    }
}

# 场景适配：是否需要勾勒轮廓
SCENE_NEED_DEFINE: Dict[Scene, bool] = {
    Scene.DAILY: False,   # 日常不需要精细勾勒
    Scene.WORK: True,     # 职场需要精致
    Scene.PARTY: True,    # 派对需要立体
    Scene.DATE: False,    # 约会自然即可
}

# 风格适配：步骤调整
STYLE_STEP_MODIFIERS: Dict[Style, Dict[Step, str]] = {
    Style.NATURAL: {
        Step.FILL: "使用浅色眉粉轻扫",
        Step.DEFINE: "省略精细勾勒，保持自然毛流感"
    },
    Style.MATTE: {
        Step.FILL: "使用哑光眉粉",
        Step.DEFINE: "哑光眉笔勾勒"
    },
    Style.GLOW: {
        Step.FILL: "带微光的眉粉提亮",
        Step.DEFINE: "可用染眉膏增加光泽"
    },
    Style.BOLD: {
        Step.FILL: "深色眉粉填充饱满",
        Step.DEFINE: "明确勾勒轮廓线条"
    }
}

# 浓度适配：每步时长调整
INTENSITY_DURATION_MODIFIER: Dict[Intensity, float] = {
    Intensity.LIGHT: 0.7,   # 淡妆缩短时长
    Intensity.MEDIUM: 1.0,  # 标准时长
    Intensity.FULL: 1.3,   # 浓妆增加时长
}

# ==================== 省略理由定义 ====================

OMISSION_REASONS = {
    Step.SHAPE: {
        "already_perfect": "眉毛形状已完美，无需修整",
        "recently_shaped": "近期已修整眉形",
        "sensitive_skin": "敏感肌肤避免过度刺激"
    },
    Step.DEFINE: {
        "daily_scene": "日常场景适合自然眉妆",
        "natural_style": "自然风格无需精细勾勒",
        "light_intensity": "淡妆避免线条过重"
    },
    Step.SET: {
        "oily_skin": "油性肌肤避免过多产品叠加",
        "short_time": "时间紧迫简化步骤"
    }
}


# ==================== 成分替换规则 ====================

# 肤质标签 -> 替换成分映射
SKIN_TAG_REPLACEMENTS: Dict[str, Dict[str, str]] = {
    "sensitive": {
        "talc": "云母(更温和)",  # Talc -> Mica
        "salicylic_acid": "温和果酸",
        "phenoxyethanol": "天然防腐体系"
    },
    "dry": {
        "kaolin": "保湿霜或精华底妆",  # Kaolin -> 保湿产品
        "silica": "滋润型眉部产品"
    },
    "oily": {
        "beeswax": "清爽定型凝胶",  # Beeswax -> 清爽产品
        "castor_oil": "清爽配方"
    },
    "acne": {
        "talc": "无油配方",  # Talc可能堵塞毛孔
        "heavy_oils": "轻薄养肤成分"
    }
}

# 步骤 -> 可能触发替换的产品成分
STEP_INGREDIENT_CAUTIONS: Dict[Step, List[str]] = {
    Step.SHAPE: ["talc"],      # 修眉可能刺激
    Step.FILL: ["talc", "kaolin"],  # 粉类可能干燥
    Step.DEFINE: ["phenoxyethanol"],  # 某些人对防腐剂敏感
    Step.SET: ["beeswax"]      # 浓稠定型可能闷痘
}


# ==================== 规则引擎实现 ====================

class PlanEngine:
    """眉妆推荐规则引擎"""
    
    def __init__(self, ingredients_data: List[Dict]):
        """
        初始化规则引擎
        
        Args:
            ingredients_data: 成分知识库数据
        """
        self.ingredients = ingredients_data
        self.ingredient_map = {ing["name"].lower(): ing for ing in ingredients_data}
    
    def generate_plan(
        self, 
        params: BeautyParameters, 
        profile: Optional[BeautyProfile] = None
    ) -> Tuple[List[PlanStep], int, int]:
        """
        生成眉妆方案
        
        Args:
            params: 美妆参数
            profile: 用户画像（可选）
        
        Returns:
            (步骤列表, 总时长, 省略步骤数)
        """
        # 第一层：生成基础步骤
        steps = self._layer1_base_steps(params)
        
        # 第二层：最低复杂度裁剪
        steps = self._layer2_minimal_pruning(steps, params, profile)
        
        # 第三层：成分触发替换
        steps = self._layer3_ingredient_replacement(steps, profile)
        
        # 计算总时长
        total_duration = sum(s.duration for s in steps)
        
        # 统计省略步骤数
        omitted_count = sum(1 for s in steps if not s.essential)
        
        return steps, total_duration, omitted_count
    
    def _layer1_base_steps(self, params: BeautyParameters) -> List[PlanStep]:
        """第一层：基础步骤映射"""
        steps = []
        
        for step_type, config in ALL_STEPS_CONFIG.items():
            # 应用浓度时长调整
            duration_modifier = INTENSITY_DURATION_MODIFIER.get(params.intensity, 1.0)
            adjusted_duration = int(config["duration"] * duration_modifier)
            
            # 应用风格提示调整
            tips = config["tips"].copy()
            if step_type in STYLE_STEP_MODIFIERS.get(params.style, {}):
                style_tip = STYLE_STEP_MODIFIERS[params.style][step_type]
                tips = [style_tip]
            
            step = PlanStep(
                step=step_type,
                name=config["name"],
                duration=adjusted_duration,
                essential=config["essential"],
                omittedReason=None,
                replacedBy=None,
                products=config["products"].copy(),
                tips=tips
            )
            steps.append(step)
        
        return steps
    
    def _layer2_minimal_pruning(
        self, 
        steps: List[PlanStep],
        params: BeautyParameters,
        profile: Optional[BeautyProfile]
    ) -> List[PlanStep]:
        """第二层：最低复杂度裁剪"""
        pruned_steps = []
        
        for step in steps:
            step = step.model_copy()
            
            # 场景相关裁剪
            if step.step == Step.DEFINE and not SCENE_NEED_DEFINE.get(params.scene, True):
                step.essential = False
                step.omittedReason = OMISSION_REASONS.get(Step.DEFINE, {}).get(
                    "daily_scene" if params.scene == Scene.DAILY else "natural_style",
                    "场景不需要精细勾勒"
                )
            
            # 风格相关裁剪
            if params.style == Style.NATURAL and step.step == Step.DEFINE:
                if not step.omittedReason:  # 尚未被裁剪
                    step.essential = False
                    step.omittedReason = OMISSION_REASONS[Step.DEFINE]["natural_style"]
            
            # 浓度相关裁剪
            if params.intensity == Intensity.LIGHT and step.step == Step.DEFINE:
                if not step.omittedReason:
                    step.essential = False
                    step.omittedReason = OMISSION_REASONS[Step.DEFINE]["light_intensity"]
            
            # 肤质相关裁剪
            if profile:
                if profile.skinType.lower() in ["sensitive"] and step.step == Step.SHAPE:
                    step.essential = False
                    step.omittedReason = OMISSION_REASONS[Step.SHAPE]["sensitive_skin"]
                
                if profile.skinType.lower() in ["oily"] and step.step == Step.SET:
                    # 保持essential但提示精简
                    pass  # 不省略，只在后续调整产品
            
            pruned_steps.append(step)
        
        return pruned_steps
    
    def _layer3_ingredient_replacement(
        self,
        steps: List[PlanStep],
        profile: Optional[BeautyProfile]
    ) -> List[PlanStep]:
        """第三层：成分触发替换"""
        if not profile or not profile.skinTags:
            return steps
        
        replaced_steps = []
        skin_tags = [tag.lower() for tag in profile.skinTags]
        
        for step in steps:
            step = step.model_copy()
            
            # 检查该步骤涉及的成分
            cautions = STEP_INGREDIENT_CAUTIONS.get(step.step, [])
            
            for caution in cautions:
                # 检查知识库中是否有该成分及其注意人群
                for ing in self.ingredients:
                    if caution in ing["name"].lower() or caution in ing.get("nameZh", "").lower():
                        ing_cautions = [c.lower() for c in ing.get("cautionGroups", [])]
                        
                        # 检查用户肤质标签是否匹配注意人群
                        for skin_tag in skin_tags:
                            if skin_tag in ing_cautions:
                                # 触发替换
                                step.replacedBy = f"建议替换含{ing['nameZh']}的产品，使用更温和的替代成分"
                                step.tips.append(f"注意：{ing['nameZh']}可能不适合您的肤质")
                                break
                        break
            
            replaced_steps.append(step)
        
        return replaced_steps


# ==================== 意图识别引擎 ====================

class IntentEngine:
    """意图识别引擎 - 标签映射"""
    
    # 自然语言 -> 场景映射
    SCENE_KEYWORDS = {
        "daily": ["日常", "上班", "上学", "出门", "普通"],
        "work": ["职场", "面试", "商务", "正式", "工作"],
        "party": ["派对", "聚会", "夜店", "蹦迪", "party"],
        "date": ["约会", "相亲", "见面", "浪漫"]
    }
    
    # 自然语言 -> 风格映射
    STYLE_KEYWORDS = {
        "natural": ["自然", "裸妆", "清淡", "日常", "简单"],
        "matte": ["哑光", "雾面", "高级", "质感"],
        "glow": ["缎光", "光泽", "水光", "亮面", "闪"],
        "bold": ["立体", "浓", "重", "明显", "精致"]
    }
    
    # 自然语言 -> 浓度映射
    INTENSITY_KEYWORDS = {
        "light": ["淡", "轻", "少", "浅", "自然"],
        "medium": ["中", "一般", "适度"],
        "full": ["浓", "重", "全", "多", "深"]
    }
    
    def parse(self, query: str) -> Tuple[Optional[BeautyParameters], float]:
        """
        解析用户查询生成美妆参数
        
        Args:
            query: 用户自然语言输入
        
        Returns:
            (美妆参数, 置信度)
        """
        query_lower = query.lower()
        scores = {
            category: {
                value: sum(kw in query_lower for kw in keywords)
                for value, keywords in keywords_map.items()
            }
            for category, keywords_map in (
                ("scene", self.SCENE_KEYWORDS),
                ("style", self.STYLE_KEYWORDS),
                ("intensity", self.INTENSITY_KEYWORDS),
            )
        }
        
        # 计算总匹配度
        total_matches = sum(sum(value_scores.values()) for value_scores in scores.values())
        confidence = min(total_matches / 3.0, 1.0)  # 归一化
        
        # 如果匹配度太低，使用默认值
        if confidence < 0.3:
            return None, confidence
        
        # 确定参数值
        scene = self._get_best_match(scores["scene"])
        style = self._get_best_match(scores["style"])
        intensity = self._get_best_match(scores["intensity"])
        
        params = BeautyParameters(
            scene=Scene(scene or "daily"),
            style=Style(style or "natural"),
            intensity=Intensity(intensity or "medium")
        )
        
        return params, confidence
    
    def _get_best_match(
        self, 
        scores: Dict[str, int]
    ) -> Optional[str]:
        """选择得分最高的值；同分时按值的字典序升序选择。"""
        if not scores or max(scores.values()) == 0:
            return None

        return min(scores, key=lambda value: (-scores[value], value))
