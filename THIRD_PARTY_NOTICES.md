# 第三方组件

本仓库的自有源码以根目录MIT许可证发布。使用的依赖继续遵循各自许可证；具体安装版本见 `web/package-lock.json` 与各Python依赖清单。

## 网页依赖

| 组件 | 许可证 | 上游 |
| --- | --- | --- |
| React / React DOM | MIT | https://github.com/facebook/react |
| react-markdown | MIT | https://github.com/remarkjs/react-markdown |
| Vite | MIT | https://github.com/vitejs/vite |

这些依赖通过npm安装，其完整许可证随依赖分发。

## 可选媒体与模型环境

Python媒体工具通过依赖清单安装httpx、m3u8、SoundFile；声学分析可选NumPy、PyTorch、torchaudio、scikit-learn、Silero VAD和FunASR。MLX转写可选mlx-whisper。它们各自的许可证保留在安装分发中。

FFmpeg、模型权重及其推理运行环境由使用者安装，不随本仓库源码分发。具体模型及其版本以运行时配置为准，许可参见对应上游项目与模型卡。

网页演示音频由 `web/scripts/generate-demo-audio.py` 合成生成，演示数据由 `web/src/demo-data.js` 定义。
