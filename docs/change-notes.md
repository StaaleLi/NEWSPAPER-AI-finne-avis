# Change Notes

## 2026-06-11

这次主要改动围绕“信源可靠性”和“筛选误判”。

### Source Changes

- 移除人民网 RSS，因为它返回的不是当天新闻，导致 5 个来源 `today_count=0`。
- 新增参考消息 5 个 JSON 来源：中国、国际、科技应用、产经、观点。
- README 和网页说明同步改成参考消息、新华网、环球网、NRK、VG。

### Classification Changes

- AI 关键词不再从栏目名里自我命中，只看标题和摘要。
- `AI` 改为边界匹配，避免命中 `Spain`、`campaign`、`email`。
- 增加包含关系去重，避免 `大模型` 和 `模型` 同时计分。
- 挪威侧去掉普通 `/nyheter/` 自动保留，减少国际泛新闻混入。
- 增加文化娱乐类排除词，例如 `mote`、`museum`、`kunst`、`festival`。

### Enrichment Changes

- 文章抓取预算按中挪两条流分配，不让挪威侧优先吃完整个预算。
- NRK 正文提取过滤部分时间、栏目和 `Nyhetssenter` 噪声。
- 挪威标题说明改成“中文提示”，不再假装做完整翻译。

### Verification

- `python -m compileall ai_builder_digest tests` 通过。
- `news-digest --target-date 2026-06-11 --no-cache --max-article-fetches 20` 成功生成日报。

