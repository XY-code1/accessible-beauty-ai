"""
无界美妆 - OCR成分识别服务
图片预处理 -> 文字识别 -> 成分匹配流水线
"""
import base64
from dataclasses import dataclass
from io import BytesIO
import logging
import warnings as python_warnings
from typing import List, Tuple
from PIL import Image, UnidentifiedImageError
from app.models import Ingredient


logger = logging.getLogger(__name__)
MAX_IMAGE_PIXELS = 16_000_000


class ImageTooLargeError(ValueError):
    """图片像素数量超过限制。"""


@dataclass
class OcrResult:
    texts: List[str]
    matched: List[Ingredient]
    warnings: List[str]
    success: bool = True


class OcrUnavailableError(RuntimeError):
    """OCR依赖或识别过程不可用。"""


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
        self._ocr_engine = None
        
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
    ) -> OcrResult:
        """
        处理图片并识别成分
        
        Args:
            image_base64: Base64编码的图片数据
            return_matches: 是否返回匹配结果
        
        Returns:
            识别结果，包含文字、成分、警告信息和成功状态
        """
        recognized_texts = []
        matched_ingredients = []
        warnings = []
        
        try:
            # 解码图片
            image_data = base64.b64decode(image_base64)
            # 只读取图片头中的尺寸，超限时不解码像素。
            try:
                with python_warnings.catch_warnings():
                    python_warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(BytesIO(image_data), formats=("PNG", "JPEG", "WEBP")) as metadata:
                        if metadata.width * metadata.height > MAX_IMAGE_PIXELS:
                            raise ImageTooLargeError("图片超过 1600 万像素限制")
            except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
                raise ImageTooLargeError("图片超过 1600 万像素限制") from exc
            except (UnidentifiedImageError, OSError):
                return OcrResult([], [], ["图片解码失败"], success=False)
            image = self._decode_image(image_data)
            
            if image is None:
                return OcrResult([], [], ["图片解码失败"], success=False)
            
            # 图片预处理
            preprocessed = self._preprocess_image(image)
            
            # 文字识别
            recognized_texts = self._extract_text(preprocessed)
            
            # 成分匹配
            if return_matches:
                matched_ingredients, warnings = self._match_ingredients(recognized_texts)
            
        except ImageTooLargeError:
            raise
        except OcrUnavailableError:
            return OcrResult([], [], ["OCR不可用"], success=False)
        except Exception:
            logger.exception("Image processing failed")
            return OcrResult([], [], ["IMAGE_PROCESS_FAILED: 图片处理失败，请稍后重试"], success=False)
        
        return OcrResult(recognized_texts, matched_ingredients, warnings)
    
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
            result = self._get_ocr_engine().ocr(preprocessed_image, cls=True)
            
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0] if isinstance(line[1], tuple) else str(line[1])
                        if text and len(text.strip()) > 0:
                            texts.append(text.strip())
                            
        except Exception as e:
            raise OcrUnavailableError("OCR不可用") from e
        
        return texts

    def _get_ocr_engine(self):
        """Lazily create and reuse one PaddleOCR engine per service process."""
        if self._ocr_engine is None:
            try:
                from paddleocr import PaddleOCR

                self._ocr_engine = PaddleOCR(
                    lang="ch",
                    use_angle_cls=True,
                    show_log=False,
                )
            except Exception as exc:
                raise OcrUnavailableError("OCR不可用") from exc
        return self._ocr_engine
    
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
