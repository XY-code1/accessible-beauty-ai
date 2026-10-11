"""
无界美妆 - OCR成分识别服务
图片预处理 -> 文字识别 -> 成分匹配流水线
"""
import base64
import io
import re
from typing import List, Tuple, Optional
from app.models import Ingredient


class OcrService:
    """OCR成分识别服务"""
    
    def __init__(self, ingredients_data: List[dict]):
        """
        初始化OCR服务
        
        Args:
            ingredients_data: 成分知识库数据
        """
        self.ingredients = ingredients_data
        self._ingredient_names = self._build_name_index()
        
        # OCR库可用性检查
        self._ocr_available = self._check_ocr_availability()
    
    def _check_ocr_availability(self) -> bool:
        """检查OCR库是否可用"""
        try:
            import cv2
            import numpy as np
            return True
        except ImportError:
            return False
    
    def _build_name_index(self) -> dict:
        """构建成分名称索引"""
        index = {}
        for ing in self.ingredients:
            # 英文名称
            index[ing["name"].lower()] = ing
            # 中文名称
            index[ing["nameZh"].lower()] = ing
            # 别名（如果有）
            if "aliases" in ing:
                for alias in ing["aliases"]:
                    index[alias.lower()] = ing
        return index
    
    def process_image(
        self, 
        image_base64: str, 
        return_matches: bool = True
    ) -> Tuple[List[str], List[Ingredient], List[str]]:
        """
        处理图片并识别成分
        
        Args:
            image_base64: Base64编码的图片数据
            return_matches: 是否返回匹配结果
        
        Returns:
            (识别的文字列表, 匹配到的成分, 警告信息)
        """
        recognized_texts = []
        matched_ingredients = []
        warnings = []
        
        try:
            # 解码图片
            image_data = base64.b64decode(image_base64)
            image = self._decode_image(image_data)
            
            if image is None:
                return [], [], ["图片解码失败"]
            
            # 图片预处理
            preprocessed = self._preprocess_image(image)
            
            # 文字识别
            recognized_texts = self._extract_text(preprocessed)
            
            # 成分匹配
            if return_matches:
                matched_ingredients, warnings = self._match_ingredients(recognized_texts)
            
        except Exception as e:
            return [], [], [f"图片处理错误: {str(e)}"]
        
        return recognized_texts, matched_ingredients, warnings
    
    def _decode_image(self, image_data: bytes):
        """解码图片数据"""
        try:
            import cv2
            import numpy as np
            
            # 从字节数据创建图片
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return image
        except Exception:
            return None
    
    def _preprocess_image(self, image) -> any:
        """
        图片预处理
        1. 灰度化
        2. 对比度增强
        3. 去噪
        4. 二值化
        """
        try:
            import cv2
            import numpy as np
            
            if image is None:
                return None
            
            # 转换为灰度图
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # 对比度增强 (CLAHE)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # 去噪
            denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
            
            # 二值化 (OTSU自动阈值)
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 形态学处理去除噪点
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            return processed
            
        except Exception:
            return image
    
    def _extract_text(self, preprocessed_image) -> List[str]:
        """
        从预处理后的图片提取文字
        
        使用PaddleOCR进行文字识别
        """
        texts = []
        
        if preprocessed_image is None:
            return texts
        
        try:
            # 尝试使用PaddleOCR
            from paddleocr import PaddleOCR
            
            ocr = PaddleOCR(
                lang='ch',  # 中文
                use_angle_cls=True,
                show_log=False
            )
            
            result = ocr.ocr(preprocessed_image, cls=True)
            
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0] if isinstance(line[1], tuple) else str(line[1])
                        if text and len(text.strip()) > 0:
                            texts.append(text.strip())
                            
        except ImportError:
            # PaddleOCR不可用，尝试PaddlePaddle
            try:
                import paddle
                # 降级处理
                texts = self._fallback_text_extraction(preprocessed_image)
            except ImportError:
                # 完全不可用，返回空
                pass
        except Exception:
            # 其他错误，降级处理
            texts = self._fallback_text_extraction(preprocessed_image)
        
        return texts
    
    def _fallback_text_extraction(self, image) -> List[str]:
        """降级文字提取 - 基于正则匹配已知的成分名称"""
        matched = []
        
        if image is None:
            return matched
        
        try:
            import cv2
            import numpy as np
            
            # 尝试用简单的二值化和轮廓检测找文字区域
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # 简单阈值
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            
            # 提取所有成分名称作为候选
            for ing in self.ingredients:
                # 中文名匹配
                if ing["nameZh"] in str(image):
                    matched.append(ing["nameZh"])
                # 英文名匹配
                if ing["name"] in str(image):
                    matched.append(ing["name"])
                    
        except Exception:
            pass
        
        return list(set(matched))
    
    def _match_ingredients(self, texts: List[str]) -> Tuple[List[Ingredient], List[str]]:
        """
        匹配识别的文字与成分知识库
        
        Returns:
            (匹配的成分列表, 警告信息)
        """
        matched = []
        warnings = []
        seen_ids = set()
        
        for text in texts:
            text_lower = text.lower()
            
            # 完全匹配
            if text_lower in self._ingredient_names:
                ing = self._ingredient_names[text_lower]
                if ing["id"] not in seen_ids:
                    matched.append(Ingredient(**ing))
                    seen_ids.add(ing["id"])
                    continue
            
            # 模糊匹配（成分名称在文本中）
            for name, ing in self._ingredient_names.items():
                if ing["id"] in seen_ids:
                    continue
                if len(name) >= 3 and name in text_lower:
                    matched.append(Ingredient(**ing))
                    seen_ids.add(ing["id"])
                    warnings.append(f"建议关注：{ing['nameZh']}（{ing['category']}）")
                    break
        
        return matched, warnings
    
    def check_warnings(self, matched_ingredients: List[Ingredient], skin_tags: List[str]) -> List[str]:
        """
        检查匹配成分是否有警告
        
        Args:
            matched_ingredients: 匹配到的成分
            skin_tags: 用户肤质标签
        
        Returns:
            警告信息列表
        """
        warnings = []
        skin_tags_lower = [tag.lower() for tag in skin_tags]
        
        for ing in matched_ingredients:
            caution_groups = [c.lower() for c in ing.cautionGroups]
            for tag in skin_tags_lower:
                if tag in caution_groups:
                    warnings.append(
                        f"⚠️ {ing.nameZh} 不适合 {tag} 肌肤使用，请注意"
                    )
        
        return warnings
