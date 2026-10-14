"""
メインカラーから PowerPoint 用の配色（強調色・明るい背景色・暗い背景色）を計算する。

入力できる形式（大文字小文字・空白は問わない）:
  "#0066CC" / "0066CC" / "#06C"     カラーコード（16進。数字だけの3桁は "#" 必須）
  (0, 102, 204) / "rgb(0,102,204)"   RGB（0〜255）
  "hsl(210, 100%, 40%)"              HSL（PowerPoint の「ユーザー設定」の色相・彩度・明度と同系統）
  "hsv(210, 100%, 80%)"              HSV / HSB
  210 / "hue(210)"                   色相環の角度のみ（0=赤, 120=緑, 240=青）
  "hue(210, 70%, 45%)"               色相環の角度＋任意で彩度・明度（HSL として解釈）
  "oklch(0.55 0.15 250)"             OKLCH（L 0〜1, C, h 度）
  "cmyk(100%, 50%, 0%, 20%)"         CMYK（印刷物の色指定から）

使い方:
  python color_palette.py "#0066CC"
  python color_palette.py "hsl(210,100%,40%)" --target 4.5
"""
import colorsys
import math
import re
import sys

# ---------- 色空間変換 ----------

def srgb_to_lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lin_to_srgb(c):
    if c <= 0.0031308:
        return c * 12.92
    return 1.055 * math.copysign(abs(c) ** (1 / 2.4), c) - 0.055


def rgb_to_oklch(rgb):
    r, g, b = (srgb_to_lin(x) for x in rgb)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def _oklch_to_rgb_raw(L, C, h):
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return [lin_to_srgb(v) for v in (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076956789 * s)]


def oklch_to_rgb(L, C, h):
    """RGB で表せない場合は色相・明度を保ったまま彩度を落として収める。"""
    while True:
        rgb = _oklch_to_rgb_raw(L, C, h)
        if all(-1e-4 <= v <= 1 + 1e-4 for v in rgb) or C < 1e-4:
            return tuple(round(min(max(v, 0), 1) * 255) for v in rgb)
        C *= 0.97


# ---------- 入力の解釈 ----------

def _nums(s):
    """'210, 100%, 40%' → [(210.0, False), (100.0, True), (40.0, True)]"""
    return [(float(n), pct == "%") for n, pct in re.findall(r"(-?\d+(?:\.\d+)?)\s*(%?)", s)]


def _frac(val, is_pct):
    """% 表記なら /100、0〜1 ならそのまま、1 超なら % とみなす。"""
    v, p = val
    return v / 100 if (p or v > 1) else v


def _hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l, s)
    return tuple(round(x * 255) for x in (r, g, b))


def parse_color(spec):
    """様々な形式の色指定を (R, G, B) に変換する。"""
    # 数値や配列での指定
    if isinstance(spec, (int, float)):
        return _hsl(spec, 0.70, 0.45)
    if isinstance(spec, (tuple, list)):
        if len(spec) != 3:
            raise ValueError("RGB は 3 要素で指定してください")
        return tuple(int(round(v)) for v in spec)

    s = spec.strip().lower()

    # 色相の数値だけ（0〜360）。"210" などを 3 桁カラーコードと誤認しないよう先に判定
    if re.fullmatch(r"-?\d+(\.\d+)?", s) and abs(float(s)) <= 360:
        return _hsl(float(s), 0.70, 0.45)

    # 16進カラーコード（数字だけの 3 桁コードは "#" を付けて指定）
    m = re.fullmatch(r"#?([0-9a-f]{3}|[0-9a-f]{6})", s)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    m = re.fullmatch(r"([a-z]+)\s*\((.*)\)", s)
    if not m:
        raise ValueError(f"解釈できない色指定です: {spec}")
    kind, body = m.group(1), m.group(2)
    n = _nums(body)

    if kind in ("rgb", "rgba"):
        return tuple(round(v * 2.55) if p else round(v) for v, p in n[:3])
    if kind in ("hsl", "hsla"):
        return _hsl(n[0][0], _frac(n[1], 0), _frac(n[2], 0))
    if kind in ("hsv", "hsb"):
        r, g, b = colorsys.hsv_to_rgb((n[0][0] % 360) / 360, _frac(n[1], 0), _frac(n[2], 0))
        return tuple(round(x * 255) for x in (r, g, b))
    if kind == "hue":
        sat = _frac(n[1], 0) if len(n) > 1 else 0.70
        lig = _frac(n[2], 0) if len(n) > 2 else 0.45
        return _hsl(n[0][0], sat, lig)
    if kind == "oklch":
        L = _frac(n[0], 0)
        return oklch_to_rgb(L, n[1][0], n[2][0])
    if kind == "cmyk":
        c, mm, y, k = (_frac(x, 0) for x in n[:4])
        return tuple(round(255 * (1 - v) * (1 - k)) for v in (c, mm, y))

    raise ValueError(f"未対応の形式です: {kind}")


# ---------- 配色計算 ----------

def luminance(rgb):
    r, g, b = (srgb_to_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1, c2):
    y1, y2 = sorted([luminance(c1), luminance(c2)], reverse=True)
    return (y1 + 0.05) / (y2 + 0.05)


def to_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def palette(spec, target=7.0):
    main = parse_color(spec)
    L0, C0, h0 = rgb_to_oklch(main)

    # 明るい色（黒字の背景）: 色相維持・高明度・低彩度
    light = oklch_to_rgb(0.96, min(C0 * 0.25, 0.04), h0)

    # 暗い色（白字の背景）: 色相維持・彩度を残しつつ、白とのコントラストが target 以上になるまで暗く
    Cd = min(C0 * 0.8, 0.14)
    Ld = 0.40
    dark = oklch_to_rgb(Ld, Cd, h0)
    while contrast(dark, (255, 255, 255)) < target and Ld > 0.05:
        Ld -= 0.01
        dark = oklch_to_rgb(Ld, Cd, h0)

    # 強調色: 補色。無彩色に近い場合はオレンジ系に固定
    ha = (h0 + 180) % 360 if C0 >= 0.03 else 50
    La = 0.72 if L0 < 0.6 else 0.50
    accent = oklch_to_rgb(La, max(C0, 0.15), ha)

    return {
        "main": main,
        "accent": accent,
        "light": light,
        "dark": dark,
        "contrast_black_on_light": contrast(light, (0, 0, 0)),
        "contrast_white_on_dark": contrast(dark, (255, 255, 255)),
        "contrast_accent_vs_main": contrast(accent, main),
    }


def print_palette(spec, target=7.0):
    p = palette(spec, target)
    print(f"入力: {spec}")
    labels = {"main": "メイン", "accent": "強調色", "light": "明るい色（黒字背景）", "dark": "暗い色（白字背景）"}
    for k, name in labels.items():
        r, g, b = p[k]
        print(f"  {name:<14} RGB({r:3d}, {g:3d}, {b:3d})  {to_hex(p[k])}")
    print(f"  コントラスト  黒字/明るい色 {p['contrast_black_on_light']:.1f}:1"
          f"  白字/暗い色 {p['contrast_white_on_dark']:.1f}:1"
          f"  強調色/メイン {p['contrast_accent_vs_main']:.1f}:1")


if __name__ == "__main__":
    args = sys.argv[1:]
    target = 7.0
    if "--target" in args:
        i = args.index("--target")
        target = float(args[i + 1])
        del args[i:i + 2]
    if not args:
        print(__doc__)
        sys.exit(0)
    for a in args:
        print_palette(a, target)
        print()
