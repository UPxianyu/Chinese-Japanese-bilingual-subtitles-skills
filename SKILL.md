---
name: concert-bilingual-subtitles
description: 为演唱会/LIVE/现场音乐视频制作并烧录双语字幕（原文+译文，信达雅），支持指定原语言与时间范围。流程为：查询歌单→抽音频→ASR→优先扒 mojigeci 官方歌词并对轴→校对翻译→先按歌曲/段落分段输出供用户审核修改→用户确认后再按原范围一次性整合并校验成片时长与原要求一致。当用户要求给演唱会、现场演出、音乐视频加字幕、配双语字幕、先分段审核再合并时使用；不适用于不需要歌词/词级对轴的普通纯翻译字幕。
---

# 演唱会双语字幕

把「查询歌单 → 抽音频 → ASR → 扒官方歌词并对轴 → 校对翻译 → 分段交付 → 审核迭代 → 按原范围整合」作为固定流水线执行。

> 下文 `scripts/` 均指本 skill 目录下的 `scripts/`。若当前工作目录不是 skill 目录，请改用绝对路径调用；运行 ASR 脚本时优先使用 `.venv-asr` 内的 Python，而不是系统 Python。

## 输入确认

先确认：视频绝对路径、起止范围（HH:MM:SS 或秒）、原声语言、译文语言、是否烧录进画面、双语排版（默认原文在上译文在下、原文字号小 2）、字体（中文 Microsoft YaHei、日文 Meiryo）。

同时确认：演出/演唱会标题、歌手或团体名、场次，以及官方歌单来源（用户提供或需自行检索）。

## 工具准备（一次性，优先国内镜像）

- ffmpeg：需带 libass + libx264 的完整版（`ffmpeg -filters` 含 `ass`、`-encoders` 含 `libx264`）。缺则从 npmmirror 的 `ffmpeg-static/b6.1.1` 下载 `ffmpeg-win32-x64.gz` 与 `ffprobe-win32-x64.gz` 解压。
- Python 环境：`python -m venv .venv-asr`，然后 `python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple faster-whisper`。Windows 后续用 `.venv-asr\Scripts\python.exe`，macOS/Linux 用 `.venv-asr/bin/python` 或先 `source .venv-asr/bin/activate`。
- CUDA（可选，RTX）：`.venv-asr\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "nvidia-cublas-cu12>=12.8,<13" "nvidia-cudnn-cu12>=9.8,<10"`，运行前把 `site-packages\nvidia\{cudnn,cublas,nvrtc}\bin` 加入 PATH。
- 模型：需要词级时间戳必须用标准 Whisper（kotoba 的 `word_timestamps` 会闪退）。优先 `Systran/faster-whisper-large-v3`；大文件卡死时改用魔搭 `https://modelscope.cn/api/v1/models/Systran/faster-whisper-large-v3/repo?Revision=master&FilePath=model.bin`。
- 歌词检索：`scripts/moji_fetch.py` 为纯标准库实现，无需额外安装；详细用法见 [references/mojigeci.md](references/mojigeci.md)。

## 执行步骤

### 1. 抽音频并转写

- `ffmpeg -ss <range_start> -to <range_end> -i <video> -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav`
- `<venv-python> scripts/asr_transcribe.py audio.wav <model> --lang <原语言> --word-timestamps --out segments.json`
- 必须保留 `words` 词级时间戳（后续对轴靠它）。

### 2. 查询演唱会歌单并扒官方歌词（演唱会关键）

- 先确定演出标题、歌手/团体名与场次，并通过网络搜索或用户提供的 setlist 整理出曲目清单；MC 与未公开新曲也一并记录。
- 歌词与中文翻译**优先使用 mojigeci**：用 `scripts/moji_fetch.py` 按「歌名 + 歌手」搜索并抓取 `lyrics`（原文）与 `tlyric`（中文翻译）。接口、签名、清洗规则见 [references/mojigeci.md](references/mojigeci.md)。
- 找不到、缺句或明显错误时，退回 ASR 校对文本（MC、口白、未公开新曲默认用 ASR）。
- 把每首歌整理成「歌词行 + 参考 LRC 时间 + 译文」结构，供后续对轴使用。

### 3. 对轴（本流程核心）

- 不要用「整段文本 bigram 匹配」自动对齐（快歌/rap、同音误听时会整段错乱）。
- 用 ASR 的**词级时间戳**逐句把官方歌词行映射到现场时间：读 `segments.json` 每个 segment 的 `words[].s/e`，纠正同音错字后给每句歌词定 [start,end]。
- 间奏、纯音乐、chant 段：留白或标 ♪；口白 intro 若 ASR 漏捕，标注为估算并提示用户复核。
- 单条 0.5–8s；过长句按语义拆开；保证时间单调、无重叠。

### 4. 校对翻译

- 原文：修正 ASR 同音/语法错、补标点、统一专有名词。
- 译文：做到信达雅——不偏离原意（信）、口语自然（达）、用词得体（雅），逐句复核。
- 排版：原文每行 ≤28 字、译文每行 ≤26 字；每 cue 只两行（原文上、译文下），禁止折行/叠加。

### 5. 分段交付（先给用户审核）

- 把每首歌/每段写进 `cues.json`：`{"key":[[start,end,原文,译文],...]}`，时间相对 `range_start`。
- 写 `manifest.json`：`[{"key":"01_糸","name":"糸","start":259.0,"end":432.0},...]`，`start/end` 同样相对 `range_start`。
- 运行 `python scripts/build_segments.py --video <V> --range-start <S> --manifest manifest.json --cues cues.json --out-dir output/切段`。
- 每个分段输出带序号的 mp4 + ass + srt 与清单，交用户逐段检查。

### 6. 审核迭代

- 用户指出某段某句问题 → 只改该段 `cues.json` 对应条目 → 用 `--only <key>` 重烧该段。
- 重复直到用户确认。

### 7. 按原范围整合（用户下整合命令后）

- `python scripts/merge_segments.py --video <V> --range-start <S> --range-end <E> --cues cues.json --out out.mp4`
- 它把全部 cue 按原范围一次性烧录（不是拼接分段文件），并用 ffprobe 校验成片时长 ≈ `range_end - range_start`。
- 合并后时长必须与原要求一致（±0.5s 内）；不一致则检查 cue 越界/重叠后修正重烧。

### 8. 验证

- 抽关键帧（首尾、长句、快语速、chant 段）用 vision 读图，核对两行完整、无裁切/重叠、原文字号更小。
- ffprobe 终检：时长、分辨率、音轨。

## 关键决策

- 帧精确：输入侧 `-ss` + 重编码，不用 `-c copy`。
- 合并长度一致：最终整合必须从源视频按原范围重编码，绝不 concat 带 padding 的分段文件。
- 双语排版：原文上、译文下，原文 fontsize 小 2 号；中文 Microsoft YaHei，日文 Meiryo。
- 歌词来源：官方词优先 mojigeci（`lyrics` 原文 + `tlyric` 中文），缺失才用 ASR 校对。
- 交付物：分段 mp4/ass/srt + 清单 + 校对说明（记录纠错与翻译取舍）。
