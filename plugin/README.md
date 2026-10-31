# 地产直播分析工作台插件

开源版本1.1.0，包含 `estate-live-workbench` 与 `douyin-live-replay-audio` 两项技能。保持 `plugin.json`、`skills/` 的完整目录结构，通过支持 Agent Plugins 的客户端加载此目录。

安装插件后，向助手提供开源仓库或自己的分析工作区路径。网页在仓库 `web/`，通用Python工具在 `pipeline/`；插件内另含可独立分发的工具副本与评分配置。

快速检查：

```sh
python3 plugin/skills/estate-live-workbench/scripts/workspace.py --workspace . --check-dependencies
python3 plugin/skills/estate-live-workbench/scripts/report_build.py --project-dir web --run
```

详细说明见仓库根目录README和docs/usage.md。插件采用MIT许可证；分析工具需要的模型、FFmpeg及其依赖按相应上游条款使用。
