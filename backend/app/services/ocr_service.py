"""
无界美妆 - OCR成分识别服务
图片预处理 -> 文字识别 -> 成分匹配 -> 肤质警告
"""
import base64
from dataclasses import dataclass
from io import BytesIO
import logging
import threading
import warnings as python_warnings
from typing import List, Optional, Tuple
from PIL import Image, UnidentifiedImageError
from app.models import Ingredient


logger = logging.getLogger(__name__)
MAX_IMAGE_PIXELS = 16_000_000

# 置信度阈值：低于该阈值的文字识别结果将被丢弃
MIN_RECOGNITION_CONFIDENCE = 0.5
# 模糊匹配时，最小关键字长度（避免误匹配过短字符）
MIN_FUZZY_KEYWORD_LENGTH = 3


class ImageTooLargeError(ValueError):
    """图片像素数量超过限制。"""


@dataclass
class OcrResult:
    """OCR 识别结果"""
    texts: List[str]
    matched: List[Ingredient]
    warnings: List[str]
    success: bool = True
    unavailable: bool = False
    message: Optional[str] = None


class OcrUnavailableError(RuntimeError):
    """OCR依赖或识别过程不可用。"""


class OcrService:
    """OCR成分识别服务

    三级流水线：
    1. 图像预处理：倾斜校正 -> 对比度增强 -> 自适应二值化 -> 边缘裁剪去噪
    2. 文字识别：调用 PaddleOCR 提取文字 + 置信度过滤
    3. 成分匹配：与知识库做模糊匹配并结合肤质标签生成警告
    """

    def __init__(self, ingredients_data: List[dict]):
        self.ingredients = ingredients_data
        self._ingredient_names = self._build_name_index()
        self._ocr_engine = None
        self._ocr_engine_lock = threading.Lock()
        self._ocr_inference_lock = threading.Lock()
        self._ocr_available = self._check_ocr_availability()

    # ------------------------------------------------------------------
    # 可用性检查
    # ------------------------------------------------------------------
    def _check_ocr_availability(self) -> bool:
        """检查 OpenCV + numpy 是否可用（PaddleOCR 延迟到首次调用再校验）"""
        try:
            import cv2  # noqa: F401
            import numpy as np  # noqa: F401
            return True
        except ImportError:
            return False

    def is_available(self) -> bool:
        """返回服务是否处于可用状态，供路由在依赖未安装时给出明确提示"""
        return self._ocr_available

    def _build_name_index(self) -> dict:
        """构建成分名称索引（中英文 + 别名）"""
        index: dict = {}
        for ing in self.ingredients:
            index[ing["name"].lower()] = ing
            index[ing["nameZh"].lower()] = ing
            if "aliases" in ing and isinstance(ing["aliases"], list):
                for alias in ing["aliases"]:
                    if isinstance(alias, str):
                        index[alias.lower()] = ing
        return index

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def process_image(
        self,
        image_base64: str,
        return_matches: bool = True,
        skin_tags: Optional[List[str]] = None,
    ) -> OcrResult:
        """处理图片并识别成分

        Args:
            image_base64: Base64 编码的图片数据
            return_matches: 是否返回成分匹配结果
            skin_tags: 用户肤质标签列表，命中成分 cautionGroups 时会生成警告

        Returns:
            OcrResult 包含文字、成分、警告信息和成功状态
        """
        if not self._ocr_available:
            return OcrResult(
                texts=[],
                matched=[],
                warnings=[],
                success=False,
                unavailable=True,
                message="OCR_FEATURE_UNAVAILABLE: OCR 功能依赖未安装，请联系管理员安装 paddleocr / paddlepaddle / opencv-python",
            )

        recognized_texts: List[str] = []
        matched_ingredients: List[Ingredient] = []
        warnings: List[str] = []

        try:
            image_data = base64.b64decode(image_base64)

            # 只读取图片元信息进行像素数预检，避免巨大图片占用内存
            try:
                with python_warnings.catch_warnings():
                    python_warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(BytesIO(image_data), formats=("PNG", "JPEG", "WEBP")) as metadata:
                        if metadata.width * metadata.height > MAX_IMAGE_PIXELS:
                            raise ImageTooLargeError("图片超过 1600 万像素限制")
            except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
                raise ImageTooLargeError("图片超过 1600 万像素限制") from exc
            except (UnidentifiedImageError, OSError):
                return OcrResult([], [], ["图片解码失败"], success=False,
                                 message="OCR_IMAGE_INVALID: 图片格式无法识别，请上传 PNG/JPEG/WebP 图片")

            image = self._decode_image(image_data)
            if image is None:
                return OcrResult([], [], ["图片解码失败"], success=False,
                                 message="OCR_IMAGE_INVALID: 图片格式无法识别，请上传 PNG/JPEG/WebP 图片")

            preprocessed = self._preprocess_image(image)
            recognized_texts = self._extract_text(preprocessed)

            if return_matches:
                matched_ingredients, warnings = self._match_ingredients(recognized_texts)
                if skin_tags:
                    warnings.extend(self.check_warnings(matched_ingredients, skin_tags))

        except ImageTooLargeError:
            raise
        except OcrUnavailableError:
            return OcrResult([], [], ["OCR不可用"], success=False, unavailable=True,
                             message="OCR_FEATURE_UNAVAILABLE: OCR 引擎初始化失败，请确认 paddleocr 已正确安装")
        except Exception:
            logger.exception("Image processing failed")
            return OcrResult([], [], ["IMAGE_PROCESS_FAILED: 图片处理失败，请稍后重试"],
                             success=False,
                             message="OCR_PROCESS_FAILED: OCR处理失败，请稍后重试")

        return OcrResult(recognized_texts, matched_ingredients, warnings)

    # ------------------------------------------------------------------
    # 图像预处理
    # ------------------------------------------------------------------
    def _decode_image(self, image_data: bytes):
        """用 OpenCV 解码图片字节流"""
        try:
            import cv2
            import numpy as np

            nparr = np.frombuffer(image_data, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception:
            return None

    def _preprocess_image(self, image) -> any:
        """图像预处理流水线

        1. 灰度化
        2. 估算文本方向 -> 倾斜校正（>0.5° 才校正）
        3. 自适应 CLAHE 对比度增强
        4. 自适应二值化（高斯）
        5. 形态学去噪 + 自动裁剪白边
        """
        try:
            import cv2
            import numpy as np

            if image is None:
                return None

            # 1) 灰度化
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            # 2) 倾斜校正：使用 Hough 变换估算倾斜角
            try:
                edges = cv2.Canny(gray, 80, 200)
                lines = cv2.HoughLines(edges, 1, np.pi / 360, threshold=120)
                if lines is not None and len(lines) > 0:
                    angles = []
                    for line in lines[:50]:
                        rho, theta = line[0]
                        angle = (theta * 180 / np.pi) - 90
                        if -45 < angle < 45:
                            angles.append(angle)
                    if angles:
                        median_angle = float(np.median(angles))
                        if abs(median_angle) > 0.5:
                            h, w = gray.shape
                            matrix = cv2.getRotationMatrix2D((w / 2, h / 2), median_angle, 1.0)
                            gray = cv2.warpAffine(
                                gray, matrix, (w, h),
                                flags=cv2.INTER_CUBIC,
                                borderMode=cv2.BORDER_REPLICATE,
                            )
            except Exception:
                # 倾斜校正失败时回退到原灰度图
                pass

            # 3) 对比度增强（CLAHE）
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)

            # 4) 自适应二值化（高斯）
            binary = cv2.adaptiveThreshold(
                enhanced, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=31,
                C=10,
            )

            # 5) 形态学去噪
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

            # 6) 自动裁剪白边
            processed = self._trim_white_borders(processed)

            return processed

        except Exception:
            return image

    def _trim_white_borders(self, image) -> any:
        """裁掉图片四周的大面积白边，提升 OCR 召回"""
        try:
            import cv2
            import numpy as np

            if image is None or image.size == 0:
                return image

            # 找二值化图片中深色内容的边界
            mask = image < 128
            if not np.any(mask):
                return image
            coords = cv2.findNonZero(mask.astype(np.uint8) * 255)
            if coords is None:
                return image
            x, y, w, h = cv2.boundingRect(coords)
            # 留 2 像素 padding 防止裁掉笔画
            pad = 2
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(image.shape[1], x + w + pad)
            y1 = min(image.shape[0], y + h + pad)
            return image[y0:y1, x0:x1]
        except Exception:
            return image

    # ------------------------------------------------------------------
    # 文字识别
    # ------------------------------------------------------------------
    def _extract_text(self, preprocessed_image) -> List[str]:
        """使用 PaddleOCR 提取文字并按置信度过滤"""
        if preprocessed_image is None:
            return []

        engine = self._get_ocr_engine()

        try:
            with self._ocr_inference_lock:
                result = engine.ocr(preprocessed_image, cls=True)
        except Exception:
            raise OcrUnavailableError("OCR不可用")

        texts: List[str] = []
        if not result or not result[0]:
            return texts

        for line in result[0]:
            if not line or len(line) < 2:
                continue
            # PaddleOCR 返回格式: ((box, (text, conf)), ...)
            try:
                payload = line[1]
                text, conf = (payload[0], payload[1]) if isinstance(payload, (list, tuple)) else (str(payload), 1.0)
            except Exception:
                continue
            if not text or not text.strip():
                continue
            if conf is not None and conf < MIN_RECOGNITION_CONFIDENCE:
                continue
            texts.append(text.strip())

        return texts

    def _get_ocr_engine(self):
        """Lazily create and reuse one PaddleOCR engine per service process"""
        if self._ocr_engine is None:
            with self._ocr_engine_lock:
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

    # ------------------------------------------------------------------
    # 成分匹配 & 肤质警告
    # ------------------------------------------------------------------
    def _match_ingredients(self, texts: List[str]) -> Tuple[List[Ingredient], List[str]]:
        """将识别文字与知识库做模糊匹配，返回成分列表与建议信息"""
        matched: List[Ingredient] = []
        warnings: List[str] = []
        seen_ids: set = set()

        for text in texts:
            text_lower = text.lower()
            text_stripped = text.replace(" ", "")

            # 1) 完全匹配
            candidate = (
                self._ingredient_names.get(text_lower)
                or self._ingredient_names.get(text_stripped.lower())
            )
            if candidate and candidate["id"] not in seen_ids:
                matched.append(Ingredient(**candidate))
                seen_ids.add(candidate["id"])
                warnings.append(f"识别到：{candidate['nameZh']}（{candidate['category']}）")
                continue

            # 2) 模糊匹配：成分名出现在识别文本中
            for name, ing in self._ingredient_names.items():
                if ing["id"] in seen_ids:
                    continue
                if len(name) < MIN_FUZZY_KEYWORD_LENGTH:
                    continue
                if name in text_lower or name in text_stripped.lower():
                    matched.append(Ingredient(**ing))
                    seen_ids.add(ing["id"])
                    warnings.append(f"建议关注：{ing['nameZh']}（{ing['category']}）")
                    break

        return matched, warnings

    def check_warnings(self, matched_ingredients: List[Ingredient], skin_tags: List[str]) -> List[str]:
        """根据肤质标签与成分 cautionGroups 生成警告"""
        warnings: List[str] = []
        if not skin_tags:
            return warnings

        skin_tags_lower = [str(tag).lower().strip() for tag in skin_tags if tag]
        if not skin_tags_lower:
            return warnings

        for ing in matched_ingredients:
            caution_groups = [str(c).lower() for c in ing.cautionGroups]
            for tag in skin_tags_lower:
                if tag in caution_groups:
                    warnings.append(
                        f"⚠️ {ing.nameZh} 不适合 {tag} 肌肤使用，请注意"
                    )
                    break
        return warnings
