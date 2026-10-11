"""
无界美妆 - 成分知识库服务
"""
import json
from typing import List, Optional
from app.models import Ingredient


class IngredientStore:
    """成分知识库"""
    
    def __init__(self, data_path: str = "data/ingredients.json"):
        """
        初始化知识库
        
        Args:
            data_path: JSON数据文件路径
        """
        self.data_path = data_path
        self._ingredients: List[Ingredient] = []
        self._load_data()
    
    def _load_data(self):
        """加载数据"""
        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self._ingredients = [Ingredient(**item) for item in data]
    
    def reload(self):
        """重新加载数据"""
        self._load_data()
    
    def get_all(self) -> List[Ingredient]:
        """获取所有成分"""
        return self._ingredients.copy()
    
    def search(self, keyword: str, limit: int = 10) -> List[Ingredient]:
        """
        模糊搜索成分
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
        
        Returns:
            匹配的成分列表
        """
        if not keyword:
            return self._ingredients[:limit]
        
        keyword_lower = keyword.lower()
        matches = []
        
        for ing in self._ingredients:
            # 匹配名称（中英文）
            if (keyword_lower in ing.name.lower() or 
                keyword_lower in ing.nameZh.lower() or
                keyword_lower in ing.description.lower()):
                matches.append(ing)
                continue
            
            # 匹配类别
            if keyword_lower in ing.category.lower():
                matches.append(ing)
                continue
            
            # 匹配功效
            for benefit in ing.benefits:
                if keyword_lower in benefit.lower():
                    matches.append(ing)
                    break
        
        return matches[:limit]
    
    def get_by_id(self, ingredient_id: str) -> Optional[Ingredient]:
        """根据ID获取成分"""
        for ing in self._ingredients:
            if ing.id == ingredient_id:
                return ing
        return None
    
    def get_by_name(self, name: str) -> Optional[Ingredient]:
        """根据名称获取成分"""
        name_lower = name.lower()
        for ing in self._ingredients:
            if ing.name.lower() == name_lower or ing.nameZh.lower() == name_lower:
                return ing
        return None
    
    def check_caution(self, ingredient_name: str, skin_tags: List[str]) -> Optional[str]:
        """
        检查成分是否与用户肤质冲突
        
        Args:
            ingredient_name: 成分名称
            skin_tags: 用户肤质标签列表
        
        Returns:
            冲突警告信息，无冲突返回None
        """
        ingredient = self.get_by_name(ingredient_name)
        if not ingredient:
            return None
        
        skin_tags_lower = [tag.lower() for tag in skin_tags]
        
        for caution in ingredient.cautionGroups:
            if caution.lower() in skin_tags_lower:
                return f"{ingredient.nameZh}不适合{caution}肌肤使用"
        
        return None
