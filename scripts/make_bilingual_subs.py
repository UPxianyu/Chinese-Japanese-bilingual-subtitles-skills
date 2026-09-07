# -*- coding: utf-8 -*-
"""从 cues.json 生成双语字幕 ASS/SRT。

cues.json: [[start, end, 原文, 译文], ...]
用法: python make_bilingual_subs.py cues.json out_dir base_name [--font-ja 42] [--font-zh 44]
"""
import argparse
import json
import os


def ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return "%d:%02d:%05.2f" % (h, m, s)


def srt_time(t: float) -> str:
    total_ms = int(round(t * 1000))
    h = total_ms // 3600000
    m = (total_ms % 3600000) // 60000
    s = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


def escape_ass_text(text: str) -> str:
    """转义可能被 libass 解释为样式控制符的字符。"""
    text = str(text)
    text = text.replace("\\", "\\\\")
    text = text.replace("{", "\\{").replace("}", "\\}")
    return text


def build_ass(cues, font_ja, font_zh, font_ja_name, font_zh_name) -> str:
    header = """[Script Info]
Title: bilingual
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,%s,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2.2,0.8,2,30,30,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" % (font_zh_name, font_zh)
    lines = [header]
    for start, end, ja, zh in cues:
        text = "{\\fn%s\\fs%d}%s\\N{\\fn%s\\fs%d}%s" % (
            font_ja_name,
            font_ja,
            escape_ass_text(ja),
            font_zh_name,
            font_zh,
            escape_ass_text(zh),
        )
        lines.append("Dialogue: 0,%s,%s,Default,,0,0,0,,%s" % (ass_time(start), ass_time(end), text))
    return "\n".join(lines)


def build_srt(cues) -> str:
    blocks = []
    for i, (start, end, ja, zh) in enumerate(cues, 1):
        blocks.append("%d\n%s --> %s\n%s\n%s" % (i, srt_time(start), srt_time(end), ja, zh))
    return "\n\n".join(blocks)


def main() -> None:
    parser = argparse.ArgumentParser(description="从 cues.json 生成双语字幕 ASS/SRT")
    parser.add_argument("cues")
    parser.add_argument("out_dir")
    parser.add_argument("base")
    parser.add_argument("--font-ja", type=int, default=42)
    parser.add_argument("--font-zh", type=int, default=44)
    parser.add_argument("--font-ja-name", default="Meiryo")
    parser.add_argument("--font-zh-name", default="Microsoft YaHei")
    args = parser.parse_args()

    with open(args.cues, encoding="utf-8") as f:
        cues = json.load(f)
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, args.base + ".ass"), "w", encoding="utf-8") as f:
        f.write(build_ass(cues, args.font_ja, args.font_zh, args.font_ja_name, args.font_zh_name))
    with open(os.path.join(args.out_dir, args.base + ".srt"), "w", encoding="utf-8") as f:
        f.write(build_srt(cues))
    print("cues:", len(cues))


if __name__ == "__main__":
    main()
