# 工作区集成与执行地图

## 目录约定

`WORKSPACE` 是实际地产工作台根目录；`WEEK` 是 `WORKSPACE/outputs/live-review/<project>/<week>`。这些名称在本文仅用作说明，运行时传入真实路径。

|资料|相对工作区路径|
|---|---|
|当前项目规则|`knowledge/<project>/automation/weekly-workflow.md`|
|规则历史与生效范围|`knowledge/<project>/automation/rule-updates.json`|
|验收契约|`knowledge/<project>/automation/weekly-acceptance.md`|
|自动任务状态|`knowledge/<project>/automation/state.json`|
|人员、账号与昵称|`knowledge/<project>/roster/`|
|续接状态|`outputs/live-review/<project>/<week>/CONTINUATION.json`|
|逐主播与全量审核|目标周 `data/review/`|
|报告源码|目标周 `周报/src/content/report/`|
|源数据快照|目标周 `周报/src/data.json`|
|报告产物|目标周 `report/`，含 HTML、manifest 指定的 JSON 与外置录音|
|运行环境|`outputs/live-review/.venv/bin/python`；FFmpeg/ffprobe 与当前 Node/Data 构建器|

读取报告源码之前，遵守其 `AGENTS.md`。不复制整套生成运行时到插件，也不携带实际源数据快照。

## 阶段入口

下表是现有系统已核对的文件名，实际存在性由 `workspace.py` 返回。入口执行前读其参数及根路径定义，尤其注意固定项目名单、历史周日期和人工短评。文件名相似不代表契约相同。

|阶段|目标周 scripts 中的入口|关键证据|
|---|---|---|
|媒体与队列|`queue_weekly.py`、`queue_media.py`、`queue_alignment.py`|场次清单、完整录音、队列状态、对齐与覆盖|
|证据准备|`prepare_whole_week_evidence.py`、`prepare_full_comment_review.py`|ASR语境、全量评论队列；准备数量与已审数量分开|
|实际主播与指标|`index_identity_text.py`、`build_current_host_metrics.py`|当前周实际交接、稳定person_id、归属争议与全员台账|
|评论与留资|`audit_all_comments.py`、`audit_all_comment_leads.py`、`adjudicate_host_session_conversion.py`、`build_comment_acquisition_insights.py`|原评论守恒、逐条真实答法、完整ID双向连接、评论前后时序|
|内容与静默|`apply_content_scoring_v2.py`、`apply_silence_exclusions.py`|内容量表、实际非语音复测、带依据排除；视频无豁免|
|报告与周期|`rebuild_accepted_report.py`、`build_period_views.py`、`package_previous_week_report.py`|真实周度、累计、月度的逐主播评价与答法汇总|
|验收|`verify_whole_week_review.py`、`verify_two_week_delivery.py`、`verify_audio16_receipt.py`|范围/数据/音频引用/版本与缺口|
|发布|`prepare_protected_release.py`、`verify_published_release_http.py`|本次包哈希、访问保护、Range与浏览器实播|

工作锁可出现在目标周及项目子目录的 `processing.lock`、`data/review/rebuild-accepted-report.lock`。锁文件存在不能单独证明进程仍在运行，需用实际进程及对应状态核验。

## 报告构建适配

原系统构建器支持 `--node`、`--data-app`，应传入当前可用路径。插件 `report_build.py` 依次使用显式参数、PATH 和已安装运行时；Data 构建器按实际安装的版本目录发现。发现文件只证明该文件存在，构建成功及浏览器验收需另有结果。

先输出构建计划（不执行报告脚本）：

```sh
python3 skills/estate-live-workbench/scripts/report_build.py --week-root "$ESTATE_WEEK_ROOT"
```

已经确认是目标周、输入和规则已对齐后，执行该周原构建器：

```sh
python3 skills/estate-live-workbench/scripts/report_build.py --week-root "$ESTATE_WEEK_ROOT" --run
```

只做样式或包装且已确认源快照的任务可传 `--skip-snapshot`。启用 `--verify-http` 时还需传真实 `--preview-url`，且预览服务已运行。若自动发现不到运行时，通过 Codex 的 workspace dependencies 工具读取当前路径，再显式传 `--node` / `--data-app` / `--python`；不要恢复失效的旧插件版本目录。

构建器成功不能替代浏览器、音频和业务证据验收。原构建器内部可能采用比总规则更低的 HTML 大小阈值，保持其实际检查并记录失败原因。

## 新周与新项目

- 显式目标周尚不存在时，先按该项目规则确定起止时间，再建立新目录、场次与证据清单。
- 从基准周复用结构/代码时逐项核对硬编码，保留输入输出契约，清除旧日期、人员结论、人工分数、客户链与旧数据快照。
- 账号、roster、项目知识、授权页面入口来自该项目真实资料。未确认身份按匿名状态继续可独立完成的分析。
- 当前工作区缺少完整周级代码时，可先用插件内媒体/转写/评分工具处理明确输入，再按照报告契约补足。不能把基础脚本执行成功写成全系统分析完成。

## 集成核验的边界

本次插件整合验证只读工作区识别、当前依赖定位、评分/词库与桥接合成测试、报告构建命令解析和包结构。当前业务报告的分析状态以实际工作区记录和本次运行结果为准。每次发布仍核验真实线上内容，历史已通过记录不自动充作当前验证。
