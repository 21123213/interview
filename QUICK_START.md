# 🚀 快速启动指南

> **最新更新**：已切换到阿里云 PNVS 短信认证服务，个人账号可用，无需企业资质和签名审核！

## ⚡ 核心变更

1. **配置简化**：所有配置直接从 `.env` 文件读取（已弃用 `config.yaml`）
2. **短信服务升级**：使用 PNVS 短信认证，无需签名审核，开通即用
3. **依赖更新**：需要重新安装后端依赖

---

## 🔧 准备工作（第一次使用必看）

### 1. 阿里云 PNVS 服务配置

#### 1.1 开通 PNVS 短信认证服务
```
1. 访问：https://pnvs.console.aliyun.com/
2. 点击左侧「短信认证」
3. 点击「立即开通」（个人账号可用，无需企业资质）
```

#### 1.2 获取预置签名
```
1. 进入：短信认证 → 资源管理 → 签名管理
2. 查看「系统签名」列表
3. 记录可用签名（例如：阿里云、验证服务）
```

#### 1.3 获取预置模板CODE
```
1. 进入：短信认证 → 资源管理 → 模板管理
2. 查看「系统模板」列表
3. 找到验证码类型模板
4. 记录模板CODE（例如：SMS_205480605）
```

#### 1.4 确认 RAM 权限
```
1. 访问：https://ram.console.aliyun.com/
2. 确认你的 RAM 用户有权限：AliyunDypnsFullAccess
3. 如果没有，添加该权限
```

---

## 第一步：配置环境变量

编辑根目录 `.env` 文件，填入你的真实配置：

```env
# ========== 应用配置 ==========
APP_NAME=RAG智能助手
APP_VERSION=1.0.0
APP_HOST=0.0.0.0
APP_PORT=8000
APP_DEBUG=True  # True=测试模式(验证码123456), False=生产模式(真实短信)

# ========== 数据库配置 ==========
DB_HOST=你的云数据库地址
DB_PORT=3306
DB_USER=你的数据库用户名
DB_PASSWORD=你的数据库密码
DB_NAME=rag_system

# 数据库API（SQLPub方式）
DB_API_BASE_URL=https://api.sqlpub.com/api/v1
DB_API_KEY=你的SQLPub_API_Key

# ChromaDB
CHROMA_PERSIST_DIR=db/chroma_db

# ========== DashScope API ==========
DASHSCOPE_API_KEY=sk-391cfd906c8d461f9a770c3ce116d4db
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v3

# ========== 阿里云 PNVS 短信认证服务 ⭐ NEW ==========
ALIYUN_ACCESS_KEY_ID=你的阿里云AccessKeyID
ALIYUN_ACCESS_KEY_SECRET=你的阿里云AccessKeySecret

# 预置签名（从 PNVS 控制台复制，无需审核）
ALIYUN_SMS_SIGN_NAME=阿里云

# 预置模板CODE（从 PNVS 控制台复制，无需审核）
ALIYUN_SMS_TEMPLATE_CODE=SMS_205480605

# 验证码有效期（分钟）
VERIFICATION_CODE_EXPIRE=5

# ========== JWT配置 ==========
JWT_SECRET_KEY=your-super-secret-key-at-least-32-characters-long
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# ========== 文件上传 ==========
UPLOAD_DIRECTORY=uploads
UPLOAD_MAX_FILE_SIZE=10485760
UPLOAD_ALLOWED_EXTENSIONS=.txt,.pdf,.docx,.md

# ========== CORS ==========
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

> **⚠️ 重要**：
> - `ALIYUN_SMS_SIGN_NAME` 必须从 PNVS 控制台的「系统签名」中复制
> - `ALIYUN_SMS_TEMPLATE_CODE` 必须从 PNVS 控制台的「系统模板」中复制
> - 先用测试模式（`APP_DEBUG=True`）验证功能，再切换生产模式

## 第二步：初始化数据库

使用MySQL客户端或图形化工具执行：

```bash
# 方式1：命令行
mysql -h 你的数据库地址 -P 3306 -u 用户名 -p < backend/init_db.sql

# 方式2：使用图形化工具（推荐）
# 打开 Navicat/DBeaver/Sequel Pro
# 连接到你的云数据库
# 执行 backend/init_db.sql 脚本
```

## 第三步：安装依赖 ⭐ 必须重新安装

### 后端依赖（已更新 SDK）
```powershell
cd backend

# ⚠️ 卸载旧的 SMS SDK
pip uninstall alibabacloud_dysmsapi20170525 alibabacloud_credentials -y

