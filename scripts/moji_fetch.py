# -*- coding: utf-8 -*-
"""歌词来源获取工具。

支持可插拔歌词来源：mojigeci 与本地 JSON 文件。mojigeci 不再内置签名密钥，
需要通过环境变量 `MOJIGECI_SECRET` 或 `--secret` 提供。

用法:
  python moji_fetch.py --provider mojigeci search "花譜 糸"
  python moji_fetch.py --provider mojigeci searchall "花譜 糸" --out result.json
  python moji_fetch.py --provider mojigeci lyrics <song_id> [关键词]
  python moji_fetch.py --provider mojigeci song "花譜 糸" --out song.json
  python moji_fetch.py --provider file song ./lyrics.json

返回结构:
  search/searchall -> JSON 数组 [{id, name, artist, ...}, ...]
  lyrics/song      -> JSON 对象 {id, name, artist, lyrics, tlyric, ...}
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(RuntimeError):
    pass


class ProviderConfigError(ProviderError):
    pass


class LyricProvider:
    """歌词来源统一接口。"""

    name = "base"

    def search(self, keyword: str, page: int = 1, page_size: int = 12):
        raise NotImplementedError

    def fetch(self, song_id, keyword: str = ""):
        raise NotImplementedError


class MojigeciProvider(LyricProvider):
    name = "mojigeci"
    BASE = "https://mojigeci.com/zh-Hans/"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Referer": "https://mojigeci.com/zh-Hans",
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8",
    }

    def __init__(self, secret: str | None = None, timeout: int = 60, retries: int = 3):
        self.secret = (secret or os.environ.get("MOJIGECI_SECRET") or "").strip()
        if not self.secret:
            raise ProviderConfigError(
                "缺少 mojigeci 签名密钥。请设置环境变量 MOJIGECI_SECRET，"
                "或改用用户提供的歌词/ASR 兜底。"
            )
        self.timeout = timeout
        self.retries = retries

    def _signature(self, keyword: str, ts: int) -> str:
        return hashlib.sha256((keyword + str(ts) + self.secret).encode("utf-8")).hexdigest()

    def _request(self, path: str, params: dict) -> dict:
        params = dict(params)
        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._signature(str(params.get("keyword", "")), params["timestamp"])
        url = self.BASE + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self.HEADERS)
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.retries - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise ProviderError("mojigeci HTTP %s: %s" % (exc.code, exc.reason)) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt < self.retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise ProviderError("mojigeci 网络错误: %s" % exc) from exc
        raise ProviderError("mojigeci 请求失败: %s" % last_error)

    def search(self, keyword: str, page: int = 1, page_size: int = 12):
        res = self._request("api/search_lists", {"keyword": keyword, "page": page, "pageSize": page_size})
        return (res.get("data") or {}).get("data") or []

    def fetch(self, song_id, keyword: str = ""):
        res = self._request("api/get_lyrics_by_id", {
            "id": song_id,
            "song_name": "",
            "song_artist": "",
            "song_cover": "",
            "keyword": keyword,
        })
        return (res.get("data") or {}).get("data") or {}


class FileProvider(LyricProvider):
    """读取本地 JSON 歌词文件，字段至少包含 lyrics，建议包含 tlyric。"""

    name = "file"

    def search(self, keyword: str, page: int = 1, page_size: int = 12):
        return []

    def fetch(self, song_id, keyword: str = ""):
        path = song_id or keyword
        if not path or not os.path.isfile(path):
            raise ProviderError("找不到本地歌词文件: %s" % path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            data = data[0] if data else {}
        return data


PROVIDERS = {
    "mojigeci": MojigeciProvider,
    "file": FileProvider,
}

_META_MARKERS = ("作词", "作曲", "编曲", "演唱", "混音", "录音", "制作", "发行", "词曲")


def _is_metadata_body(body: str) -> bool:
    cleaned = re.sub(r"[\s:：　]", "", body)
    return any(cleaned.startswith(m) for m in _META_MARKERS)


def parse_lrc(text: str, keep_metadata: bool = False):
    """把 LRC 文本解析为 [(start_seconds, line), ...]。"""
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


def _build_provider(name: str, secret: str | None = None) -> LyricProvider:
    cls = PROVIDERS.get(name)
    if not cls:
        raise ProviderConfigError("未知歌词来源: %s" % name)
    if name == "file":
        return cls()
    return cls(secret=secret)


def _write_json(data, out: str | None, default: str):
    target = out or default
    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("saved ->", target)
    return target


def _print_items(items):
    for it in items:
        print(it.get("id"), "|", it.get("name"), "|", "、".join(it.get("artist") or []))


def build_parser():
    parser = argparse.ArgumentParser(description="可插拔歌词来源工具")
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="mojigeci")
    parser.add_argument("--secret", default=None, help="mojigeci 签名密钥；默认读取 MOJIGECI_SECRET")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search")
    p.add_argument("keyword")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page-size", type=int, default=12)
    p.add_argument("--out")

    p = sub.add_parser("searchall")
    p.add_argument("keyword")
    p.add_argument("--pages", type=int, default=3)
    p.add_argument("--out")

    p = sub.add_parser("lyrics")
    p.add_argument("song_id")
    p.add_argument("keyword", nargs="?", default="")
    p.add_argument("--out")

    p = sub.add_parser("song")
    p.add_argument("keyword")
    p.add_argument("--out")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        provider = _build_provider(args.provider, args.secret)
    except ProviderConfigError as exc:
        print("配置错误:", exc, file=sys.stderr)
        sys.exit(2)

    try:
        if args.command == "search":
            items = provider.search(args.keyword, args.page, args.page_size)
            print(json.dumps(items, ensure_ascii=False, indent=1)[:4000])
            if args.out:
                _write_json(items, args.out, "search.json")
        elif args.command == "searchall":
            items, seen = [], set()
            for page in range(1, args.pages + 1):
                batch = provider.search(args.keyword, page, 12)
                if not batch:
                    break
                for it in batch:
                    key = (it.get("id"), it.get("name"))
                    if key not in seen:
                        seen.add(key)
                        items.append(it)
            _write_json(items, args.out, "search.json")
            _print_items(items)
        elif args.command == "lyrics":
            data = provider.fetch(args.song_id, args.keyword)
            print(json.dumps(data, ensure_ascii=False, indent=1)[:5000])
            if args.out:
                _write_json(data, args.out, "lyrics.json")
        elif args.command == "song":
            items = provider.search(args.keyword, 1)
            if not items:
                if provider.name == "file":
                    data = provider.fetch(args.keyword, args.keyword)
                else:
                    print("no result for:", args.keyword)
                    return
            else:
                first = items[0]
                data = provider.fetch(first.get("id"), args.keyword)
                data = {"id": first.get("id"), "name": first.get("name"),
                        "artist": first.get("artist"), **data}
            _write_json(data, args.out, "song.json")
            print(data.get("id"), "|", data.get("name"),
                  "|", "、".join(data.get("artist") or []),
                  "| lyrics_len=", len(data.get("lyrics") or ""),
                  "| tlyric_len=", len(data.get("tlyric") or ""))
    except ProviderError as exc:
        print("歌词来源错误:", exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
