# 课堂模板平台 v2

这是一个 Vue 重构后的课堂互动模板平台。前端负责课文模板展示、课堂脉络、学生问 AI、AI 问学生、设置与课堂记录下载；后端只保留 AI 代理和容器更新 webhook。

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

构建并用 Python 服务托管：

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
- 填写 API endpoint、API key、model。
- 选择是否优先使用远程 AI。

这些设置只保存在当前浏览器 `localStorage`。AI 请求仍通过同源 Python 后端代理发出，不会写入仓库、镜像或服务端文件。

## AI 配置

服务端默认读取：

- `V2_LESSON_AI_ENDPOINT`
- `V2_LESSON_AI_MODEL`

兼容旧变量：

- `LESSON_AI_ENDPOINT`
- `LESSON_AI_API_KEY`
- `LESSON_AI_MODEL`

前端设置中填写的 API 配置优先于服务端环境变量。

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
- `V2_LESSON_AI_ENDPOINT`
- `V2_LESSON_AI_MODEL`

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
