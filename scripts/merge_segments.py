# -*- coding: utf-8 -*-
"""按原范围一次性整合烧录双语字幕，并校验成片时长与原要求一致。
用法:
  python merge_segments.py --video V.mp4 --range-start 3720 --range-end 11296 \
      --cues cues.json --out out.mp4 [--ffmpeg PATH] [--ffprobe PATH]

cues.json: {"seg_key":[[start,end,原文,译文], ...], ...}
  时间相对 range-start；本脚本会把所有分段 cue 合并后按原范围烧录（不拼接分段文件）。
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAKE_SUBS = os.path.join(HERE, "make_bilingual_subs.py")
PY = sys.executable


def ass_filter_path(p):
    if os.name == "nt":
        return p.replace("\\", "/").replace(":", "\\:")
    return p


def resolve_tool(value, name):
    return value or shutil.which(name) or name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--range-start", type=float, required=True)
    ap.add_argument("--range-end", type=float, required=True)
    ap.add_argument("--cues", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ffmpeg", default=None, help="ffmpeg 可执行文件；默认从 PATH 查找")
    ap.add_argument("--ffprobe", default=None, help="ffprobe 可执行文件；默认从 PATH 查找")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--no-overwrite", action="store_true", help="输出文件已存在时直接报错，不覆盖")
    args = ap.parse_args()
    args.ffmpeg = resolve_tool(args.ffmpeg, "ffmpeg")
    args.ffprobe = resolve_tool(args.ffprobe, "ffprobe")

    if args.range_end <= args.range_start:
        print("[FAIL] range_end must be greater than range_start", file=sys.stderr)
        sys.exit(2)
    if args.no_overwrite and os.path.exists(args.out):
        print("[FAIL] output exists: %s" % args.out, file=sys.stderr)
        sys.exit(3)

    cues = json.load(open(args.cues, encoding="utf-8"))
    flat = []
    for key, rows in cues.items():
        for st, en, ja, zh in rows:
            if not ja:
                continue
            flat.append([float(st), float(en), ja, zh])
    flat.sort(key=lambda x: x[0])
    # 单调 + 去重叠 + 限制在 [0, 范围长度]
    length = args.range_end - args.range_start
    clean = []
    prev = -1.0
    for st, en, ja, zh in flat:
        st = max(0.0, st)
        en = min(length, en)
        if st < prev:
            st = round(prev + 0.05, 2)
        if en <= st:
            continue
        prev = en
        clean.append([round(st, 2), round(en, 2), ja, zh])

    if not clean:
        print("[warn] no valid cues; output will not contain subtitles")

    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    base = os.path.splitext(os.path.basename(args.out))[0]
    cue_path = os.path.join(out_dir, base + "_cues.json")
    with open(cue_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=1)
    subprocess.run([PY, MAKE_SUBS, cue_path, out_dir, base], check=True)

    ass = os.path.join(out_dir, base + ".ass")
    vf = "ass=filename='%s'" % ass_filter_path(ass)
    cmd = [args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-ss", "%.3f" % args.range_start, "-to", "%.3f" % args.range_end,
           "-i", args.video, "-vf", vf,
           "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", args.out]
    print("[encode] %s -> %s  cues=%d" % (args.range_start, args.range_end, len(clean)))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print("[FAIL] encode")
        sys.exit(r.returncode)

    p = subprocess.run([args.ffprobe, "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", args.out],
                       capture_output=True, text=True)
    if p.returncode != 0 or not p.stdout.strip():
        print("[FAIL] ffprobe duration check failed: %s" % p.stderr.strip(), file=sys.stderr)
        sys.exit(p.returncode or 1)
    try:
        dur = float(p.stdout.strip())
    except ValueError:
        print("[FAIL] invalid duration from ffprobe: %s" % p.stdout.strip(), file=sys.stderr)
        sys.exit(1)
    diff = abs(dur - length)
    ok = diff <= 0.5
    print("expected=%.2fs  actual=%.2fs  diff=%.2fs  %s" % (
        length, dur, diff, "PASS" if ok else "FAIL"))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