# ✅ 安装新的 PNVS SDK
pip install -r requirements.txt
```

**新增依赖**：
- `alibabacloud_dypnsapi20170525>=2.0.24` - PNVS 短信认证 SDK
- `alibabacloud_tea_util>=0.3.11` - 阿里云工具库

### 前端依赖（无变化）
```powershell
cd frontend
npm install
```

## 第四步：启动服务

### 启动后端（终端1）
```powershell
cd backend
python app/main.py
```

看到以下输出表示成功：
```
✅ PNVS服务初始化成功
   - 签名: 阿里云
   - 模板: SMS_205480605
   - 调试模式: True
Starting server at http://0.0.0.0:8000
API Docs: http://0.0.0.0:8000/docs
```

### 启动前端（终端2）
```powershell
cd frontend
npm run dev
```

看到以下输出表示成功：
```
VITE v5.0.8  ready in xxx ms
➜  Local:   http://localhost:5173/
```

---

## 第五步：测试功能

### 测试模式验证（验证码 123456）

1. **访问系统**：`http://localhost:5173`
2. **点击"立即注册"**
3. **填写信息**：
   - 用户名：testuser
   - 密码：test123456
   - 手机号：18174619015（随便填）
4. **点击"发送验证码"**
   - 后端日志显示：`🧪 [测试模式] 验证码: 123456`
5. **输入验证码**：`123456`
6. **完成注册**

✅ 测试模式通过后，说明代码运行正常！

---

### 切换到生产模式（真实短信）

1. **修改 `.env`**：
   ```env
   APP_DEBUG=False  # 关闭测试模式
   ```

2. **重启后端**：
   ```powershell
   # 停止当前进程（Ctrl+C）
   cd backend
   python app/main.py
   ```

3. **检查日志**：
   ```
   ✅ PNVS服务初始化成功
      - 调试模式: False  # ← 应该是 False
   ```

4. **真实测试**：
   - 输入你的真实手机号
   - 点击"发送验证码"
   - 检查手机短信（5-30秒内到达）
   - 输入收到的验证码
   - 完成注册

---

## 📋 功能清单

✅ **用户认证**
- 手机号注册（**PNVS 短信认证**，无需审核）
- 用户名密码登录
- JWT Token认证
- 测试模式/生产模式自动切换

✅ **文件管理**
- 文件上传（支持 .txt, .pdf, .docx, .md）
- 自动向量化处理
- 文件列表查看
- 文件删除

✅ **智能对话**
- 基于上传文档的问答
- 多轮对话支持
- 实时消息展示
- 来源追溯

---

## 🔍 完整测试流程

### 1. 注册账号（测试模式）
```
用户名：testuser
密码：test123456
手机号：18174619015
验证码：123456（测试模式固定）
```

### 2. 注册账号（生产模式）
```
用户名：yourname
密码：your_password
手机号：你的真实手机号
验证码：输入收到的短信验证码
```

### 3. 上传文档
- 点击"选择文件上传"
- 选择一个txt或pdf文件
- 等待处理完成（状态变为"已处理"）

### 4. 开始对话
- 输入问题，如："这个文档的主要内容是什么？"
- 查看AI回答

---

## 🛠️ API文档

后端API文档地址：`http://localhost:8000/docs`

## ⚠️ 注意事项

### 1. PNVS 短信认证配置（⭐ 新）

**必须完成的准备工作**：
- ✅ 开通阿里云 PNVS 短信认证服务
- ✅ 从控制台获取预置签名（无需审核）
- ✅ 从控制台获取预置模板CODE（无需审核）
- ✅ 确认 RAM 用户有 `AliyunDypnsFullAccess` 权限
- ✅ 账户余额 > 1 元

**优势**：
- ✅ 个人账号可用，无需企业资质
- ✅ 无需签名和模板审核，开通即用
- ✅ 验证码由阿里云托管，更安全

**详细配置指南**：
- 查看 `PNVS_MIGRATION_GUIDE.md` - 完整技术文档
- 查看 `PNVS_TODO.md` - 快速操作清单

---

### 2. 数据库连接

- 使用HTTP API方式，无需本地MySQL
- 确保 `DB_API_KEY` 正确配置
- 首次使用需执行 `backend/init_db.sql` 初始化

---

### 3. 文件大小限制

- 单个文件最大10MB
- 建议先用小文件测试（1-2MB）

---

### 4. 测试模式 vs 生产模式

| 特性 | 测试模式 | 生产模式 |
|------|---------|---------|
| 配置 | `APP_DEBUG=True` | `APP_DEBUG=False` |
| 验证码 | 固定 `123456` | 系统生成 |
| 短信 | ❌ 不发送 | ✅ 真实发送 |
| 成本 | 免费 | 0.045元/条 |
| 用途 | 开发测试 | 正式环境 |

---

## 📝 目录结构

```
RAG-FOR-BEGINNERS/
├── backend/          # 后端FastAPI
│   ├── app/         # 应用代码
│   ├── config.yaml  # 配置文件
│   └── init_db.sql  # 数据库脚本
├── frontend/         # 前端React
│   ├── src/         # 源代码
│   └── package.json # 依赖配置
├── db/              # ChromaDB向量数据库
├── docs/            # 文档目录
├── uploads/         # 上传文件存储
└── .env             # 环境变量
```

