# 无界美妆后端服务

无障碍美妆AI项目的后端服务模块，提供眉妆推荐闭环与公共接口。

## 技术栈

- **框架**: FastAPI
- **数据验证**: Pydantic v2
- **知识库**: 本地JSON存储
- **OCR**: PaddleOCR + OpenCV (可选)

## 项目结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI应用入口
│   ├── models.py            # 数据模型定义
│   ├── api/                 # API路由
│   │   ├── __init__.py
│   │   ├── intent.py        # 意图识别接口
│   │   ├── plan.py          # 方案生成接口
│   │   ├── ingredient.py    # 成分查询接口
│   │   └── ocr.py           # OCR识别接口
│   └── services/            # 服务层
│       ├── __init__.py
│       ├── plan_engine.py    # 眉妆规则引擎
│       ├── knowledge_base.py # 成分知识库
│       └── ocr_service.py   # OCR服务
├── data/
│   └── ingredients.json     # 成分知识库数据
├── main.py                  # 应用入口
├── requirements.txt         # 依赖列表
└── init.py                  # 环境初始化脚本
```

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. OCR功能（可选）

如需使用OCR成分识别功能，需要安装额外依赖：

```bash
pip install paddleocr paddlepaddle opencv-python numpy
```

### 3. 启动服务

```bash
# 开发模式
uvicorn main:app --reload --port 8000

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. 验证服务

- 健康检查: http://localhost:8000/health
- API文档: http://localhost:8000/docs
- ReDoc文档: http://localhost:8000/redoc

### 5. 运行后端契约测试

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

## 接口列表

| 接口 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/intent` | POST | 意图识别 |
| `/api/plan` | POST | 方案生成 |
| `/api/ingredient` | GET | 成分查询 |
| `/api/ingredient/all` | GET | 所有成分 |
| `/api/ingredient/{id}` | GET | 成分详情 |
| `/api/ocr/ingredient` | POST | OCR成分识别 |
| `/api/ocr/ingredient/file` | POST | OCR文件上传 |

OCR图片大小上限为10 MiB；JSON请求按Base64解码后的大小计算，文件上传按文件字节数计算，超限返回HTTP 413。
图片另有1600万像素上限，两种接口均在解码像素及预处理前检查，超限返回HTTP 413。OCR不可用时返回HTTP 200，响应中 `success` 为 `false`，并保留 `OCR不可用` 警告。

## 自测指南

详见下文 `自测说明.md`

## 数据模型

### BeautyParameters

| 字段 | 类型 | 描述 |
|------|------|------|
| scene | Scene | 使用场景 (daily/work/party/date) |
| style | Style | 妆效风格 (natural/matte/glow/bold) |
| intensity | Intensity | 浓度偏好 (light/medium/full) |
| side | Side | 侧别 (left/right, 可选) |

### PlanStep

| 字段 | 类型 | 描述 |
|------|------|------|
| step | Step | 步骤类型 |
| name | str | 步骤名称 |
| duration | int | 预估时长(秒) |
| essential | bool | 是否必要 |
| omittedReason | str | 省略理由 |
| replacedBy | str | 替换原因 |
| products | List[str] | 推荐产品 |
| tips | List[str] | 操作提示 |

### Ingredient

| 字段 | 类型 | 描述 |
|------|------|------|
| id | str | 成分ID |
| name | str | 英文名称 |
| nameZh | str | 中文名称 |
| category | str | 类别 |
| description | str | 描述 |
| benefits | List[str] | 功效 |
| cautionGroups | List[str] | 注意人群 |

## 开发说明

### 添加新成分

编辑 `data/ingredients.json`，添加新的成分对象：

```json
{
  "id": "ing_xxx",
  "name": "Ingredient Name",
  "nameZh": "成分名称",
  "category": "类别",
  "description": "描述",
  "benefits": ["功效1", "功效2"],
  "cautionGroups": ["注意人群标签"]
}
```

### 添加新步骤

编辑 `app/services/plan_engine.py` 中的 `ALL_STEPS_CONFIG` 字典。

### 添加成分替换规则

编辑 `app/services/plan_engine.py` 中的 `SKIN_TAG_REPLACEMENTS` 字典。

## 许可证

MIT License
