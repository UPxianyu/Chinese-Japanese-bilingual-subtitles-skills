# 歌词来源与提供方式

歌词来源应当是可选、可替换的。不要默认强制访问 mojigeci。

## 优先级

1. 用户主动提供的官方歌词、LRC、翻译文件或文本。
2. 用户明确授权使用的第三方歌词来源，例如 mojigeci。
3. ASR 转写 + 校对 + 翻译兜底。

如果用户没有提供歌词来源，先询问；问不到时使用 ASR 转写后校对翻译，并把来源标注为 `ASR`。

## 用户提供文件

推荐用户提供以下任一形式：

- 每首歌的 LRC 文件；
- 一个 JSON 文件，字段包含 `name`、`artist`、`lyrics`、`tlyric`；
- 纯文本歌词和对应译文。

`scripts/moji_fetch.py --provider file` 支持读取本地 JSON 歌词文件。

## mojigeci provider

mojigeci 不再内置签名密钥。使用前设置环境变量：

```bash
export MOJIGECI_SECRET="你的密钥"
```

PowerShell：

```powershell
$env:MOJIGECI_SECRET = "你的密钥"
```

然后调用：

```bash
python scripts/moji_fetch.py --provider mojigeci search "花譜 糸"
```

如果未配置 `MOJIGECI_SECRET`，脚本会给出明确提示并停止，不会静默使用公开默认值。
