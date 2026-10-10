#!/usr/bin/env python3
"""Reel auto-edit helper built on FFmpeg and faster-whisper.

Subcommands:
  check       Check FFmpeg / Whisper / Japanese fonts.
  clip        Cut the first N seconds of a video (smoke test).
  transcribe  Transcribe speech to JSON + SRT with word timestamps.
  analyze     Measure a reference video (cuts, silence, loudness) and dump frames.
  plan        Build an edit plan (keep ranges, telops, hook, BGM) from a transcript.
  render      Render a plan to a vertical 1080x1920 MP4.

The plan is a JSON file meant to be reviewed (and edited) before rendering.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FILLERS = {"えー", "えーと", "えっと", "えーっと", "あー", "あのー", "うーん", "んー", "うん", "まぁ", "まあ", "えと"}
PUNCT = "。、,.!?！？…・「」『』（）()"
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}


# ---------- helpers ----------

def run(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=capture, text=True)


def die(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_video(path: Path) -> Path:
    """Accept a video file or a folder (uses the first video inside)."""
    if path.is_dir():
        vids = sorted(p for p in path.iterdir() if p.suffix.lower() in VIDEO_EXTS)
        if not vids:
            die(f"{path} に動画が見つかりません。")
        if len(vids) > 1:
            print(f"注意: {path} に動画が{len(vids)}本あります。{vids[0].name} を使います。", file=sys.stderr)
        return vids[0]
    if not path.exists():
        die(f"{path} が見つかりません。")
    return path


def probe(path: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", str(path)])
    if r.returncode != 0:
        die(f"ffprobe に失敗しました: {r.stderr.strip()}")
    data = json.loads(r.stdout)
    info = {"duration": float(data["format"].get("duration", 0)), "has_audio": False}
    for s in data.get("streams", []):
        if s["codec_type"] == "video" and "width" not in info:
            num, den = s.get("r_frame_rate", "30/1").split("/")
            info.update(width=s["width"], height=s["height"],
                        fps=round(float(num) / float(den or 1), 2))
        elif s["codec_type"] == "audio":
            info["has_audio"] = True
    return info


def japanese_fonts() -> list[str]:
    if not shutil.which("fc-list"):
        return []
    r = run(["fc-list", ":lang=ja", "family"])
    names = []
    for line in r.stdout.splitlines():
        name = line.split(",")[0].strip()
        if name and name not in names:
            names.append(name)
    return names


def pick_font(wanted: str) -> str:
    fonts = japanese_fonts()
    if not fonts or wanted in fonts:
        return wanted
    for pref in ("Noto Sans CJK JP", "Noto Sans JP", "Hiragino Sans", "ヒラギノ角ゴシック",
                 "Yu Gothic", "游ゴシック", "Meiryo", "IPAGothic", "IPAexGothic"):
        if pref in fonts:
            return pref
    return fonts[0]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt_t(t: float) -> str:
    m, s = divmod(max(t, 0), 60)
    return f"{int(m)}:{s:05.2f}"


def silences(path: Path, noise_db: float, min_dur: float) -> list[tuple[float, float]]:
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
             "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}", "-f", "null", "-"])
    out, start = [], None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            out.append((start, float(m.group(1))))
            start = None
    if start is not None:
        out.append((start, probe(path)["duration"]))
    return out


# ---------- check / clip ----------

def cmd_check(args: argparse.Namespace) -> None:
    ok = True
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        print(f"{'OK ' if path else 'NG '} {tool}: {path or '入っていません'}")
        ok &= bool(path)
    if shutil.which("ffmpeg"):
        filters = run(["ffmpeg", "-hide_banner", "-filters"]).stdout
        has_sub = " subtitles " in filters
        print(f"{'OK ' if has_sub else 'NG '} テロップ機能(libass): {'あり' if has_sub else 'なし(libass 付きの FFmpeg が必要)'}")
        ok &= has_sub
    try:
        import faster_whisper  # noqa: F401
        print(f"OK  Whisper(faster-whisper {faster_whisper.__version__})")
    except ImportError:
        print("NG  Whisper: 入っていません(pip install faster-whisper)")
        ok = False
    fonts = japanese_fonts()
    print(f"{'OK ' if fonts else '?  '} 日本語フォント: {', '.join(fonts[:5]) if fonts else '見つかりません(fc-list が無い環境では確認できません)'}")
    print("\n使える状態です。" if ok else "\n足りないものがあります。上の NG を入れてください。")
    sys.exit(0 if ok else 1)


def cmd_clip(args: argparse.Namespace) -> None:
    src = resolve_video(Path(args.input))
    out = Path(args.output)
    if out.is_dir() or not out.suffix:
        out = out / f"{src.stem}_最初の{args.seconds:g}秒.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
             "-t", str(args.seconds), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)])
    if r.returncode != 0:
        die(r.stderr.strip())
    print(f"書き出しました: {out}({probe(out)['duration']:.2f}秒)")


# ---------- transcribe ----------

def cmd_transcribe(args: argparse.Namespace) -> None:
    src = resolve_video(Path(args.input))
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        die("Whisper が入っていません。`pip install faster-whisper` を実行してください。")
    try:
        model = WhisperModel(args.model, device="cpu", compute_type="int8")
    except Exception as e:  # model download can be blocked by the network
        die(f"Whisper のモデル「{args.model}」を読み込めません({type(e).__name__})。"
            "初回はインターネットからモデルをダウンロードします。ネットにつながる PC で実行するか、"
            "--model にダウンロード済みモデルのフォルダを指定してください。")
    segs, info = model.transcribe(str(src), language="ja", word_timestamps=True, vad_filter=True,
                                  initial_prompt=args.prompt)
    data = {"language": info.language, "source": str(src), "segments": []}
    for s in segs:
        data["segments"].append({
            "start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip(),
            "words": [{"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word.strip()}
                      for w in (s.words or [])],
        })
    out = Path(args.output) if args.output else src.with_suffix(".transcript.json")
    save_json(out, data)
    srt = []
    for i, s in enumerate(data["segments"], 1):
        srt.append(f"{i}\n{_srt_t(s['start'])} --> {_srt_t(s['end'])}\n{s['text']}\n")
    out.with_suffix(".srt").write_text("\n".join(srt), encoding="utf-8")
    print(f"文字起こしを保存しました: {out}")
    for s in data["segments"]:
        print(f"[{fmt_t(s['start'])}-{fmt_t(s['end'])}] {s['text']}")


def _srt_t(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


# ---------- analyze ----------

def cmd_analyze(args: argparse.Namespace) -> None:
    src = resolve_video(Path(args.input))
    info = probe(src)
    dur = info["duration"]
    out_dir = Path(args.output) if args.output else src.parent / f"{src.stem}_分析"
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-an",
             "-vf", f"select='gt(scene,{args.scene})',showinfo", "-f", "null", "-"])
    cuts = [float(m.group(1)) for m in re.finditer(r"pts_time:([\d.]+)", r.stderr)]
    bounds = [0.0] + cuts + [dur]
    shots = [round(b - a, 2) for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]

    result: dict = {"source": str(src), "duration": round(dur, 2),
                    "size": f"{info.get('width')}x{info.get('height')}", "fps": info.get("fps"),
                    "cuts": {"count": len(cuts), "times": [round(c, 2) for c in cuts],
                             "avg_shot_sec": round(sum(shots) / len(shots), 2) if shots else None,
                             "min_shot_sec": min(shots) if shots else None,
                             "max_shot_sec": max(shots) if shots else None}}
    if info["has_audio"]:
        sil = silences(src, args.noise, 0.2)
        gaps = [round(e - s, 2) for s, e in sil]
        vol = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-vn",
                   "-af", "volumedetect", "-f", "null", "-"]).stderr
        mean = re.search(r"mean_volume: ([-\d.]+)", vol)
        peak = re.search(r"max_volume: ([-\d.]+)", vol)
        result["audio"] = {"silences_over_0.2s": len(gaps), "longest_silence_sec": max(gaps) if gaps else 0,
                           "silence_ratio": round(sum(gaps) / dur, 3) if dur else None,
                           "mean_db": float(mean.group(1)) if mean else None,
                           "peak_db": float(peak.group(1)) if peak else None}
    else:
        result["audio"] = None

    # Frames for visual review: opening, every N sec, and right after each cut.
    times = sorted({0.0, 0.5, 1.0, *[t for t in _frange(2.0, dur, args.every)], *[c + 0.15 for c in cuts]})
    times = [t for t in times if t < dur][: args.max_frames]
    for t in times:
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(src),
             "-frames:v", "1", "-vf", "scale=360:-2", str(frames_dir / f"t{t:06.2f}.jpg")])
    result["frames_dir"] = str(frames_dir)
    result["frames"] = len(times)
    save_json(out_dir / "analysis.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n分析結果: {out_dir / 'analysis.json'}\nコマ画像: {frames_dir}(テロップの位置・色・大きさ、ズームはこの画像を見て判断する)")


def _frange(a: float, b: float, step: float):
    t = a
    while t < b:
        yield round(t, 2)
        t += step


# ---------- plan ----------

def _clean(text: str) -> str:
    return text.strip().strip(PUNCT).strip()


def cmd_plan(args: argparse.Namespace) -> None:
    src = resolve_video(Path(args.input))
    kata = load_json(Path(args.kata))
    info = probe(src)
    dur = info["duration"]
    tempo, telop = kata["tempo"], kata["telop"]

    words: list[dict] = []
    if args.transcript:
        tr = load_json(Path(args.transcript))
        for s in tr["segments"]:
            ws = s.get("words") or [{"start": s["start"], "end": s["end"], "word": s["text"]}]
            for i, w in enumerate(ws):
                words.append({**w, "seg_end": i == len(ws) - 1})

    removed: list[dict] = []
    if words:
        kept_words = []
        for w in words:
            if tempo.get("remove_fillers") and _clean(w["word"]) in FILLERS:
                removed.append({"start": w["start"], "end": w["end"], "reason": f"言いよどみ「{_clean(w['word'])}」"})
            else:
                kept_words.append(w)
        spans = [(max(0.0, w["start"] - tempo["pad_sec"]), min(dur, w["end"] + tempo["pad_sec"])) for w in kept_words]
    else:
        # No transcript: keep everything that is not silence.
        sil = silences(src, args.noise, tempo["max_gap_sec"]) if info["has_audio"] else []
        spans, cur = [], 0.0
        for s, e in sil:
            if s > cur:
                spans.append((max(0.0, cur - tempo["pad_sec"]), min(dur, s + tempo["pad_sec"])))
            cur = e
        if cur < dur:
            spans.append((max(0.0, cur - tempo["pad_sec"]), dur))
        kept_words = []

    keep: list[list[float]] = []
    for s, e in sorted(spans):
        if keep and s - keep[-1][1] <= tempo["max_gap_sec"]:
            keep[-1][1] = max(keep[-1][1], e)
        else:
            keep.append([s, e])
    keep = [[round(s, 3), round(e, 3)] for s, e in keep if e - s >= 0.15]
    if not keep:
        keep = [[0.0, round(dur, 3)]]
    prev = 0.0
    for s, e in keep:
        if s - prev > 0.05:
            removed.append({"start": round(prev, 3), "end": round(s, 3), "reason": "無音・間"})
        prev = e
    if dur - prev > 0.05:
        removed.append({"start": round(prev, 3), "end": round(dur, 3), "reason": "無音・間"})
    removed = _merge_removed(removed)

    telops = _build_telops(kept_words, telop["max_chars"])
    hook_text = args.hook if args.hook is not None else (telops[0]["text"] if telops else "")
    plan = {
        "source": str(src), "kata": str(args.kata), "kata_name": kata.get("name"),
        "source_duration": round(dur, 2),
        "keep": keep,
        "removed": removed,
        "telops": telops,
        "hook": {"enabled": kata["hook"]["enabled"] and bool(hook_text), "text": hook_text,
                 "duration_sec": kata["hook"]["duration_sec"]},
        "bgm": {"file": args.bgm or "", "volume": kata["sound"]["bgm_volume"]},
        "output": kata["output"],
    }
    plan["output_duration"] = round(sum(e - s for s, e in keep), 2)
    out = Path(args.output) if args.output else src.with_suffix(".plan.json")
    save_json(out, plan)
    md = plan_markdown(plan)
    out.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\n計画: {out}(直すときはこの JSON の keep / telops / hook / bgm を書き換える)")


def _merge_removed(removed: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for r in sorted(removed, key=lambda r: r["start"]):
        if merged and r["start"] <= merged[-1]["end"] + 0.02:
            m = merged[-1]
            m["end"] = max(m["end"], r["end"])
            if r["reason"] not in m["reason"]:
                m["reason"] += "・" + r["reason"]
        else:
            merged.append(dict(r))
    return merged


def _build_telops(words: list[dict], max_chars: int) -> list[dict]:
    telops, cur, start, end = [], "", None, None

    def flush():
        nonlocal cur, start
        text = _clean(cur)
        if text:
            telops.append({"start": round(start, 3), "end": round(end, 3), "text": text})
        cur, start = "", None

    for w in words:
        piece = w["word"].strip()
        if not piece:
            continue
        clean_piece = re.sub(f"[{re.escape('。、,.')}]", "", piece)
        if start is not None and (len(cur) + len(clean_piece) > max_chars or w["start"] - end > 0.6):
            flush()
        if start is None:
            start = w["start"]
        cur += clean_piece
        end = w["end"]
        if piece[-1:] in "。！？!?" or w.get("seg_end"):
            flush()
    flush()
    for a, b in zip(telops, telops[1:]):  # hold each telop until the next one (max +0.4s)
        a["end"] = round(min(b["start"], a["end"] + 0.4), 3)
    return telops


def plan_markdown(plan: dict) -> str:
    lines = [f"# 編集計画({plan.get('kata_name') or '型'})", "",
             f"- 元の長さ {plan['source_duration']}秒 → 書き出し {plan['output_duration']}秒"
             f"(残すところ {len(plan['keep'])} か所)",
             f"- 冒頭の大きい文字: {plan['hook']['text'] if plan['hook']['enabled'] else 'なし'}"
             f"({plan['hook']['duration_sec']}秒)",
             f"- BGM: {plan['bgm']['file'] or 'なし'}(音量 {plan['bgm']['volume']})", "",
             "## 切るところ", "", "| 元の時間 | 長さ | 理由 |", "| --- | --- | --- |"]
    for r in plan["removed"]:
        lines.append(f"| {fmt_t(r['start'])}〜{fmt_t(r['end'])} | {r['end'] - r['start']:.2f}秒 | {r['reason']} |")
    lines += ["", "## テロップ", "", "| # | 元の時間 | 文言 | 文字数 |", "| --- | --- | --- | --- |"]
    for i, t in enumerate(plan["telops"], 1):
        lines.append(f"| {i} | {fmt_t(t['start'])}〜{fmt_t(t['end'])} | {t['text']} | {len(t['text'])} |")
    return "\n".join(lines)


# ---------- render ----------

def _ass_color(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def _ass_t(t: float) -> str:
    cs = int(round(max(t, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", "\\N")


def map_time(t: float, keep: list[list[float]]) -> float | None:
    acc = 0.0
    for s, e in keep:
        if t < s:
            return acc
        if t <= e:
            return acc + (t - s)
        acc += e - s
    return None


def _fit(text: str, size: int, width: int) -> str:
    """Shrink the font so one line fits inside the frame (full-width chars ~ 1em)."""
    units = sum(1.0 if ord(c) > 0xFF else 0.55 for c in text)
    fit = int((width - 120) / max(units, 1))
    return f"{{\\fs{fit}}}" if fit < size else ""


def build_ass(plan: dict, kata: dict, font: str) -> str:
    out, tl, hk = plan["output"], kata["telop"], kata["hook"]
    hook_align = {"top": 8, "middle": 5, "bottom": 2}.get(hk.get("position", "top"), 8)
    bold = -1 if tl.get("bold", True) else 0
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {out['width']}", f"PlayResY: {out['height']}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: Telop,{font},{tl['font_size']},{_ass_color(tl['color'])},&H000000FF,{_ass_color(tl['outline_color'])},"
        f"&H64000000,{bold},0,0,0,100,100,0,0,1,{tl['outline']},2,2,60,60,{tl['margin_v']},1",
        f"Style: Hook,{font},{hk['font_size']},{_ass_color(hk['color'])},&H000000FF,{_ass_color(tl['outline_color'])},"
        f"&H64000000,-1,0,0,0,100,100,0,0,1,{tl['outline'] + 2},3,{hook_align},60,60,{hk['margin_v']},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = []
    if plan["hook"]["enabled"] and plan["hook"]["text"]:
        events.append(f"Dialogue: 1,{_ass_t(0)},{_ass_t(plan['hook']['duration_sec'])},Hook,,0,0,0,,"
                      f"{{\\fad(0,150)}}{_fit(plan['hook']['text'], hk['font_size'], out['width'])}"
                      f"{_ass_escape(plan['hook']['text'])}")
    for t in plan["telops"]:
        s, e = map_time(t["start"], plan["keep"]), map_time(t["end"], plan["keep"])
        if s is None:
            continue
        e = e if e is not None else plan["output_duration"]
        if e - s < 0.2:
            continue
        events.append(f"Dialogue: 0,{_ass_t(s)},{_ass_t(e)},Telop,,0,0,0,,"
                      f"{_fit(t['text'], tl['font_size'], out['width'])}{_ass_escape(t['text'])}")
    return "\n".join(head + events) + "\n"


def cmd_render(args: argparse.Namespace) -> None:
    plan_path = Path(args.plan)
    plan = load_json(plan_path)
    kata = load_json(Path(args.kata or plan["kata"]))
    src = Path(plan["source"])
    info = probe(src)
    W, H, fps = plan["output"]["width"], plan["output"]["height"], plan["output"]["fps"]
    motion = kata.get("motion", {})
    font = pick_font(kata["telop"]["font"])
    if font != kata["telop"]["font"]:
        print(f"注意: フォント「{kata['telop']['font']}」が無いので「{font}」を使います。", file=sys.stderr)

    work = plan_path.parent / f".{plan_path.stem}_work"
    work.mkdir(parents=True, exist_ok=True)
    ass_path = work / "telop.ass"
    ass_path.write_text(build_ass(plan, kata, font), encoding="utf-8")

    keep = plan["keep"]
    fc = []
    for i, (s, e) in enumerate(keep):
        z = motion.get("zoom", 1.0) if motion.get("punch_in") and i % max(motion.get("every_n_cuts", 2), 1) == 1 else 1.0
        zw, zh = int(W * z) // 2 * 2, int(H * z) // 2 * 2
        fc.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS,"
                  f"scale={zw}:{zh}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps}[v{i}]")
        if info["has_audio"]:
            fc.append(f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d=0.02,afade=t=out:st={max(e - s - 0.02, 0):.3f}:d=0.02[a{i}]")
    n = len(keep)
    if info["has_audio"]:
        fc.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
    else:
        fc.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc]")
    ass_arg = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    fc.append(f"[vc]subtitles=filename='{ass_arg}'[vout]")

    inputs = ["-i", str(src)]
    voice = kata["sound"].get("voice_volume", 1.0)
    bgm = plan.get("bgm", {}).get("file")
    if bgm:
        inputs += ["-stream_loop", "-1", "-i", bgm]
        dur = plan["output_duration"]
        bgm_chain = (f"[1:a]atrim=0:{dur},asetpts=PTS-STARTPTS,volume={plan['bgm']['volume']},"
                     f"afade=t=out:st={max(dur - 1, 0):.2f}:d=1[bg]")
        if info["has_audio"]:
            fc += [bgm_chain, f"[ac]volume={voice}[vo]",
                   "[vo][bg]amix=inputs=2:duration=first:normalize=0[aout]"]
        else:
            fc.append(bgm_chain.replace("[bg]", "[aout]"))
        amap = "[aout]"
    elif info["has_audio"]:
        fc.append(f"[ac]volume={voice}[aout]")
        amap = "[aout]"
    else:
        amap = None

    script = work / "filter.txt"
    script.write_text(";\n".join(fc), encoding="utf-8")
    out = Path(args.output)
    if out.is_dir() or not out.suffix:
        out = out / f"{src.stem}_{plan.get('kata_name') or '編集'}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats", *inputs,
           "-filter_complex_script", str(script), "-map", "[vout]"]
    if amap:
        cmd += ["-map", amap, "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", args.preset, "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", str(fps), "-movflags", "+faststart", "-shortest", str(out)]
    r = run(cmd, capture=False)
    if r.returncode != 0:
        die(f"書き出しに失敗しました。フィルタ: {script}")
    o = probe(out)
    print(f"\n書き出しました: {out}({o['duration']:.2f}秒, {o.get('width')}x{o.get('height')})")


# ---------- main ----------

def main() -> None:
    p = argparse.ArgumentParser(description="リールの自動編集(FFmpeg + Whisper)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="FFmpeg・Whisper・日本語フォントの確認").set_defaults(func=cmd_check)

    c = sub.add_parser("clip", help="最初の N 秒を切り出す(動作確認)")
    c.add_argument("input", help="動画ファイル、または動画の入ったフォルダ")
    c.add_argument("-o", "--output", required=True, help="出力ファイルまたはフォルダ")
    c.add_argument("--seconds", type=float, default=5)
    c.set_defaults(func=cmd_clip)

    t = sub.add_parser("transcribe", help="文字起こし(JSON と SRT)")
    t.add_argument("input")
    t.add_argument("-o", "--output", help="出力 JSON(省略時は動画の隣)")
    t.add_argument("--model", default="small", help="Whisper のモデル(tiny/base/small/medium/large-v3 かフォルダ)")
    t.add_argument("--prompt", help="固有名詞などのヒント(例: 'キャバクラ、指名、同伴')")
    t.set_defaults(func=cmd_transcribe)

    a = sub.add_parser("analyze", help="参考例の分析(カット・無音・音量・コマ画像)")
    a.add_argument("input")
    a.add_argument("-o", "--output", help="出力フォルダ")
    a.add_argument("--scene", type=float, default=0.3, help="カット検出のしきい値(0〜1)")
    a.add_argument("--noise", type=float, default=-35, help="無音とみなす音量(dB)")
    a.add_argument("--every", type=float, default=2.0, help="コマ画像の間隔(秒)")
    a.add_argument("--max-frames", type=int, default=40)
    a.set_defaults(func=cmd_analyze)

    pl = sub.add_parser("plan", help="編集計画を作る")
    pl.add_argument("input")
    pl.add_argument("--kata", required=True, help="型の JSON(例: kata/kata-a.json)")
    pl.add_argument("--transcript", help="transcribe の JSON(無いと無音カットだけ・テロップなし)")
    pl.add_argument("--hook", help="冒頭に大きく出す文字(省略時は最初のテロップ)")
    pl.add_argument("--bgm", help="BGM の音声ファイル")
    pl.add_argument("--noise", type=float, default=-35)
    pl.add_argument("-o", "--output", help="計画 JSON(省略時は動画の隣)")
    pl.set_defaults(func=cmd_plan)

    r = sub.add_parser("render", help="計画どおりに書き出す")
    r.add_argument("plan")
    r.add_argument("-o", "--output", required=True, help="出力ファイルまたはフォルダ")
    r.add_argument("--kata", help="型の JSON(省略時は計画に書いた型)")
    r.add_argument("--preset", default="medium", help="x264 の preset(速くしたいときは veryfast)")
    r.set_defaults(func=cmd_render)

    args = p.parse_args()
    for tool in ("ffmpeg", "ffprobe"):
        if args.cmd != "check" and not shutil.which(tool):
            die(f"{tool} が入っていません。先に `python reel.py check` で確認してください。")
    args.func(args)


if __name__ == "__main__":
    main()
