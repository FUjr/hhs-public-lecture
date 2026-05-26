# 课堂模板平台 v2

## 面向教师的功能介绍

这是一个面向语文课堂的 AI 互动工具。教师可以选择课文模板，直接开展“学生问 AI”和“AI 问学生”两个课堂环节：学生提出问题后，系统会结合课文内容生成课堂式回答；学生表达观点后，系统会生成点评和追问，帮助教师把讨论推进到文本依据、表达逻辑和现实思考。

平台内置课堂脉络、学习目标、提问提示、思考步骤和课堂记录下载。AI 不可用时会自动回到本地模板，保证课堂流程不中断；配置远程 AI 后，回答会优先由浏览器直接请求 AI API 生成。

## 教师使用说明

1. 打开页面后，左下角点击设置按钮。
2. 在“课文”中选择本节课模板。
3. 默认已内置 SiliconFlow API Endpoint 和模型 `deepseek-ai/DeepSeek-V4-Flash`，只需要填写 API Key。
4. 在页面顶部或设置页选择“本地模式”或“大语言模型模式”，浏览器会记住上一次选择。
5. 选择“大语言模型模式”后点击“保存”或“测试连接”，看到“大语言模型可用”即可使用；如果 API 不可用，系统会提示并切回本地模式。
6. 在“学生问 AI”中输入学生问题，点击提交问题。
7. 在“AI 问学生”中输入学生观点，生成点评后可继续输入学生对追问的回应。
8. 课堂结束后，在“学生问 AI”页面点击“保存记录”，下载本节课 Markdown 记录。

## AI 配置分享与导入

设置页支持“导出配置链接”。教师配置好 Endpoint、API Key、模型和远程优先开关后，点击“生成链接”，系统会生成一个包含 Base64 编码 AI 配置的 URL，并尽量自动复制到剪贴板。

其他设备或浏览器打开这个 URL 后，会自动导入 AI 配置到当前浏览器的 `localStorage`，随后地址栏中的配置参数会被清理。这个链接包含 API Key，请只发给可信任的使用者，不要公开发布。

这是一个 Vue 重构后的课堂互动模板平台。前端负责课文模板展示、课堂脉络、学生问 AI、AI 问学生、设置与课堂记录下载，并直接请求 AI API；后端只保留静态文件托管和容器更新 webhook。

## 本地开发

生成课文模板 JSON：

```bash
python3 scripts/generate_lessons.py
```

启动前端开发服务：

```bash
npm install
npm run dev
```

构建并用 Python 服务托管静态文件：

```bash
npm run build
python3 web_dialogue_app.py --host 127.0.0.1 --port 8000
```

访问：

```text
http://127.0.0.1:8000
```

## 课文模板

- 教案源文件放在 `lesson_plan/*.md`。
- 生成结果放在 `public/generated-lessons/`。
- 每篇课文一个 JSON，`index.json` 是前端课文清单。
- 生成脚本会记录教案内容 hash；教案未变化时不会重复生成。
- 未配置 AI 生成接口时，脚本会用本地 markdown 解析兜底。

GitHub Action 会在构建镜像前运行：

```bash
python scripts/generate_lessons.py
```

如果 `public/generated-lessons/` 有变化，Action 会自动提交生成结果。

## 前端设置

左下角设置按钮支持：

- 切换课文。
- 默认 API endpoint：`https://api.siliconflow.cn/v1/chat/completions`。
- 默认模型：`deepseek-ai/DeepSeek-V4-Flash`。
- 教师通常只需要填写 SiliconFlow API Key。
- 切换“本地模式”和“大语言模型模式”。
- 导出一个可自动导入的 AI 配置链接。

这些设置只保存在当前浏览器 `localStorage`。AI 请求由浏览器直接发往设置中的 Endpoint，不会写入仓库、镜像或服务端文件。导出的配置链接会包含 API Key，请谨慎分享。

## AI 配置

运行时 AI 配置只从前端设置读取。未修改前端设置时，浏览器默认使用 SiliconFlow 兼容接口和 `deepseek-ai/DeepSeek-V4-Flash` 模型，只需补充 API Key。

如果目标 AI 服务没有开放浏览器跨域请求，直连会失败并回退本地模板；此时再考虑补充服务端转发接口。

## Docker

镜像地址：

```text
registry.cn-hangzhou.aliyuncs.com/fjrcn/hhs-class-1:v2
```

本地构建测试：

```bash
docker build -t hhs-class-1:v2 .
docker run --rm -p 8000:8000 hhs-class-1:v2
```

Compose：

```bash
export DEPLOY_WEBHOOK_TOKEN="替换成一段随机密钥"
docker compose up -d
```

## 自动构建与热更新

GitHub Actions 使用以下 secrets：

- `V2_ALIYUN_DOCKER_USERNAME`
- `V2_ALIYUN_DOCKER_PASSWORD`
- `V2_DEPLOY_WEBHOOK_URL`

部署 webhook 仍使用旧 API：

```text
POST /api/deploy/update?token=<DEPLOY_WEBHOOK_TOKEN>
```

Compose 默认使用 `v2` 标签，并通过一个临时 updater 容器执行：

```bash
docker compose pull hhs-class-1-v2
docker compose up -d hhs-class-1-v2
```

如服务器 compose 文件不在应用工作目录，可设置：

```bash
export DEPLOY_UPDATE_COMMAND="docker compose -f /path/to/docker-compose.yml pull hhs-class-1-v2 && docker compose -f /path/to/docker-compose.yml up -d hhs-class-1-v2"
```
