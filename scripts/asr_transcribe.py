# -*- coding: utf-8 -*-
"""用 faster-whisper 转写音频，可输出词级时间戳 JSON。
用法: python asr_transcribe.py audio.wav <model-id-or-path> [--lang ja] [--word-timestamps] [--out segments.json]
"""
import json, sys


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("缺少 faster_whisper，请先在 .venv-asr 中安装：python -m pip install faster-whisper")
        return
    audio = args[0]
    model_id = args[1]
    lang = None
    out = "segments.json"
    word_ts = False
    if "--lang" in args:
        lang = args[args.index("--lang") + 1]
    if "--out" in args:
        out = args[args.index("--out") + 1]
    if "--word-timestamps" in args:
        word_ts = True
    device = "cuda"
    try:
        model = WhisperModel(model_id, device="cuda", compute_type="float16")
    except Exception:
        model = WhisperModel(model_id, device="cpu", compute_type="int8")
        device = "cpu"
    kwargs = dict(language=lang, beam_size=5, word_timestamps=word_ts,
                  condition_on_previous_text=False)
    segments, info = model.transcribe(audio, **kwargs)
    data = []
    for s in segments:
        words = []
        for w in (s.words or []):
            words.append({"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2)})
        data.append({"start": round(s.start, 2), "end": round(s.end, 2),
                     "text": s.text.strip(), "words": words})
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("device:", device, "lang:", info.language, "segments:", len(data))


if __name__ == "__main__":
    main()