## 🐛 常见问题

### Q1: PNVS 服务初始化失败？
**错误**：`⚠️ PNVS服务初始化失败`

**解决**：
```env
# 检查 .env 文件中的配置
ALIYUN_ACCESS_KEY_ID=必须有值
ALIYUN_ACCESS_KEY_SECRET=必须有值
ALIYUN_SMS_TEMPLATE_CODE=必须有值
```

---

### Q2: 验证码收不到？（生产模式）
**可能原因**：
- 签名或模板CODE配置错误
- 手机号不是中国大陆号码
- 手机设置了短信拦截

**解决**：
1. 检查后端日志，查看 PNVS 响应
2. 确认签名和模板CODE从控制台复制
3. 先用测试模式（`APP_DEBUG=True`）验证代码正确性

---

### Q3: 报错 `isv.SMS_SIGNATURE_ILLEGAL`？
**原因**：签名名称不正确

**解决**：
1. 进入 PNVS 控制台 → 资源管理 → 签名管理
2. 完全复制「系统签名」中的签名名称
3. 粘贴到 `.env` 的 `ALIYUN_SMS_SIGN_NAME`
4. 重启后端

---

### Q4: 报错 `isv.SMS_TEMPLATE_ILLEGAL`？
**原因**：模板CODE不正确

**解决**：
1. 进入 PNVS 控制台 → 资源管理 → 模板管理
2. 复制「系统模板」中的完整CODE（包括 `SMS_` 前缀）
3. 粘贴到 `.env` 的 `ALIYUN_SMS_TEMPLATE_CODE`
4. 重启后端

---

### Q5: 数据库连接失败？
**解决**：
- 检查 `.env` 中的数据库配置和 API Key
- 确认数据库已执行 `init_db.sql` 初始化

---

### Q6: 前端无法连接后端？
**解决**：
- 确认后端已启动在 8000 端口
- 检查 CORS 配置
- 检查防火墙设置

---

### Q7: 文件上传后无法问答？
**解决**：
- 检查文件状态是否为"已处理"
- 查看后端日志是否有错误
- 确认 ChromaDB 正常运行

---

## 📧 获取帮助

- **PNVS 配置指南**：`PNVS_MIGRATION_GUIDE.md`（完整技术文档）
- **PNVS 操作清单**：`PNVS_TODO.md`（快速操作步骤）
- **详细文档**：`README_DEPLOYMENT.md`
- **后端日志**：`logs/app.log`
- **API文档**：`http://localhost:8000/docs`
- **浏览器控制台**：按F12查看

---

## 📦 需要重新下载/安装的内容

### ✅ 后端依赖（必须）

```powershell
cd backend

# 卸载旧的 SMS SDK
pip uninstall alibabacloud_dysmsapi20170525 alibabacloud_credentials -y

# 安装新依赖
pip install -r requirements.txt
```

**主要变化**：
- ❌ 移除：`alibabacloud_dysmsapi20170525==3.0.0` （旧 SMS SDK）
- ❌ 移除：`alibabacloud_credentials==0.3.4`
- ✅ 新增：`alibabacloud_dypnsapi20170525>=2.0.24` （PNVS SDK）
- ✅ 新增：`alibabacloud_tea_util>=0.3.11`

### ✅ 前端依赖（无变化）

```powershell
cd frontend
npm install
```

前端代码无任何变化，不需要重新安装依赖。

---

## 🚀 快速启动命令（一键复制）

### Windows PowerShell

```powershell
# 1. 卸载旧依赖
cd d:\RAG-FOR-BEGINNERS\backend
pip uninstall alibabacloud_dysmsapi20170525 alibabacloud_credentials -y

# 2. 安装新依赖
pip install -r requirements.txt

# 3. 启动后端（终端1）
python app/main.py

# 4. 启动前端（新开终端2）
cd d:\RAG-FOR-BEGINNERS\frontend
npm run dev
```

---

## ✅ 启动检查清单

启动前确认：

- [ ] `.env` 文件已配置（特别是 PNVS 相关配置）
- [ ] 阿里云 PNVS 服务已开通
- [ ] 预置签名和模板CODE已获取
- [ ] RAM 用户有 `AliyunDypnsFullAccess` 权限
- [ ] 后端旧依赖已卸载
- [ ] 后端新依赖已安装
- [ ] 数据库已初始化（执行过 `init_db.sql`）

启动后确认：

- [ ] 后端日志显示：`✅ PNVS服务初始化成功`
- [ ] 后端运行在：`http://localhost:8000`
- [ ] 前端运行在：`http://localhost:5173`
- [ ] 测试模式验证码 `123456` 能成功注册

---

**祝你使用愉快！** 🎉
