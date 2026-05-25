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
- 点击“保存记录”会把本节对话保存到 `session_logs/` 目录。

## 桌面版运行方式

```bash
python main.py
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

接口不可用、超时或未配置时，程序会自动回退到内置演示逻辑。

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
