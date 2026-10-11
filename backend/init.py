"""
无界美妆后端 - 初始化脚本
验证环境配置
"""
import sys
import os

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    print(f"Python版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("⚠️ 警告: 推荐使用 Python 3.8+")
        return False
    return True

def check_dependencies():
    """检查依赖包"""
    required = ["fastapi", "uvicorn", "pydantic", "python_multipart"]
    optional = ["paddleocr", "paddlepaddle", "cv2"]
    
    print("\n=== 必需依赖 ===")
    all_ok = True
    for package in required:
        try:
            if package == "cv2":
                import cv2
            else:
                __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - 未安装")
            all_ok = False
    
    print("\n=== 可选依赖 (OCR) ===")
    for package in optional:
        try:
            if package == "cv2":
                import cv2
            elif package == "paddlepaddle":
                __import__("paddle")
            else:
                __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"⚠️ {package} - 未安装 (OCR功能不可用)")
    
    return all_ok

def check_data_files():
    """检查数据文件"""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    ingredients_file = os.path.join(data_dir, "ingredients.json")
    
    print("\n=== 数据文件 ===")
    if os.path.exists(ingredients_file):
        print(f"✅ ingredients.json 存在")
        # 验证JSON格式
        import json
        try:
            with open(ingredients_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"   包含 {len(data)} 个成分")
        except json.JSONDecodeError as e:
            print(f"❌ JSON格式错误: {e}")
            return False
    else:
        print(f"❌ ingredients.json 不存在")
        return False
    
    return True

def main():
    print("=" * 50)
    print("无界美妆后端环境检查")
    print("=" * 50)
    
    checks = [
        ("Python版本", check_python_version),
        ("依赖包", check_dependencies),
        ("数据文件", check_data_files)
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n[{name}]")
        results.append(check_func())
    
    print("\n" + "=" * 50)
    if all(results):
        print("✅ 环境检查通过!")
        print("\n启动服务: uvicorn main:app --reload --port 8000")
    else:
        print("⚠️ 部分检查未通过，但可以继续运行")
        print("\n安装依赖: pip install -r requirements.txt")
    print("=" * 50)

if __name__ == "__main__":
    main()
