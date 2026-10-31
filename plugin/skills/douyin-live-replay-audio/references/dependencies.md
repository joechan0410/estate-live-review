# 依赖与运行

建议独立 Python 3.12 虚拟环境；Mac Apple Silicon 可用 uv 管理。FFmpeg 与 ffprobe 必须在 PATH 中。依赖和模型装在运行环境，模型权重不进入插件包。以下固定版本来自原系统使用记录；插件打包验证覆盖标准库测试，完整模型执行需在目标设备另行验证。

## 当前脚本

| 脚本 | 用途 | 依赖 |
|---|---|---|
| `scripts/collect_media.py` | 获准完整 HLS 回放采集和字幕证据 | m3u8==6.0.0、httpx、soundfile、ffmpeg、ffprobe |
| `scripts/archive_audio.py` | 历史录音转 MP3、验证后清理替代来源 | soundfile、ffmpeg、系统 ps；适用 macOS/POSIX |
| `scripts/analyze_audio.py` | 全量 VAD 和匿名说话人候选分段 | silero-vad==6.2.1、funasr==1.4.15、torch、torchaudio、numpy、soundfile、scikit-learn、ffmpeg |
| `scripts/process_transcripts.py` | 原文、纠错记录、术语与 CTA 候选 | Python 标准库 |
| `scripts/transcribe_missing.py` | Apple Silicon 本地补转缺口 | mlx-whisper==0.4.3、soundfile、ffmpeg |
| `scripts/score_hosts.py` | 按当前配置计算已核个人指标 | Python 标准库 |

采集 manifest 为场次对象数组，每项至少包含 `roomId`、Unix 秒 `start`、已观察且获准使用的 `replayUrl`；私人媒体地址只保存在项目目录。每项目每周期使用独立 `--root`，所有数据与生成文件写入该目录。评分输入结构在 `score_hosts.py` 顶部说明，实名核验、评论与留资连接、逐条答法审核由上游完成。

通用术语默认读取插件 `assets/general-lexicon.csv`；`<root>/knowledge/general-lexicon.csv` 可追加项目术语，同标准词以项目行覆盖。`<root>/knowledge/project-lexicon.csv` 仅对明确设置 `auto_correct=true` 的对应项自动纠错，其他通用候选保留原文待核。词库缺失或空表不会阻断转写处理。

CAM++ 使用 `funasr/campplus` 公开模型，首次运行需要下载。原系统记录的模型快照为 `e4b6ede7ce16997aff4ae69fbca1f0175e2afede`；脚本未锁定该 revision，目标运行必须记录实际模型/库版本、revision 与设备。默认每 5 秒选最多 5 秒语音（可用 `--step` 调整），在时间上取邻近多数，属于候选主讲者检测；短于约两分钟的声音变化特别复核。不创建姓名声纹注册表。

建议一次同时处理 1—2 场音频，媒体下载并发量按带宽和内存调整。当前完整外置交付录音为 **16 kbps、单声道、16 kHz MP3**，保留时轴和静默。新采集直接编码 MP3；历史来源转换必须全段解码、时长与引用核验通过，并确认读取进程结束。`archive_audio.py` 含源文件删除步骤，运行前应完成[交付维护](delivery-and-maintenance.md#录音压缩交付)要求的清单与引用核验；未满足时保留来源。既有分析不因交付压缩而重算，原分析哈希和参数独立留存。

本地补转的原系统使用模型为 `mlx-community/whisper-large-v3-turbo-q4`；可传本地模型路径，下载后记录 revision、字节数和 SHA256。现有 `transcribe_missing.py` 专用 MLX，其他设备使用受支持的 ASR 工具并转换为其 `local_asr/*.json` 输入结构，不宣称本脚本兼容其他 ASR 引擎。短期片段处理后删除。

说话人特征采用同长度小批次计算，不对不同长度语音补零后直接池化；样本按时间重新排序。静默仍使用全量音频 VAD，与说话人采样间隔无关。候选分段与实名确认、已核静默保持独立状态。

## 无私有数据自测

从本技能目录运行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_score_hosts.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_process_transcripts.py
```

评分测试覆盖当前 25/11/16/5/11/16/16 权重、缺测、非法输入、排名、静默曲线和严格大于 500 秒边界；转写测试在临时合成项目内实际执行 CLI，覆盖无项目词库、空词库及项目扩展。测试不采集媒体、不加载模型、不改历史报告。
