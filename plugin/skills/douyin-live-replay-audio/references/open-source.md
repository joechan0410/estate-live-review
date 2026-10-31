# GitHub与公开模型检索记录

检索日2026-09-12。只引用项目官方仓库；第三方技能仅比较流程，不未经审阅安装或运行。

| 组件 | 选择 | 用途/限制 |
|---|---|---|
| [Silero VAD](https://github.com/snakers4/silero-vad) | 已采用 | 全音频发声区间，按用户>10秒口径计算静默候选；仍需区分背景人声。 |
| [FunASR](https://github.com/modelscope/FunASR) / [CAM++模型](https://huggingface.co/funasr/campplus) | 已采用 | 单场匿名聚类，Python调用公开实现；模型Apache2.0，权重独立下载。 |
| [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) | 已采用 | Apple Silicon本地补转字幕缺口和核对交接语句；本次使用large-v3-turbo-q4，保留模型版本与校验值。 |
| [m3u8](https://github.com/globocom/m3u8) | 已采用 | 解析播放列表，避免自行写不完整HLS解析器。 |
| [FFmpeg](https://ffmpeg.org/) | 已采用 | 完整音频解复用、16k单声道分析文件；短片精确定位需解码裁切。 |
| [pyannote.audio](https://github.com/pyannote/pyannote-audio) | 备选 | 更完整说话人分段；部分模型须HF令牌和接受条件。本次未具备这些前提，不伪称运行。 |
| [WhisperX](https://github.com/m-bain/whisperX) | 备选 | ASR、逐词对齐和分段整合；较重，不必把已有可用字幕全部重做。 |
| [OpenAI transcribe skill](https://github.com/openai/skills/blob/main/skills/.curated/transcribe/SKILL.md) | 流程参考 | 需API凭证与云端上传授权；本次未上传音频。 |
| [ElevenLabs speech-to-text skill](https://github.com/elevenlabs/skills/blob/main/speech-to-text/SKILL.md) | 备选 | 可用关键词与说话人标签；受云端上传、凭证和计费约束。 |
| [wechat-toolkit](https://github.com/QUSEIT/skill-wechat-toolkit/blob/main/SKILL.md) | 检索思路参考 | Sogou公众号搜索可辅助发现；不是绕过微信安全策略的工具，不安装不执行不明脚本。 |
| [audio-transcriber skill](https://github.com/ericgandrade/claude-superskills/blob/main/skills/audio-transcriber/SKILL.md) | 比较参考 | 通用音频转写流程，未直接满足地产价值讲解、评论收割和统计口径。 |

修正原技能技术说法：Chrome默认配置远程调试限制从136起，[Chrome官方说明](https://developer.chrome.com/blog/remote-debugging-port)。本技能直接使用支持的已登录浏览器连接。HLS规范见 [RFC8216](https://www.rfc-editor.org/rfc/rfc8216.html)，不能只处理EXTINF而忽略KEY/MAP/BYTERANGE和discontinuity。
