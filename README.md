# 💎 晶体材料样品管理系统

本地 Web 应用，用于管理晶体生长实验所得样品的全部信息。

## 功能特性

- **样品管理** — 新建、查看、编辑、删除、搜索样品
- **基本信息** — 样品编号、目标产物、成功/失败、生长流程、结果、备注
- **元素质量计算** — 输入元素摩尔比 + 某元素质量，自动计算其余元素称量质量
- **实物照片** — 多张照片上传、缩略图网格、点击放大预览
- **EDX 能谱分析** — 上传 EDX 谱图 → 调用 GPT Vision API 自动识别元素成分
- **数据文件** — 上传/下载/删除 `.dat` 等数据文件

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python / Flask |
| 数据库 | SQLite |
| 前端 | HTML / CSS / JavaScript |
| AI 识别 | OpenAI 兼容 API (GPT-4o / Gemini) |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API（可选）

编辑 `config.py`，填写 EDX 识别所需的 API 信息：

```python
OPENAI_API_KEY = "your-api-key"
OPENAI_BASE_URL = "https://api.gptgod.online/v1/"  # 代理地址
OPENAI_MODEL = "gemini-3-pro-all"
```

### 3. 启动

```bash
python app.py
```

访问 http://127.0.0.1:5000

## 项目结构

```
crystal_manager/
├── app.py              # Flask 主应用 & API 路由
├── config.py           # 配置文件 (API Key, 代理, 路径)
├── models.py           # SQLite 数据库操作
├── molmass_data.py     # 元素摩尔质量数据
├── requirements.txt    # Python 依赖
├── templates/
│   └── index.html      # 前端页面
├── static/
│   ├── css/style.css   # 深色主题样式
│   └── js/app.js       # 前端逻辑
└── uploads/            # 上传文件目录 (自动创建)
    ├── photos/
    ├── edx/
    └── data/
```

## 元素质量计算公式

给定参考元素 A 的质量 `m_A`、摩尔比 `r_A`、摩尔质量 `M_A`，
计算元素 B 的质量：

```
m_B = m_A × (r_B / r_A) × (M_B / M_A)
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/samples?q=xxx` | 样品列表 & 搜索 |
| POST | `/api/samples` | 新建样品 |
| GET | `/api/samples/<id>` | 样品详情 |
| PUT | `/api/samples/<id>` | 更新样品 |
| DELETE | `/api/samples/<id>` | 删除样品 |
| POST | `/api/samples/<id>/photos` | 上传照片 |
| POST | `/api/samples/<id>/edx` | 上传 EDX 图片 |
| POST | `/api/edx/<id>/recognize` | AI 识别 EDX |
| POST | `/api/samples/<id>/datafiles` | 上传数据文件 |
| POST | `/api/calculate_mass` | 元素质量计算 |
