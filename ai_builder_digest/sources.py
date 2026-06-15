from __future__ import annotations

from .models import Source


SOURCES: list[Source] = [
    Source("参考消息-中国", "https://ckxxapp.ckxx.net/json/channel/zhongguo/list.json", "cankaoxiaoxi", "国内时政", "CN"),
    Source("参考消息-国际", "https://ckxxapp.ckxx.net/json/channel/gj/list.json", "cankaoxiaoxi", "国际时政", "CN"),
    Source("参考消息-科技应用", "https://ckxxapp.ckxx.net/json/channel/kejiyy/list.json", "cankaoxiaoxi", "AI产业", "CN"),
    Source("参考消息-产经", "https://ckxxapp.ckxx.net/json/channel/cj/list.json", "cankaoxiaoxi", "AI产业", "CN"),
    Source("参考消息-观点", "https://ckxxapp.ckxx.net/json/channel/guandian/list.json", "cankaoxiaoxi", "评论", "CN"),
    Source("新华网-时政", "https://www.news.cn/politics/", "html", "国内时政", "CN"),
    Source("新华网-科技", "https://www.news.cn/tech/", "html", "AI产业", "CN"),
    Source("环球网-国际", "https://world.huanqiu.com/", "html", "国际时政", "CN"),
    Source("环球网-科技", "https://tech.huanqiu.com/", "html", "AI产业", "CN"),
    Source("NRK-最新新闻", "https://www.nrk.no/nyheter/siste.rss", "rss", "挪威/NATO/EØS", "NO"),
    Source("VG-最新新闻", "https://www.vg.no/rss/feed", "rss", "挪威/NATO/EØS", "NO"),
]
