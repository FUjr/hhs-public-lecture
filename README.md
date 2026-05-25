# 《爱莲说》，说AI莲

这是一个围绕《爱莲说》课堂互动设计的 Python 课堂助手原型。

## 网页版对话 AI

网页模块只包含“学生问 AI”和“AI 问学生”的课堂互动部分，适合教师投屏使用。

```bash
python web_dialogue_app.py
```

打开终端提示的本地地址，例如：

```text
http://127.0.0.1:8000
```

网页版默认离线优先：

- 学生界面不展示预设问题，保留开放提问空间。
- 程序后台会优先匹配教学设计中的关键问答，保障课堂回答稳定。
- 同类问题会调整回答顺序和衔接语，减少多组提问时的重复感。
- AI 向学生追问后，学生可以继续回应，AI 会再给一次课堂式回应。
- 未命中预设时，会继续复用项目已有的 AI 接口配置。
- 如果没有配置接口，程序会回退到本地演示回答。
- 如果已配置接口但远端请求失败、返回空内容或响应解析失败，界面会明确显示“请求错误”提示，避免把异常误当成正常课堂回答。
- 程序会把运行状态、AI 请求结果、保存记录和部署更新写入 `logs/classroom_ai.log`，日志目录不会提交到仓库。
- 点击“保存记录”会把本节对话保存到 `session_logs/` 目录。

## 桌面版运行方式

```bash
python main.py
```

## Docker 运行

本项目提供容器镜像配置，镜像地址：

```text
registry.cn-hangzhou.aliyuncs.com/fjrcn/hhs-class-1
```

本地构建测试：

```bash
docker build -t hhs-class-1:test .
docker run --rm -p 8000:8000 hhs-class-1:test
```

服务器推荐使用 Docker Compose：

```bash
export DEPLOY_WEBHOOK_TOKEN="替换成一段随机密钥"
docker compose up -d
```

`docker-compose.yml` 会把宿主机 `/var/run/docker.sock` 和当前部署目录挂载到容器中，用于 webhook 收到请求后在服务器上执行 `docker compose pull/up` 更新当前服务。

服务启动后访问：

```text
http://服务器地址:8000
```

## 自动构建与自动更新

仓库已配置 GitHub Actions：当 `main` 分支收到 push 时，会自动构建容器镜像并推送到阿里云容器镜像仓库，然后调用部署 webhook 更新服务器上的容器。

需要在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions` 中配置：

- `ALIYUN_DOCKER_USERNAME`：阿里云容器镜像仓库用户名。
- `ALIYUN_DOCKER_PASSWORD`：阿里云容器镜像仓库密码。
- `DEPLOY_WEBHOOK_URL`：服务器更新接口完整 URL。

`DEPLOY_WEBHOOK_URL` 示例：

```text
https://your-domain.example.com/api/deploy/update?token=替换成同一个随机密钥
```

服务器上的课堂 Web 服务会处理：

```text
POST /api/deploy/update?token=<DEPLOY_WEBHOOK_TOKEN>
```

token 必须和服务器环境变量 `DEPLOY_WEBHOOK_TOKEN` 一致。鉴权通过后，服务默认启动一个临时 updater 容器，由它延迟执行更新，避免课堂服务在 HTTP 响应发出前重启：

```bash
docker run -d --rm --name hhs-class-1-updater -v /var/run/docker.sock:/var/run/docker.sock -v ${PWD}:${PWD} -w ${PWD} registry.cn-hangzhou.aliyuncs.com/fjrcn/hhs-class-1:latest sh -c 'sleep 2; docker compose -f ${PWD}/docker-compose.yml --project-directory ${PWD} pull hhs-class-1 && docker compose -f ${PWD}/docker-compose.yml --project-directory ${PWD} up -d hhs-class-1'
```

如果服务器上的 compose 文件不在应用工作目录，或需要自定义更新命令，可以在服务器上设置：

```bash
export DEPLOY_UPDATE_COMMAND="docker compose -f /path/to/docker-compose.yml pull hhs-class-1 && docker compose -f /path/to/docker-compose.yml up -d hhs-class-1"
```

## 功能流程

- 预习过渡
- 课文理解
- 学生问 AI
- AI 问学生
- 教师总结与作业

课堂结束后，记录会自动保存到 `session_logs/` 目录。

## 真实 AI 配置

默认会使用内置演示问答逻辑，无需额外依赖。

如果需要接入真实接口，可在运行前设置以下环境变量：

- `LESSON_AI_ENDPOINT`
- `LESSON_AI_API_KEY`
- `LESSON_AI_MODEL`（可选）

未配置接口时，程序会自动回退到内置演示逻辑；已配置接口但请求异常时，会显示请求错误提示。

当前回退策略：

- 未配置 `LESSON_AI_ENDPOINT` 或 `LESSON_AI_API_KEY` 时，继续使用内置演示回答，保障课堂流程可离线运行。
- 已配置 AI 接口但请求失败、HTTP 状态异常、响应为空或解析失败时，不再静默使用本地演示回答，而是返回“请求错误”提示，方便教师及时检查接口和网络。

程序启动时会先尝试请求一次已配置的 AI 后端：

- 请求成功时，界面状态显示 `AI后端已连接`。
- 未配置时，界面状态显示 `课堂模式：本地`，课堂互动仍会使用内置备用回答继续运行。
- 已配置但请求失败时，界面状态显示 `AI后端请求错误`，课堂互动会提示请求错误，便于及时排查接口。

如果使用 OpenAI 兼容平台：

- `LESSON_AI_ENDPOINT` 可以直接填平台给你的 `base URL`
- 程序会自动判断并补成合适的接口地址
- 对 OpenAI 官方地址会自动补成 `/responses`
- 对大多数第三方兼容平台会自动补成 `/chat/completions`

例如 SiliconFlow 可直接填：

```powershell
$env:LESSON_AI_ENDPOINT="https://api.siliconflow.cn/v1/"
$env:LESSON_AI_API_KEY="你的密钥"
$env:LESSON_AI_MODEL="Pro/zai-org/GLM-5.1"
python main.py
```

联网并成功接入真实 AI 后：

- 学生问 AI 会按问题类型分别生成回答，不再尽量套用同一种句式。
- AI 问学生的点评会根据学生立场变化，更像课堂上的即时回应。
- 程序会尽量避开最近几次回答的重复开头，减少“翻来覆去是同一句话”的感觉。

## 推送到 GitHub

本项目已配置远端仓库：

```text
git@github.com:FUjr/hhs-public-lecture.git
```

后续修改后，可以运行：

```powershell
.\scripts\auto_push.ps1 -Message "Update classroom dialogue"
```

提交信息要求：

- 后续 AI 或人工提交时，commit message 必须完整描述具体改动，不能只写 `update`、`fix`、`change` 等泛化内容。
- 推荐格式为首行概括改动范围，正文逐条说明关键行为变化、配置或文档更新、验证方式。
