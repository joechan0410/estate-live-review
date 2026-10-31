# 使用说明

## 先运行报告示例

需要 Node.js 22.12 或更高版本和 npm；CI 使用 Node.js 22。从仓库根目录运行：

```sh
cd web
npm ci
npm run dev
```

打开终端显示的本地地址。页面自带示例楼盘 A/B/C 和主播甲/乙/丙的合成数据，启动演示无需 API Key、Codex 或数据插件。

示例提供两周切换，也可以在地址后使用 `?week=2026-09-12` 或 `?week=2026-09-19`。可以查看评分、内容价值和问答证据，使用项目与主播筛选，并导出 CSV。示例数值用于演示界面与数据结构。

构建静态站点并在本地预览：

```sh
npm test
npm run build
npm run preview
```

构建结果在 `web/dist/`。`preview` 命令用于检查本地构建结果；发布时将 `dist/` 内容交给所选静态站点服务。

## 运行 Python 评分示例

需要 Python 3.11 或更高版本。在仓库根目录创建环境：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m unittest discover -s tests -v
```

用合成输入生成评分结果：

```sh
python -m pipeline.score_hosts \
  --input tests/fixtures/synthetic-hosts.json \
  --output /tmp/synthetic-host-scores.json
```

默认评分配置位于 `pipeline/assets/scoring-policy.json`。先核对输入中的数值、缺项和分母，再根据自己的业务口径调整配置。

## 计算评论到留资的实际主播归属

该命令使用 Python 标准库，按直播间和完整客户标识连接记录，并通过提交前最后一次评论所在的实际主播时段确定归属。

```sh
python -m pipeline.attribute_comment_leads \
  --input tests/fixtures/synthetic-attribution.json \
  --output /tmp/synthetic-attribution.json
```

输入 JSON 的时间统一使用 Unix 秒数：

| 数组 | 主要字段 |
| --- | --- |
| `comments` | `id`、`room_id`、`customer_id`、`timestamp`、`eligible` |
| `leads` | `id`、`room_id`、`customer_id`、`timestamp` |
| `shifts` | `id`、`room_id`、`host_id`、`start`、`end`、`verified` |
| `room_coverage` | `room_id`、`comments_complete`、`leads_complete` |

`eligible` 表示评论有效性已核结果；保留完整评论列表，包括已判无效的评论，才能确定提交前的末次评论。`verified: true` 表示实际主播与时段边界已核；`room_coverage` 的两个完整性字段也需要真实证据。录制缺口可以通过时段内的 `unrecorded_gaps` 起止区间记录。

归属需要满足 `评论时间 < 留资时间 < 该主播实际结束时间`，同一实际时段内须有有效评论。工具使用完整 ID 连接，跨直播间分别处理，采用实际时段且不设固定分钟窗口。缺失身份、未闭合边界、时间相同无法排序、记录不全或中间录制缺口会保留待核。

输出包括 `matches`、`pending`、`excluded`、`duplicates`、逐直播间/客户/主播的 `opportunities` 和 `host_totals`。同直播间的同客户转化只计一次；相同 ID 的重复输入记录会列出，内容相互冲突的重复 ID 会报错。先查看待核原因与统计范围，再将已闭合的数值接入评分。

## 使用数据处理命令

转写整理和评分使用 Python 标准库。媒体采集与归档还需要 FFmpeg/ffprobe 在 `PATH` 中，并安装：

```sh
python -m pip install -r pipeline/requirements.txt
```

各工具通过模块形式运行，完整参数以当前命令的帮助信息为准：

```sh
python -m pipeline.collect_media --help
python -m pipeline.process_transcripts --help
python -m pipeline.analyze_audio --help
python -m pipeline.archive_audio --help
python -m pipeline.score_hosts --help
python -m pipeline.attribute_comment_leads --help
```

转写整理入口读取指定项目目录下的会话资料，例如：

```text
example-project/
└── data/
    └── session-001/
        ├── complete.json
        ├── subtitle_snapshots.jsonl
        └── local_asr/
            └── *.json
```

```sh
python -m pipeline.process_transcripts --root ./example-project
```

该工具整理字幕及已有本地转写，生成逐句转写和口播行动提示候选。检查命令输出与来源对应关系后，再用于人工分析。

音频分析安装 `pipeline/requirements-audio.txt`。本地 ASR 安装 `pipeline/requirements-asr.txt`，当前 MLX 后端支持 Apple Silicon macOS；安装后用 `python -m pipeline.transcribe_missing --help` 查看指定录音及起止时间的参数。音频模型会按需下载。只运行前端演示和标准库评分测试时，无需这些模型。

## 使用工作台插件

支持 Agent Plugins 的客户端可以加载 `plugin/` 目录，保持其中 `plugin.json` 和 `skills/` 的目录结构。插件支持当前开源仓库，也支持已有分析工作区。

在仓库根目录检查独立运行环境：

```sh
python plugin/skills/estate-live-workbench/scripts/workspace.py \
  --workspace . --check-dependencies
```

命令识别 `web/` 与 `pipeline/`，返回 `standalone-source` 模式及本地依赖位置。它只检查环境，不启动分析。

通过插件构建当前前端：

```sh
npm --prefix web ci
python plugin/skills/estate-live-workbench/scripts/report_build.py \
  --project-dir web --run
```

`--project-dir web` 使用 npm 构建，产物仍在 `web/dist/`，无需 Data 插件。去掉 `--run` 只输出构建计划。已有工作区可继续使用其原有目录与构建入口，详见 [插件说明](../plugin/README.md)。

## 接入自己的报告

1. 整理媒体、字幕、评论与留资输入，保留源标识和时间轴。
2. 运行需要的数据处理模块，复核身份、交接、原话和缺项。
3. 按评分配置生成数值，保留分母、覆盖范围及证据指针。
4. 参考 `web/src/demo-data.js` 将已审核结果映射为页面快照。
5. 本地检查筛选、证据链接、音频地址和 CSV，再发布静态页面。

公开提交的示例使用合成数据。个人项目的录音、转写、账号配置及业务数据放在自己的工作目录。
