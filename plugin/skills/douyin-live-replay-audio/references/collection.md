# 采集约束与字段

在用户已登录浏览器中核对项目/场次，从页面真实产生的响应获得数据。本次验证过的Cluerich路径为：

- `/bff/statistic/live-screen/v3/get-live-replay?roomId=<已观察id>` → `data.replayUrl`。
- `/bff/statistic/live-screen/overview` → `data.statRows[0].metrics`。
- `/bff/statistic/live-screen/clue-detail` → `data.list[].fields`，含留资时间和路径。
- `/bff/statistic/live-comment/comment-list` → `data.comments[]` 与 `data.total`。
- `/bff/statistic/live-comment/clue-detail` → `data.statRows[].fields.sec_uid`，可在本场内建立匿名评论客户与已留资标记。不能把这里的标记当成精确留资时间。

这些是2026-09-12实际观察，不保证未来兼容。不可在未观察之前猜测接口参数或字段。页面按场次切换后，响应要与对应roomId/时间范围核验。读取UI明确的整场直播，投放期间和自然/付费范围不能混用。

主要指标：`lp_screen_live_watch_uv`（场次看播人数）、`lp_screen_clue_uv`（全场景线索人数）、`lp_screen_live_icon_click_count`（小风车点击）、`lp_screen_live_comment_count`（评论次数）、`lp_screen_live_stat_cost`（消耗）、`lp_screen_live_avg_watch_duration`（平均看播秒）。金额/人数分母以实际UI说明为准。

HLS时间：`EXT-X-PROGRAM-DATE-TIME`指向片段时刻，必须结合累计`EXTINF`；不把它直接当字幕说话开始。校验 discontinuity、时间戳回退、头尾缺段。媒体播放列表可能短于后台直播，分别报告。

视频TS剥离188字节包头和adaptation字段后，按PID拼接payload，再读取字幕JSON。完整下载同步编码MP3并验证全段解码，不长期保存WAV/M4A；本包未覆盖加密、字节区间、fMP4或主播放列表，检测到即停止并选择支持这些结构的成熟HLS工具。不得破除访问保护。

匿名化：只保留评论内容、时间、会话内客户编号、是否运营账号和是否本场留资；姓名/电话/账号标识不进入公开报告。需要同客户时间链时在工作内存中关联，再导出匿名结果。
