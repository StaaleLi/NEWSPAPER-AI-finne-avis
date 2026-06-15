# Project Structure

这个项目的目标不是做一个静态新闻页面，而是做一条可以复现的新闻处理流水线：

```text
fetch -> classify -> enrich -> audit -> render -> persist
```

## Core Package

`ai_builder_digest/` 是核心代码目录。

- `sources.py`：集中维护新闻来源。当前包含参考消息、新华网、环球网、NRK、VG。
- `fetchers.py`：抓取 RSS、HTML 页面和参考消息 JSON 列表，并把原始内容转成统一的 `DigestItem`。
- `classifier.py`：关键词筛选和打分逻辑，区分中国时政 / AI产业和挪威 / NATO / EØS 两条信息流。
- `article.py`：正文提取和噪声过滤，避免把导航、版权、面包屑当作正文。
- `enrich.py`：生成摘要、重要性说明、可信度提示和 claim check。
- `render.py`：把结构化结果渲染成 `site/index.html`。
- `storage.py`：把每日结果和来源审查写入 SQLite。
- `llm.py`：可选 LLM 二次摘要和判断，只有设置 `OPENAI_API_KEY` 后才使用。
- `cli.py`：命令行入口，串联完整流程。

## Tests

`tests/` 放离线测试。测试重点不是模拟真实网络，而是覆盖容易出错的本地逻辑：

- 关键词匹配不能误命中英文单词内部；
- 旧日期和非目标日期会被过滤；
- 环球网隐藏块解析失败时能回退到普通链接解析；
- SQLite 可以保存每日结果；
- 挪威体育、娱乐、文化噪声会被排除。

## Generated Output

这些目录是运行后生成的，不建议作为源码提交：

- `site/`：网页日报；
- `data/`：JSON、缓存、SQLite 历史库；
- `__pycache__/`、`.pytest_cache/`、`*.egg-info/`：Python 本地缓存。

