# -*- coding: utf-8 -*-
"""用 faster-whisper 转写音频，可输出词级时间戳 JSON。

用法:
  python asr_transcribe.py audio.wav <model-id-or-path> \
      --lang ja --word-timestamps --out segments.json
"""
import argparse
import json
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="faster-whisper 音频转写")
    parser.add_argument("audio")
    parser.add_argument("model")
    parser.add_argument("--lang", default=None)
    parser.add_argument("--word-timestamps", action="store_true")
    parser.add_argument("--out", default="segments.json")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--compute-type", default=None)
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--condition-on-previous-text", action="store_true")
    args = parser.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("缺少 faster_whisper，请先在 .venv-asr 中安装：python -m pip install faster-whisper")
        return

    device = args.device
    compute_type = args.compute_type
    model = None
    if device in ("auto", "cuda"):
        try:
            model = WhisperModel(args.model, device="cuda", compute_type=compute_type or "float16")
            device = "cuda"
        except Exception:
            if args.device == "cuda":
                raise
            model = WhisperModel(args.model, device="cpu", compute_type=compute_type or "int8")
            device = "cpu"
    else:
        model = WhisperModel(args.model, device="cpu", compute_type=compute_type or "int8")
        device = "cpu"

    kwargs = dict(
        language=args.lang,
        beam_size=args.beam_size,
        word_timestamps=args.word_timestamps,
        condition_on_previous_text=args.condition_on_previous_text,
    )
    segments, info = model.transcribe(args.audio, **kwargs)
    data = []
    for s in segments:
        words = []
        for w in (s.words or []):
            words.append({"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2)})
        data.append({
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "text": s.text.strip(),
            "words": words,
        })

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("device:", device, "lang:", info.language, "segments:", len(data))


if __name__ == "__main__":
    main()
