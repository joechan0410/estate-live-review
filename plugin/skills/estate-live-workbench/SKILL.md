---
name: estate-live-workbench
description: 查看、运行或继续地产直播分析工作台，连接网页、采集、转写、评分与项目工作区。
---

# 地产直播分析工作台

## 定位项目

用户提供的目录优先；也可使用环境变量 `ESTATE_WORKBENCH_ROOT` 或当前目录。开源仓库根目录包含 `web/`、`pipeline/`；已有业务工作区包含 `outputs/live-review/` 与 `knowledge/`。

```sh
python3 plugin/skills/estate-live-workbench/scripts/workspace.py --workspace . --check-dependencies
```

工具只读取文件与运行环境元数据，不启动分析。

## 开源网页

在仓库根目录运行：

```sh
cd web
npm ci
npm run dev
```

前端演示使用合成数据。接入自己的已审核数据时，以 `web/src/demo-data.js` 的结构为契约，保留项目、稳定人员ID、周度、累计、月度及证据音频字段。修改数据时相应更新周期，按计数与时长合并，不平均周百分比。

构建可直接使用 `npm run build`，也可用本技能包装器：

```sh
python3 plugin/skills/estate-live-workbench/scripts/report_build.py --project-dir web --run
```

默认仅打印构建计划；`--run` 执行构建。

## 分析流水线

`pipeline/` 提供完整录音采集、转写归一化、语音分析、缺口补转、音频归档和七项评分CLI。参数见各脚本 `--help` 与仓库 `docs/usage.md`。评分输入样例在 `tests/fixtures/synthetic-hosts.json`。

七项权重：留资25%、互动11%、评论后留资16%、价值讲透5%、表达组织11%、小风车16%、静默16%。逐主播按稳定ID汇总，评论结果连接原问题、实际答法和后续提交；缺项保留证据范围。人员与账号从当前项目配置读取。

## 连接已有业务工作区

可传 `--workspace`、`--project`、`--week` 发现已有周目录与阶段入口。专用审核和构建器按目标工作区解析，业务资料保留在该工作区。旧报告采用其他构建器时，包装器的 `--week-root` 模式可通过 `--node`、`--data-app`、`--python` 指定已安装环境；开源网页本身只需Node和npm。

## 交付

完成网页修订后构建并检查受影响的项目、周期、评分、评论与音频。发布目的地依据用户任务确定；需要部署时使用该项目自己的配置。保存实际结果和入口，不以内部进度代替报告。
