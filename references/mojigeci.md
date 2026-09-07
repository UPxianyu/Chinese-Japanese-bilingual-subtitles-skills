# mojigeci.com 歌词查询方法

## 何时使用

演唱会歌词与中文翻译的**可选来源之一**。用户提供歌词/LRC 时优先使用；未配置密钥、未获授权、找不到、缺句或译文明显错误时，退回 ASR 校对文本。

## 网址与入口

- 首页：https://mojigeci.com/zh-Hans
- 网页搜索：https://mojigeci.com/zh-Hans/search?q=<歌名 歌手>
- 建议用「歌名 + 歌手/团体名」组合搜索，减少同名误配。

## 接口（推荐直接调用 scripts/moji_fetch.py）

接口无需登录 Cookie，但需要正确的签名与请求头。签名密钥不再内置在脚本中，使用前设置 `MOJIGECI_SECRET`。Base 为 `https://mojigeci.com/zh-Hans/`。

### 1. 搜索：`api/search_lists`

GET 参数：

- `keyword`：关键词（歌名 + 歌手）
- `page`：页码，从 1 开始
- `pageSize`：每页条数（常用 12）
- `timestamp`：毫秒时间戳（脚本自动生成）
- `signature`：`sha256(keyword + str(timestamp) + MOJIGECI_SECRET)`

返回路径：`res["data"]["data"]` 为数组，每条含 `id`、`name`、`artist`（数组）。

### 2. 取歌词：`api/get_lyrics_by_id`

GET 参数：

- `id`：搜索结果的 `id`
- `song_name`、`song_artist`、`song_cover`：可留空
- `keyword`：可留空或填原关键词
- 同样带 `timestamp` 与 `signature`

返回路径：`res["data"]["data"]`，主要字段：

- `lyrics`：原文 LRC 文本
- `tlyric`：中文翻译 LRC 文本
- `name` / `artist` / `cover` / `audio_url`

### 3. 请求头（必带）

```text
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36
Referer: https://mojigeci.com/zh-Hans
Accept: application/json
Accept-Language: zh-CN,zh;q=0.9,ja;q=0.8
```

## LRC 解析与清洗

- 时间标签形如 `[mm:ss.SS]` 或 `[mm:ss.SSS]`；一行可能有多个标签。
- `lyrics` 头部常带 `作词/作曲/编曲/演唱` 等元数据行，需过滤，只保留正文。
- `tlyric` 常以 `[by:xxx]` 开头，并含大量只有时间戳、正文为空的行，需跳过空正文。
- 过滤后按时间戳排序，即得到「原文 / 译文」可对轴的歌词行。

脚本里的 `parse_lrc()` 已默认过滤常见元数据行；如需要保留元数据，可传 `keep_metadata=True`。

## 使用策略

1. 先确认演出标题、歌手/团体与官方歌单，逐首生成关键词。
2. 每首用 `python scripts/moji_fetch.py --provider mojigeci search "歌名 歌手"` 搜索，选 id（优先歌手匹配、`lyrics` 非空）。
3. 用 `python scripts/moji_fetch.py --provider mojigeci lyrics <id> [关键词]` 取 `lyrics` 与 `tlyric`。
4. 原文取 `lyrics`；中文译文优先取 `tlyric`，但需按「信达雅」润色（tlyric 可能直译、漏译，或时间轴与原文不一致）。
5. 团体曲/翻唱按「歌名 + 团体名（如 V.W.P / KAMITSUBAKI）」检索；用户给出官方歌单曲名时，用官方曲名检索。
6. 找不到或缺句时，用 ASR 词级时间戳补齐，并在校对说明里标注来源。

## 命令行示例

```bash
export MOJIGECI_SECRET="你的密钥"
python scripts/moji_fetch.py --provider mojigeci search "花譜 糸"
python scripts/moji_fetch.py --provider mojigeci searchall "花譜 糸" --out moji_糸.json
python scripts/moji_fetch.py --provider mojigeci lyrics 1399849873 糸
python scripts/moji_fetch.py --provider mojigeci song "花譜 糸" --out moji_糸_song.json
```
