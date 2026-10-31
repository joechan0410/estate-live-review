# 直播复盘演示网页

独立的 React + Vite 前端，包含周度、累计、月度切换，三个示例项目，主播七维评分、价值点覆盖、评论问答、详细数据与 CSV 导出。蓝黑报告组件通过本目录中的轻量数据接口运行。

## 本地运行

需要 Node.js 22.12 或更新版本。

```sh
cd web
npm ci
npm run dev
```

打开终端显示的本地地址。页面默认显示第 2 周；可在页面切换第 1 周，或使用 `?week=2026-09-12`。项目选择会写入 URL，累计与月度使用 `period` 参数。

```sh
npm test
npm run build
npm run preview
```

`dist/` 为静态构建产物。Vite 使用相对资源路径，可放在静态服务器的子目录中。

## 演示数据

`src/demo-data.js` 在浏览器内生成固定的合成数据：2026 年 9 月 6—12 日、13—19 日两周，示例楼盘 A、B、C，以及各项目的主播甲、乙、丙。累计计数相加，主播评分按分析时长加权；月度视图引用这两周累计数据。所有查询均带 `synthetic-demo-generator` 来源标识。

音频 `public/audio/demo-tones.wav` 是程序生成的 24 秒提示音，用于体验播放、片段定位与结束位置控制。它与合成讲解文本分别承担界面演示用途。可用 Python 标准库重新生成：

```sh
python3 scripts/generate-demo-audio.py
```

`src/report/audio-segments.json` 是空对象，预留给分段媒体映射。页面直接使用本地演示音频。

## 数据接口

`src/runtime.jsx` 自行实现报告所需的五个接口：

| 接口 | 用途 |
| --- | --- |
| `useDataApp` | 读取快照、标题、查询行与当前模式 |
| `DataComponent` | 渲染业务区块，展开对应行数据及来源 |
| `RichNarrative` | 使用 `react-markdown` 渲染说明文字 |
| `SortableRegion` | 容纳报告章节 |
| `SortableItem` | 渲染单个章节 |

报告以只读模式展示。入口 `src/main.jsx` 把快照传入 `ReviewProvider`；接入自己的数据时，可在此处替换 `buildDemoSnapshot` 的调用，并保持如下结构：

```js
{
  title: '直播复盘报告',
  report: { asOf: '2026-09-19' },
  queries: {
    weekly: {
      rows: [{ project: '项目名称', hours: 10, scenes: 7, comments: 30, leads: 8 }],
      source: { provider: 'your-source', source_weeks: ['2026-09-19'] }
    },
    // 其余查询结构见 src/demo-data.js。可选明细使用空 rows 数组。
  },
  periodViews: []
}
```

主要数据集合为 `weekly`、`daily`、`host_rollup`、`host_dimensions`、`host_content_summary`、`host_value_blocks`、`project_value_topics`、`question_details` 与对应审核明细。累计数据通过 `periodViews[].queryPrefix` 定位，月度可通过 `datasetsRef` 引用已声明的累计视图。

测试验证两周范围、项目与主播覆盖、七维权重、每日与周度汇总、累计计数、问答转化分母、数据来源、唯一 ID、媒体范围及子路径导航。
