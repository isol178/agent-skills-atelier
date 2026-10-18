#!/usr/bin/env python3
"""Agentic Vision 用の画像加工 CLI (Think -> Act -> Observe の Act 担当)。

Claude が Bash で実行し、出力された PNG を Read で見る (Observe) ために使う。

座標のルール (重要):
  - 座標はすべて「元画像に対する 0.0〜1.0 の割合」(左上が 0,0)。
    crop や tile の出力にグリッドを重ねても、ラベルは元画像の座標で表示される。
    そのため、見えたラベルの値をそのまま次の crop に渡せる。
  - 例外は adjust の出力 (回転などで元画像と対応しなくなる)。
    adjust の出力を --source に指定したときだけ、座標はその画像自身の割合になる。

サブコマンド:
  init      作業フォルダを作り、EXIF の向きを反映した元画像を保存して基本情報を表示
  grid      座標グリッドを重ねる (全体 or --box の範囲)
  crop      範囲を切り出して拡大 (常に元画像の画素から切るので画質が落ちない)
  tile      N x M のタイルに分割 (境界の取りこぼしを防ぐため重なりあり)
  adjust    回転 / 反転 / コントラスト / 明るさ / シャープ / 二値化 など
  annotate  枠・点と番号を描く (数え上げや位置の検算用)
  list      これまでに作った画像の一覧

例:
  python vision.py init photo.jpg
  python vision.py grid --rows 8 --cols 8
  python vision.py crop 0.70 0.85 1.0 1.0
  python vision.py tile --rows 3 --cols 3
  python vision.py adjust --box 0.1,0.2,0.5,0.6 --rotate 90 --autocontrast --sharpen
  python vision.py annotate --points "0.12,0.30;0.18,0.33" --view 0,0.2,0.5,0.6
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

Image.MAX_IMAGE_PIXELS = 300_000_000

# Claude の画像入力は長辺 ~1568px / 約 1.15MP を超えると縮小される。
# 出力をこの範囲に収めれば、作った画素がそのままモデルに届く。
MAX_SIDE = 1568
MAX_PIXELS = 1_150_000
MIN_SIDE = 900          # 小さな切り出しはこの長辺まで拡大 (最大 MAX_UPSCALE 倍)
MAX_UPSCALE = 4.0

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/meiryo.ttc",
]


# ------------------------------------------------------------------ 共通
def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def font(size: int):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def ws_dir(args) -> Path:
    return Path(args.ws or os.getenv("VISION_WS", "vision_ws")).resolve()


def load_manifest(ws: Path) -> dict:
    mf = ws / "manifest.json"
    if not mf.exists():
        die(f"{ws} が初期化されていません。先に `vision.py init <画像>` を実行してください。")
    return json.loads(mf.read_text())


def save_manifest(ws: Path, m: dict) -> None:
    (ws / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=1))


def parse_box(s: str | None) -> tuple[float, float, float, float] | None:
    if s is None:
        return None
    try:
        v = [float(x) for x in s.replace(" ", "").split(",")]
    except ValueError:
        die(f"box '{s}' は 'left,top,right,bottom' の形式で指定してください。")
    if len(v) != 4:
        die(f"box '{s}' は4つの数値が必要です。")
    return clamp_box(*v)


def clamp_box(l, t, r, b):
    c = lambda x: max(0.0, min(1.0, float(x)))  # noqa: E731
    l, r = sorted((c(l), c(r)))
    t, b = sorted((c(t), c(b)))
    return (l, t, r, b)


def px_box(img: Image.Image, box) -> tuple[int, int, int, int]:
    l, t, r, b = box
    return (round(l * img.width), round(t * img.height), round(r * img.width), round(b * img.height))


def fit(img: Image.Image, upscale: bool = True) -> tuple[Image.Image, float]:
    """モデルに縮小されない大きさに収める。小さい切り出しは拡大する。倍率も返す。"""
    w, h = img.size
    s = min(MAX_SIDE / max(w, h), (MAX_PIXELS / (w * h)) ** 0.5)
    if s >= 1.0:
        s = min(max(1.0, MIN_SIDE / max(w, h)), MAX_UPSCALE, s) if upscale else 1.0
    if abs(s - 1.0) < 1e-3:
        return img, 1.0
    out = img.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    return out, s


def next_name(m: dict, prefix: str) -> str:
    m.setdefault("counters", {})
    m["counters"][prefix] = m["counters"].get(prefix, 0) + 1
    return f"{prefix}_{m['counters'][prefix]}.png"


def open_original(ws: Path, m: dict) -> Image.Image:
    return Image.open(ws / m["original"]["file"]).convert("RGB")


def resolve_source(ws: Path, m: dict, source: str):
    """(画像, 元画像に対応しているか) を返す。対応している場合は常に元画像を返す。"""
    if source in ("original", m["original"]["file"]):
        return open_original(ws, m), True
    item = m["items"].get(source)
    if item is None:
        die(f"'{source}' が見つかりません。`vision.py list` で名前を確認してください。")
    if item.get("mappable"):
        # 切り出し・タイル・グリッドは元画像と対応しているので、元画像から処理し直す
        return open_original(ws, m), True
    return Image.open(ws / source).convert("RGB"), False


def emit(ws: Path, m: dict, name: str, img: Image.Image, meta: dict, scale: float) -> None:
    img.save(ws / name)
    meta = {**meta, "size": list(img.size)}
    m["items"][name] = meta
    save_manifest(ws, m)
    note = ""
    if scale < 0.9:
        note = " (縮小あり: 細部が必要ならもっと狭く切り出す)"
    elif scale > 1.001:
        note = " (拡大: 情報量は元画像の画素数が上限)"
    print(f"saved: {ws / name}")
    print(f"  size={img.size[0]}x{img.size[1]}  元画像1px → {scale:.2f}px{note}")
    if "box" in meta:
        print(f"  box(元画像座標)={fmt_box(meta['box'])}")


def px_to_global(m: dict, name: str, vals: list[float]) -> list[float]:
    """出力画像 name 上の画素座標 (x, y, x, y, ...) を元画像の割合座標に変換する。"""
    it = m["items"].get(name)
    if it is None or not it.get("mappable") or not it.get("box"):
        die(f"--px-of には元画像と対応する出力 (crop/tile/grid/overview) を指定してください: {name}")
    l, t, r, b = it["box"]
    w, h = it["size"]
    return [(l + v / w * (r - l)) if i % 2 == 0 else (t + v / h * (b - t)) for i, v in enumerate(vals)]


def fmt_box(b) -> str:
    return ",".join(f"{v:.3f}" for v in b)


def outlined(d: ImageDraw.ImageDraw, xy, text, fnt, fill=(255, 255, 0)):
    d.text(xy, text, fill=fill, font=fnt, stroke_width=max(2, fnt.size // 8), stroke_fill=(0, 0, 0))


def nice_step(span: float, n: int) -> float:
    """span を約 n 分割する「きりのいい」刻み幅。"""
    raw = span / max(1, n)
    for s in (0.001, 0.002, 0.0025, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.125, 0.2, 0.25, 0.5, 1.0):
        if s >= raw * 0.999:
            return s
    return 1.0


def label_fmt(step: float) -> str:
    return "{:.3f}" if step < 0.01 else "{:.2f}"


# ------------------------------------------------------------------ コマンド
def cmd_init(args):
    ws = ws_dir(args)
    ws.mkdir(parents=True, exist_ok=True)
    src = Image.open(args.image)
    exif_orient = None
    try:
        exif_orient = src.getexif().get(0x0112)
    except Exception:  # noqa: BLE001
        pass
    img = ImageOps.exif_transpose(src).convert("RGB")
    img.save(ws / "original.png")
    m = {"original": {"file": "original.png", "source": str(Path(args.image).resolve()), "size": list(img.size)},
         "items": {}, "counters": {}}
    overview, s = fit(img, upscale=False)
    overview.save(ws / "overview.png")
    m["items"]["overview.png"] = {"kind": "overview", "box": [0, 0, 1, 1], "mappable": True, "size": list(overview.size)}
    save_manifest(ws, m)
    w, h = img.size
    print(f"workspace: {ws}")
    print(f"original : {w}x{h} ({w * h / 1e6:.1f}MP)  EXIF orientation={exif_orient or 'なし'}"
          f"{' → 補正済み' if exif_orient and exif_orient != 1 else ''}")
    print(f"overview : {ws / 'overview.png'}  (元画像1px → {s:.2f}px)")
    if 0.75 <= s < 0.999:
        print("  全体表示はほぼ等倍。小さい文字や細い線は crop で拡大すると読みやすくなる。")
    elif s < 0.75:
        print(f"  全体表示は約 1/{1 / s:.1f} に縮小されている。"
              f"元画像の {1 / s:.1f}px 未満の細部 (小さい文字・細い線) は全体表示では見えていない前提で扱う。")
        k = max(1, round(1 / s))
        print(f"  目安: 等倍で見るには一辺が全体の 1/{k} 程度の範囲を crop する。")
    else:
        print("  全体表示でも画素は落ちていない。細部は crop で拡大すると読みやすくなる。")


def cmd_grid(args):
    ws = ws_dir(args)
    m = load_manifest(ws)
    img, mappable = resolve_source(ws, m, args.source)
    box = parse_box(args.box) or (tuple(m["items"][args.source]["box"])
                                 if mappable and args.source in m["items"] else (0, 0, 1, 1))
    view = img.crop(px_box(img, box))
    view, s = fit(view)
    w, h = view.size
    l, t, r, b = box
    ov = Image.new("RGBA", view.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    fs = max(14, min(28, w // 45))
    fnt = font(fs)
    lw = max(1, w // 700)

    def lines(lo, hi, n):
        st = nice_step(hi - lo, n)
        k0 = int(lo / st + 0.999)
        vals = []
        k = k0
        while k * st <= hi + 1e-9:
            vals.append(round(k * st, 6))
            k += 1
        return vals, st

    xs, sx = lines(l, r, args.cols)
    ys, sy = lines(t, b, args.rows)
    fx, fy = label_fmt(sx), label_fmt(sy)
    for v in xs:
        x = min(w - 1, round((v - l) / (r - l) * w))
        d.line([(x, 0), (x, h)], fill=(255, 0, 0, 160), width=lw)
        lab = fx.format(v)
        tx = min(max(2, x + 3), w - d.textlength(lab, font=fnt) - 3)
        outlined(d, (tx, 2), lab, fnt)
    for v in ys:
        y = min(h - 1, round((v - t) / (b - t) * h))
        d.line([(0, y), (w, y)], fill=(255, 0, 0, 160), width=lw)
        ty = min(max(2, y + 2), h - fs - 6)
        outlined(d, (2, ty), fy.format(v), fnt, fill=(0, 255, 255))
    out = Image.alpha_composite(view.convert("RGBA"), ov).convert("RGB")
    name = next_name(m, "grid")
    meta = {"kind": "grid", "box": list(box) if mappable else None, "mappable": mappable, "parent": args.source}
    if not mappable:
        meta.pop("box")
    emit(ws, m, name, out, meta, s)
    if mappable:
        print("  ラベルは元画像座標 (黄=x, 水色=y)。そのまま crop に渡せる。")
    else:
        print(f"  ラベルは {args.source} 自身の座標。crop するときは --source {args.source} を付ける。")


def cmd_crop(args):
    ws = ws_dir(args)
    m = load_manifest(ws)
    img, mappable = resolve_source(ws, m, args.source)
    vals = [args.left, args.top, args.right, args.bottom]
    if args.px_of:
        vals = px_to_global(m, args.px_of, vals)
    box = clamp_box(*vals)
    pb = px_box(img, box)
    if pb[2] - pb[0] < 4 or pb[3] - pb[1] < 4:
        die("切り出し範囲が小さすぎます (4px 未満)。範囲を広げてください。")
    if args.pad:
        pw, ph = (pb[2] - pb[0]) * args.pad, (pb[3] - pb[1]) * args.pad
        box = clamp_box(box[0] - pw / img.width, box[1] - ph / img.height,
                        box[2] + pw / img.width, box[3] + ph / img.height)
        pb = px_box(img, box)
    out, s = fit(img.crop(pb))
    name = next_name(m, "crop")
    meta = {"kind": "crop", "mappable": mappable, "parent": args.source}
    if mappable:
        meta["box"] = list(box)
    else:
        meta["local_box"] = list(box)
    emit(ws, m, name, out, meta, s)
    print(f"  元画像の画素範囲: {pb[2] - pb[0]}x{pb[3] - pb[1]}px")


def cmd_tile(args):
    ws = ws_dir(args)
    m = load_manifest(ws)
    img = open_original(ws, m)
    l, t, r, b = parse_box(args.box) or (0, 0, 1, 1)
    rows, cols = max(1, min(args.rows, 8)), max(1, min(args.cols, 8))
    ov = max(0.0, min(args.overlap, 0.5))
    cw, ch = (r - l) / cols, (b - t) / rows
    print(f"tiles ({rows}x{cols}, overlap={ov:.0%})")
    if ov > 0 and not args.no_frame:
        print("  各タイルの水色の枠が担当範囲。数えるときは「中心が枠の内側にある対象」だけ数えれば、"
              "重なり部分の二重カウントが起きない。")
    for i in range(rows):
        for j in range(cols):
            core = (l + j * cw, t + i * ch, l + (j + 1) * cw, t + (i + 1) * ch)
            box = clamp_box(l + (j - ov) * cw, t + (i - ov) * ch, l + (j + 1 + ov) * cw, t + (i + 1 + ov) * ch)
            box = (max(box[0], l), max(box[1], t), min(box[2], r), min(box[3], b))
            out, s = fit(img.crop(px_box(img, box)))
            if ov > 0 and not args.no_frame:
                d = ImageDraw.Draw(out)
                bw, bh = box[2] - box[0], box[3] - box[1]
                fx = lambda v: (v - box[0]) / bw * out.width  # noqa: E731
                fy = lambda v: (v - box[1]) / bh * out.height  # noqa: E731
                d.rectangle((fx(core[0]), fy(core[1]), fx(core[2]) - 1, fy(core[3]) - 1),
                            outline=(0, 220, 255), width=max(2, out.width // 500))
            name = next_name(m, "tile")
            out.save(ws / name)
            m["items"][name] = {"kind": "tile", "row": i, "col": j, "box": list(box), "mappable": True,
                                "size": list(out.size)}
            print(f"  {ws / name}  [r{i} c{j}] box={fmt_box(box)}  ×{s:.2f}")
    save_manifest(ws, m)


def cmd_adjust(args):
    ws = ws_dir(args)
    m = load_manifest(ws)
    img, mappable = resolve_source(ws, m, args.source)
    box = parse_box(args.box)
    if box is None and mappable and args.source in m["items"]:
        box = tuple(m["items"][args.source]["box"])
    if box:
        img = img.crop(px_box(img, box))
    # 拡大は加工前に行う (二値化・シャープ化は拡大後の方が効く)
    img, s = fit(img)
    ops = []
    if args.gray:
        img = ImageOps.grayscale(img).convert("RGB"); ops.append("gray")
    if args.autocontrast:
        img = ImageOps.autocontrast(img, cutoff=1); ops.append("autocontrast")
    if args.equalize:
        img = ImageOps.equalize(img); ops.append("equalize")
    if args.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(max(0.1, min(args.contrast, 5.0))); ops.append(f"contrast={args.contrast}")
    if args.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(max(0.1, min(args.brightness, 5.0))); ops.append(f"brightness={args.brightness}")
    if args.sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=160, threshold=2)); ops.append("sharpen")
    if args.invert:
        img = ImageOps.invert(img); ops.append("invert")
    if args.threshold is not None:
        g = ImageOps.grayscale(img)
        th = args.threshold
        img = g.point(lambda p: 255 if p > th else 0).convert("RGB"); ops.append(f"threshold={th}")
    if args.rotate % 360:
        img = img.rotate(-args.rotate, expand=True, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
        ops.append(f"rotate={args.rotate}")
    if args.flip == "horizontal":
        img = ImageOps.mirror(img); ops.append("flip=h")
    elif args.flip == "vertical":
        img = ImageOps.flip(img); ops.append("flip=v")
    if not ops:
        die("加工内容が指定されていません (--rotate / --autocontrast / --sharpen など)。")
    img, s2 = fit(img, upscale=False)
    name = next_name(m, "adjust")
    meta = {"kind": "adjust", "mappable": False, "parent": args.source, "ops": ops}
    if box:
        meta["from_box"] = list(box)
    emit(ws, m, name, img, meta, s * s2)
    print(f"  ops: {', '.join(ops)}")
    print(f"  この画像は元画像座標と対応しない。ここから切り出すときは --source {name} を付ける (座標はこの画像の割合)。")


def parse_list(s: str | None, n: int, what: str):
    if not s:
        return []
    out = []
    for chunk in s.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            v = [float(x) for x in chunk.split(",")]
        except ValueError:
            die(f"{what} '{chunk}' の数値が読めません。")
        if len(v) != n:
            die(f"{what} '{chunk}' は {n} 個の数値が必要です。")
        out.append(v)
    return out


def cmd_annotate(args):
    ws = ws_dir(args)
    m = load_manifest(ws)
    img, mappable = resolve_source(ws, m, args.source)
    boxes = parse_list(args.boxes, 4, "box")
    points = parse_list(args.points, 2, "point")
    if args.px_of:
        boxes = [px_to_global(m, args.px_of, bx) for bx in boxes]
        points = [px_to_global(m, args.px_of, pt) for pt in points]
        if not args.view:
            args.view = fmt_box(m["items"][args.px_of]["box"])
    if not boxes and not points:
        die("--boxes か --points を指定してください。")
    labels = [x.strip() for x in args.labels.split(";")] if args.labels else []
    view = parse_box(args.view) or (0, 0, 1, 1)
    vl, vt, vr, vb = view
    base = img.crop(px_box(img, view))
    base, s = fit(base)
    w, h = base.size
    d = ImageDraw.Draw(base, "RGBA")
    fs = max(14, min(26, w // 50))
    fnt = font(fs)
    lw = max(2, w // 450)

    def to_px(x, y):
        return ((x - vl) / (vr - vl) * w, (y - vt) / (vb - vt) * h)

    k = 0
    for bx in boxes:
        lab = labels[k] if k < len(labels) else str(k + 1)
        k += 1
        l, t, r, b = clamp_box(*bx)
        x0, y0 = to_px(l, t)
        x1, y1 = to_px(r, b)
        d.rectangle((x0, y0, x1, y1), outline=(255, 0, 0, 255), width=lw)
        tw = d.textlength(lab, font=fnt)
        d.rectangle((x0, y0 - fs - 6 if y0 > fs + 6 else y0, x0 + tw + 8, (y0 if y0 > fs + 6 else y0 + fs + 6)),
                    fill=(255, 0, 0, 220))
        d.text((x0 + 4, (y0 - fs - 5) if y0 > fs + 6 else y0 + 1), lab, fill=(255, 255, 255), font=fnt)
    rad = max(5, w // 160)
    for p in points:
        lab = labels[k] if k < len(labels) else str(k + 1)
        k += 1
        x, y = to_px(*p)
        d.ellipse((x - rad, y - rad, x + rad, y + rad), outline=(255, 0, 255, 255), width=lw)
        outlined(d, (x + rad + 2, y - fs // 2), lab, fnt, fill=(255, 0, 255))
    name = next_name(m, "annot")
    meta = {"kind": "annotate", "mappable": False, "parent": args.source, "view": list(view),
            "n_boxes": len(boxes), "n_points": len(points)}
    emit(ws, m, name, base, meta, s)
    print(f"  描画: 枠 {len(boxes)} 個 + 点 {len(points)} 個 = 計 {k} 個。"
          "印のない対象・二重の印・ずれた印がないか確認すること。")


def cmd_list(args):
    ws = ws_dir(args)
    m = load_manifest(ws)
    o = m["original"]
    print(f"original.png  {o['size'][0]}x{o['size'][1]}  ← {o['source']}")
    for name, it in m["items"].items():
        extra = f"box={fmt_box(it['box'])}" if it.get("box") else \
            ("ops=" + ",".join(it.get("ops", [])) if it.get("ops") else "")
        print(f"{name:14s} {it['kind']:9s} {'map' if it.get('mappable') else '---'}  {extra}")


# ------------------------------------------------------------------ CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ws", help="作業フォルダ (既定: ./vision_ws または環境変数 VISION_WS)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="作業フォルダを初期化")
    p.add_argument("image")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("grid", help="座標グリッドを重ねる")
    p.add_argument("--source", default="original")
    p.add_argument("--box", help="この範囲だけ表示 (元画像座標 l,t,r,b)")
    p.add_argument("--rows", type=int, default=6)
    p.add_argument("--cols", type=int, default=6)
    p.set_defaults(func=cmd_grid)

    p = sub.add_parser("crop", help="切り出して拡大")
    for k in ("left", "top", "right", "bottom"):
        p.add_argument(k, type=float)
    p.add_argument("--source", default="original", help="adjust の出力から切るときだけ指定")
    p.add_argument("--pad", type=float, default=0.0, help="範囲を各辺この割合だけ広げる (例 0.1)")
    p.add_argument("--px-of", help="座標を、この出力画像 (crop_1.png など) 上の画素位置として解釈する")
    p.set_defaults(func=cmd_crop)

    p = sub.add_parser("tile", help="タイル分割")
    p.add_argument("--rows", type=int, default=2)
    p.add_argument("--cols", type=int, default=2)
    p.add_argument("--overlap", type=float, default=0.1)
    p.add_argument("--box", help="この範囲だけをタイル分割 (元画像座標)")
    p.add_argument("--no-frame", action="store_true", help="担当範囲の水色枠を描かない (文字読み取り時など)")
    p.set_defaults(func=cmd_tile)

    p = sub.add_parser("adjust", help="向き・見やすさの調整")
    p.add_argument("--source", default="original")
    p.add_argument("--box", help="この範囲だけ切り出して加工 (元画像座標)")
    p.add_argument("--rotate", type=float, default=0.0, help="時計回りの角度 (90, 180, -12 など)")
    p.add_argument("--flip", choices=["none", "horizontal", "vertical"], default="none")
    p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--brightness", type=float, default=1.0)
    p.add_argument("--autocontrast", action="store_true")
    p.add_argument("--equalize", action="store_true", help="ヒストグラム平坦化 (暗部の掘り起こし)")
    p.add_argument("--sharpen", action="store_true")
    p.add_argument("--gray", action="store_true")
    p.add_argument("--invert", action="store_true")
    p.add_argument("--threshold", type=int, help="0-255 で二値化 (かすれた文字に)")
    p.set_defaults(func=cmd_adjust)

    p = sub.add_parser("annotate", help="枠・点と番号を描く")
    p.add_argument("--source", default="original")
    p.add_argument("--boxes", help='"l,t,r,b;l,t,r,b" (元画像座標)')
    p.add_argument("--points", help='"x,y;x,y" (元画像座標)')
    p.add_argument("--labels", help='"A;B;C" (省略時は 1,2,3...)')
    p.add_argument("--view", help="この範囲だけ表示 (元画像座標 l,t,r,b)")
    p.add_argument("--px-of", help="座標を、この出力画像 (tile_1.png など) 上の画素位置として解釈する。"
                   "--view 省略時はその画像と同じ範囲を表示")
    p.set_defaults(func=cmd_annotate)

    p = sub.add_parser("list", help="作った画像の一覧")
    p.set_defaults(func=cmd_list)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
