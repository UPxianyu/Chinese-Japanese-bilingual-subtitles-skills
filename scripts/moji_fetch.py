# -*- coding: utf-8 -*-
"""mojigeci.com 歌词检索工具（演唱会双语字幕的官方歌词/翻译优先来源）。

纯标准库实现，无需 pip 安装依赖。用法:

  python moji_fetch.py search "花譜 糸"
  python moji_fetch.py searchall "花譜 糸" --out result.json
  python moji_fetch.py lyrics <song_id> [关键词]
  python moji_fetch.py song "花譜 糸" --out song.json   # 搜索取第一条并抓 lyrics+tlyric

返回结构:
  search/searchall -> JSON 数组 [{id, name, artist, ...}, ...]
  lyrics/song      -> JSON 对象 {id, name, artist, lyrics, tlyric, ...}

注意: 若网站更新了签名密钥（SECRET），需同步修改本文件中的 SECRET。
"""
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
import re

BASE = "https://mojigeci.com/zh-Hans/"
SECRET = "wmn_api_secret_2024_v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://mojigeci.com/zh-Hans",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
}


def signature(keyword: str, ts: int) -> str:
    return hashlib.sha256((keyword + str(ts) + SECRET).encode("utf-8")).hexdigest()


def api(path: str, params: dict) -> dict:
    params = dict(params)
    params["timestamp"] = int(time.time() * 1000)
    params["signature"] = signature(str(params.get("keyword", "")), params["timestamp"])
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_items(keyword: str, page: int = 1, page_size: int = 12):
    res = api("api/search_lists", {"keyword": keyword, "page": page, "pageSize": page_size})
    return (res.get("data") or {}).get("data") or []


def get_lyrics(song_id, keyword: str = ""):
    res = api("api/get_lyrics_by_id", {
        "id": song_id,
        "song_name": "",
        "song_artist": "",
        "song_cover": "",
        "keyword": keyword,
    })
    return (res.get("data") or {}).get("data") or {}


_META_MARKERS = ("作词", "作曲", "编曲", "演唱", "混音", "录音", "制作", "发行", "词曲")


def _is_metadata_body(body: str) -> bool:
    cleaned = re.sub(r"[\s:：　]", "", body)
    return any(cleaned.startswith(m) for m in _META_MARKERS)


def parse_lrc(text: str, keep_metadata: bool = False):
    """把 LRC 文本解析为 [(start_seconds, line), ...]。

    - 支持 [mm:ss.SS] 与 [mm:ss.SSS]，一行多个时间标签取最早值。
    - 跳过无时间标签或正文为空的行（含 tlyric 常见的 [by:xxx] 元信息行）。
    - 默认过滤「作词/作曲/编曲/演唱/混音」等带 [00:00.00] 的元数据行；传 keep_metadata=True 可保留。
    """
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        stamps = []
        body = line
        while body.startswith("["):
            end = body.find("]")
            if end == -1:
                break
            tag = body[1:end]
            body = body[end + 1:].lstrip()
            if ":" in tag:
                stamps.append(tag)
        seconds = []
        for tag in stamps:
            try:
                mm, ss = tag.split(":", 1)
                seconds.append(int(mm) * 60 + float(ss))
            except (ValueError, TypeError):
                pass
        if seconds and body and (keep_metadata or not _is_metadata_body(body)):
            out.append((min(seconds), body))
    return out


def _out_arg(argv):
    return argv[argv.index("--out") + 1] if "--out" in argv else None


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "search":
        kw = sys.argv[2]
        page = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        print(json.dumps(search_items(kw, page), ensure_ascii=False, indent=1)[:4000])
    elif cmd == "searchall":
        kw = sys.argv[2]
        out = _out_arg(sys.argv) or "moji_search.json"
        all_items, seen = [], set()
        for page in range(1, 4):
            items = search_items(kw, page)
            if not items:
                break
            for it in items:
                key = (it.get("id"), it.get("name"))
                if key not in seen:
                    seen.add(key)
                    all_items.append(it)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(all_items, f, ensure_ascii=False, indent=1)
        print("saved", len(all_items), "items ->", out)
        for it in all_items:
            print(it.get("id"), "|", it.get("name"), "|", "、".join(it.get("artist") or []))
    elif cmd == "lyrics":
        sid = sys.argv[2]
        kw = sys.argv[3] if len(sys.argv) > 3 else ""
        data = get_lyrics(sid, kw)
        out = _out_arg(sys.argv)
        if out:
            with open(out, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            print("saved ->", out)
        else:
            print(json.dumps(data, ensure_ascii=False, indent=1)[:5000])
    elif cmd == "song":
        kw = sys.argv[2]
        items = search_items(kw, 1)
        if not items:
            print("no result for:", kw)
            return
        first = items[0]
        data = get_lyrics(first.get("id"), kw)
        data = {"id": first.get("id"), "name": first.get("name"),
                "artist": first.get("artist"), **data}
        out = _out_arg(sys.argv) or "moji_song.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print("saved ->", out)
        print(data.get("id"), "|", data.get("name"),
              "|", "、".join(data.get("artist") or []),
              "| lyrics_len=", len(data.get("lyrics") or ""),
              "| tlyric_len=", len(data.get("tlyric") or ""))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
