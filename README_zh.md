# 💎 晶体材料样品管理系统 (Crystal Material Sample Management System)

[English](README.md)

本地 Web 应用，用于管理晶体生长实验所得样品的全部信息。

## 功能特性

- **样品管理** — 新建、查看、编辑、删除、按状态及参数搜索样品
- **基本信息** — 样品编号、目标产物、状态（成功/失败/待定/生长中）、专属测量标记（电学/磁性）、生长流程与烧制时间记录、结果、备注
- **快捷导航与体验** — 极速的前后样品切换、文本框高度自适应、智能避免自动滚动，及支持保留参考元素的快速复制功能
- **元素质量计算** — 直观展示当前计算环境（样品ID/产物）；输入元素摩尔比和某参考元素质量，自动计算其余元素称量质量
- **实物照片** — 多张照片上传（支持拍照）、自动生成缩略图（按需加载）、点击放大预览原图、原生文件名还原下载
- **EDX 能谱分析** — 上传 EDX 谱图生成缩略图 → 调用 GPT Vision API 自动识别元素成分
- **数据与附件区** — 支持上传/下载 `.dat/.csv/.txt` 等实验数据文件以及不限格式的其他附件，完美还原原始文件名
- **Microsoft To Do 深度集成** — 绑定微软账户，自动同步样品的烧制结束时间，实现高效的多端到期提醒
- **双语与响应式设计** — 支持中英文 (i18n) 动态无缝切换；为手机、平板深度优化的独立排版结构和交互体验；提供全屏的宽屏浏览模式
- **自动备份** — 启动时立即备份 + 自动增量定时热备，配套命令行极速恢复工具

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python / Flask / Pillow (缩略图处理) |
| 数据库 | SQLite |
| 前端 | HTML / CSS / JavaScript |
| AI 识别 | OpenAI 兼容 API (GPT-4o / Gemini) |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 创建配置文件

复制 `config.py.example` 为 `config.py`，并填入你自己的密码和 API Key：

```bash
cp config.py.example config.py
```

然后编辑 `config.py`，修改以下内容：

```python
LOGIN_PASSWORD = "your-password"                # 登录密码
APP_PORT = 5000                                 # 服务端口
OPENAI_API_KEY = "sk-your-api-key"              # EDX 识别用 API Key
OPENAI_BASE_URL = "https://api.openai.com/v1/"  # 代理地址
OPENAI_MODEL = "gpt-4o"                         # 模型名称
```

### 3. 启动

```bash
python app.py
```

访问 http://127.0.0.1:5000 ，输入密码登录。

## 项目结构

```
crystal_manager/
├── app.py              # Flask 主应用 & API 路由
├── config.py.example   # 配置文件模板 (复制为 config.py 使用)
├── models.py           # SQLite 数据库操作
├── backup.py           # 增量备份 & 定时调度器
├── restore_backup.py   # 命令行备份恢复工具
├── migrate_storage.py  # 文件存储结构迁移工具
├── molmass_data.py     # 元素摩尔质量数据
├── requirements.txt    # Python 依赖
├── templates/
│   ├── index.html      # 主页面
│   └── login.html      # 登录页面
├── static/
│   ├── css/style.css   # 亮色主题样式
│   └── js/app.js       # 前端逻辑
├── uploads/            # 上传文件目录 (按样品编号组织)
│   └── <样品编号>/
│       ├── photos/
│       ├── edx/
│       ├── data/
│       └── others/
└── backups/            # 备份目录 (自动创建)
    ├── manifest.json   # 增量备份清单
    └── <时间戳>/
        ├── db.sqlite       # 数据库快照
        ├── files/          # 增量文件
        └── backup_info.json
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
| POST | `/api/samples/<id>/otherfiles`| 上传其他文件 |
| POST | `/api/calculate_mass` | 元素质量计算 |

## 备份与恢复

### 自动备份

应用启动时自动执行一次备份，之后每隔固定时间自动增量备份。

**备份内容：**
- 数据库完整快照（使用 SQLite Online Backup API，安全热备份）
- 上传文件增量备份（通过 manifest.json 跟踪文件变化，只备份新增/修改的文件）

**配置 (`config.py`):**
```python
BACKUP_INTERVAL_HOURS = 24   # 备份间隔（小时）
BACKUP_KEEP_COUNT = 30       # 最多保留备份数量，超出自动删除最旧的
```

### 命令行工具

```bash
# 查看所有备份
python restore_backup.py list

# 立即手动触发一次备份
python restore_backup.py backup

# 交互式选择恢复
python restore_backup.py

# 直接恢复到指定时间点
python restore_backup.py 2026-03-08_22-00-00
```

> ⚠️ 恢复后需重启应用才能生效。
