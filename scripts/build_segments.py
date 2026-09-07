# -*- coding: utf-8 -*-
"""按分段清单生成并烧录双语字幕片段（供审核）。
用法:
  python build_segments.py --video V.mp4 --range-start 3720 \
      --manifest segs.json --cues cues.json --out-dir OUT \
      [--range-end 11296] [--pad 3] [--only KEY] [--ffmpeg PATH] [--crf 21]

manifest.json: [{"key":"01_糸","name":"糸","start":259.0,"end":432.0}, ...]
  start/end 为相对 range-start 的秒数（即整段视频内的相对秒）。
cues.json: {"01_糸":[[start,end,原文,译文], ...], ...}
  时间同样相对 range-start。
"""
import argparse, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAKE_SUBS = os.path.join(HERE, "make_bilingual_subs.py")
PY = sys.executable


def safe_key(key):
    return re.sub(r"[^\w\u4e00-\u9fff\-]", "_", key).strip("_") or "seg"


def ass_filter_path(p):
    return p.replace("\\", "/").replace(":", "\\:")


def fmt_hms(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    return "%02d:%02d:%02d" % (h, m, s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--range-start", type=float, required=True,
                    help="整段视频起点（秒），例如 1:02:00 = 3720")
    ap.add_argument("--range-end", type=float, default=None,
                    help="整段视频终点（秒）；提供后会把分段外扩限制在原范围内")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--cues", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--pad", type=float, default=3.0)
    ap.add_argument("--only", default=None, help="只处理 key 含该子串的分段")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--crf", type=int, default=21)
    ap.add_argument("--preset", default="veryfast")
    args = ap.parse_args()

    manifest = json.load(open(args.manifest, encoding="utf-8"))
    cues = json.load(open(args.cues, encoding="utf-8"))
    os.makedirs(args.out_dir, exist_ok=True)

    summary = []
    for seg in manifest:
        key, name, start, end = seg["key"], seg["name"], float(seg["start"]), float(seg["end"])
        if args.only and args.only not in key and args.only not in name:
            continue
        rows = cues.get(key, [])
        max_seg_end = None
        if args.range_end is not None:
            max_seg_end = args.range_end - args.range_start
        seg_start = max(0.0, start - args.pad)
        seg_end = end + args.pad
        if max_seg_end is not None:
            if seg_start >= max_seg_end:
                print("[skip] %s outside range" % key)
                continue
            seg_end = min(seg_end, max_seg_end)
        rel = []
        for st, en, ja, zh in rows:
            st = round(st - seg_start, 2)
            en = round(en - seg_start, 2)
            if en <= 0 or not ja:
                continue
            if en - st < 0.3:
                continue
            rel.append([max(0.0, st), en, ja, zh])
        rel.sort(key=lambda x: x[0])
        if not rel:
            print("[skip] %s no cues" % key)
            continue

        sk = safe_key(key)
        cue_path = os.path.join(args.out_dir, sk + "_cues.json")
        with open(cue_path, "w", encoding="utf-8") as f:
            json.dump(rel, f, ensure_ascii=False, indent=1)
        subprocess.run([PY, MAKE_SUBS, cue_path, args.out_dir, sk], check=True)

        ass = os.path.join(args.out_dir, sk + ".ass")
        mp4 = os.path.join(args.out_dir, sk + ".mp4")
        vf = "ass=filename='%s'" % ass_filter_path(ass)
        cmd = [args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
               "-ss", "%.3f" % (args.range_start + seg_start),
               "-to", "%.3f" % (args.range_start + seg_end),
               "-i", args.video, "-vf", vf,
               "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", mp4]
        print("[encode] %s  %s -> %s  cues=%d" % (
            key, fmt_hms(args.range_start + seg_start), fmt_hms(args.range_start + seg_end), len(rel)))
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print("[FAIL] %s" % key)
            continue
        summary.append({"file": sk + ".mp4", "name": name, "key": key,
                        "abs_start": fmt_hms(args.range_start + seg_start),
                        "abs_end": fmt_hms(args.range_start + seg_end),
                        "cues": len(rel)})

    with open(os.path.join(args.out_dir, "切段清单.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("done:", len(summary), "segments")
    for m in summary:
        print("%-28s %s - %s  %s" % (m["file"], m["abs_start"], m["abs_end"], m["name"]))


if __name__ == "__main__":
    main()
