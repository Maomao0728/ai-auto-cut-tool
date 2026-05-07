# AI 全自动剪辑工具

一个基于 Python + Gradio 的 AI 自动剪辑演示项目。用户上传图片/视频素材并输入宣传文案后，系统可以自动生成分镜、匹配素材、合成配音与字幕，并导出 MP4 视频。

## 功能特性

- 文案自动拆分分镜
- 支持自定义分镜与指定素材
- 图片/视频素材自动匹配
- 素材标签分析与匹配增强
- TTS 自动配音
- 字幕自动生成
- 背景音乐混音
- 支持 16:9、9:16、1:1 画面比例
- Gradio Web 页面一键生成与下载视频

## 项目结构

```text
.
├── gradio_app.py          # Gradio Web 主入口
├── api_config.py          # 环境变量与服务配置
├── llm_engine.py          # 分镜生成逻辑/LLM 接口预留
├── matching_engine.py     # 文案与素材匹配逻辑
├── tts_engine.py          # TTS 配音逻辑
├── video_engine.py        # 视频合成、字幕、BGM 混音
├── vision_engine.py       # 素材标签分析/视觉接口预留
├── requirements.txt       # Python 依赖
├── .env.example           # 环境变量示例
└── start_demo.bat         # Windows 本地启动脚本
```

## 环境要求

推荐环境：

- Python 3.10 或 3.11
- FFmpeg
- Windows / Linux 均可运行

Windows 服务器或本地电脑需要确保以下命令可用：

```bash
python --version
pip --version
ffmpeg -version
ffprobe -version
```

## 安装依赖

进入项目目录后执行：

```bash
python -m venv .venv
```

Windows 激活虚拟环境：

```bash
.venv\Scripts\activate
```

Linux / macOS 激活虚拟环境：

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

如果网络较慢，可使用清华源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
copy .env.example .env
```

Linux / macOS：

```bash
cp .env.example .env
```

本地 Windows 演示推荐配置：

```env
SERVER_NAME=127.0.0.1
SERVER_PORT=7860
INBROWSER=true
GRADIO_SHARE=false
TTS_PROVIDER=auto
```

服务器部署推荐配置：

```env
SERVER_NAME=0.0.0.0
SERVER_PORT=7860
INBROWSER=false
GRADIO_SHARE=false
TTS_PROVIDER=edge
TTS_EDGE_VOICE=zh-CN-XiaoxiaoNeural
```

如果部署到云服务器，需要在云服务器安全组和系统防火墙中放行 `7860` 端口。

## 启动项目

```bash
python gradio_app.py
```

本地访问：

```text
http://127.0.0.1:7860
```

服务器公网访问示例：

```text
http://服务器公网IP:7860
```

## 使用建议

比赛或演示时建议：

- 视频时长：20～30 秒
- 图片素材：4～6 张
- 视频素材：0～2 个短视频
- 文案长度：80～150 字
- 一次只运行一个生成任务

素材文件名建议使用明确语义，例如：

```text
政务大厅窗口.jpg
工作人员服务群众.jpg
数据大屏展示.jpg
AI系统界面.png
会议汇报现场.jpg
```

不要使用无意义名称，例如：

```text
1.jpg
2.png
aaa.mp4
```

## GitHub 上传注意事项

请不要上传以下文件或目录：

```text
.env
.venv/
__pycache__/
input/
output/
temp/
material_library/
*.mp4
*.mp3
*.wav
*.zip
```

建议上传 `.env.example`，不要上传真实 `.env`，避免泄露 API Key、服务器配置或其他敏感信息。

## 说明

当前项目定位为比赛/演示版，适合单人或少量用户测试使用。若需要长期公网服务，建议增加登录认证、任务队列、后台服务守护和更严格的安全组规则。
