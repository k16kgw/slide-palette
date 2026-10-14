/*
 * スライド配色計算（color_palette.py の JavaScript 版）
 * ブラウザでは window.SlidePalette、Node では module.exports として使える。
 * 計算結果は Python 版と一致するよう、丸め方（偶数丸め）や colorsys の挙動も合わせている。
 */
(function (root) {
  "use strict";

  // Python の round()（偶数丸め）と同じ挙動
  function pyRound(x) {
    const f = Math.floor(x);
    const d = x - f;
    if (d > 0.5) return f + 1;
    if (d < 0.5) return f;
    return f % 2 === 0 ? f : f + 1;
  }

  // Python の % と同じ（結果が除数と同符号）
  function pyMod(a, n) {
    return ((a % n) + n) % n;
  }

  // ---------- 色空間変換 ----------

  function srgbToLin(c) {
    c /= 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  }

  function linToSrgb(c) {
    if (c <= 0.0031308) return c * 12.92;
    return 1.055 * Math.sign(c) * Math.pow(Math.abs(c), 1 / 2.4) - 0.055;
  }

  function rgbToOklch(rgb) {
    const [r, g, b] = rgb.map(srgbToLin);
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    const L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s;
    const a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s;
    const bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s;
    return [L, Math.hypot(a, bb), pyMod((Math.atan2(bb, a) * 180) / Math.PI, 360)];
  }

  function oklchToRgbRaw(L, C, h) {
    const hr = (h * Math.PI) / 180;
    const a = C * Math.cos(hr), b = C * Math.sin(hr);
    const l = Math.pow(L + 0.3963377774 * a + 0.2158037573 * b, 3);
    const m = Math.pow(L - 0.1055613458 * a - 0.0638541728 * b, 3);
    const s = Math.pow(L - 0.0894841775 * a - 1.2914855480 * b, 3);
    return [
      4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.7076956789 * s,
    ].map(linToSrgb);
  }

  // RGB で表せない場合は色相・明度を保ったまま彩度を落として収める
  function oklchToRgb(L, C, h) {
    for (;;) {
      const rgb = oklchToRgbRaw(L, C, h);
      if (rgb.every((v) => v >= -1e-4 && v <= 1 + 1e-4) || C < 1e-4) {
        return rgb.map((v) => pyRound(Math.min(Math.max(v, 0), 1) * 255));
      }
      C *= 0.97;
    }
  }

  // Python colorsys.hls_to_rgb / hsv_to_rgb の移植
  function _v(m1, m2, hue) {
    hue = pyMod(hue, 1.0);
    if (hue < 1 / 6) return m1 + (m2 - m1) * hue * 6.0;
    if (hue < 0.5) return m2;
    if (hue < 2 / 3) return m1 + (m2 - m1) * (2 / 3 - hue) * 6.0;
    return m1;
  }

  function hlsToRgb(h, l, s) {
    if (s === 0) return [l, l, l];
    const m2 = l <= 0.5 ? l * (1.0 + s) : l + s - l * s;
    const m1 = 2.0 * l - m2;
    return [_v(m1, m2, h + 1 / 3), _v(m1, m2, h), _v(m1, m2, h - 1 / 3)];
  }

  function hsvToRgb(h, s, v) {
    if (s === 0) return [v, v, v];
    let i = Math.trunc(h * 6.0);
    const f = h * 6.0 - i;
    const p = v * (1.0 - s), q = v * (1.0 - s * f), t = v * (1.0 - s * (1.0 - f));
    i = pyMod(i, 6);
    return [[v, t, p], [q, v, p], [p, v, t], [p, q, v], [t, p, v], [v, p, q]][i];
  }

  // ---------- 入力の解釈 ----------

  function nums(s) {
    const out = [];
    const re = /(-?\d+(?:\.\d+)?)\s*(%?)/g;
    let m;
    while ((m = re.exec(s)) !== null) out.push([parseFloat(m[1]), m[2] === "%"]);
    return out;
  }

  // % 表記なら /100、0〜1 ならそのまま、1 超なら % とみなす
  function frac(val) {
    const [v, p] = val;
    return p || v > 1 ? v / 100 : v;
  }

  function hsl(h, s, l) {
    return hlsToRgb(pyMod(h, 360) / 360, l, s).map((x) => pyRound(x * 255));
  }

  function parseColor(spec) {
    if (typeof spec === "number") return hsl(spec, 0.7, 0.45);
    if (Array.isArray(spec)) {
      if (spec.length !== 3) throw new Error("RGB は 3 要素で指定してください");
      return spec.map((v) => pyRound(v));
    }

    const s = String(spec).trim().toLowerCase();

    // 色相の数値だけ（0〜360）。"210" などを 3 桁カラーコードと誤認しないよう先に判定
    if (/^-?\d+(\.\d+)?$/.test(s) && Math.abs(parseFloat(s)) <= 360) {
      return hsl(parseFloat(s), 0.7, 0.45);
    }

    // 16進カラーコード（数字だけの 3 桁コードは "#" を付けて指定）
    let m = s.match(/^#?([0-9a-f]{3}|[0-9a-f]{6})$/);
    if (m) {
      let h = m[1];
      if (h.length === 3) h = h.split("").map((c) => c + c).join("");
      return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
    }

    m = s.match(/^([a-z]+)\s*\((.*)\)$/s);
    if (!m) throw new Error("解釈できない色指定です: " + spec);
    const kind = m[1];
    const n = nums(m[2]);
    const need = (k) => {
      if (n.length < k) throw new Error(kind + "() には数値が " + k + " つ必要です");
    };

    if (kind === "rgb" || kind === "rgba") {
      need(3);
      return n.slice(0, 3).map(([v, p]) => (p ? pyRound(v * 2.55) : pyRound(v)));
    }
    if (kind === "hsl" || kind === "hsla") {
      need(3);
      return hsl(n[0][0], frac(n[1]), frac(n[2]));
    }
    if (kind === "hsv" || kind === "hsb") {
      need(3);
      return hsvToRgb(pyMod(n[0][0], 360) / 360, frac(n[1]), frac(n[2])).map((x) => pyRound(x * 255));
    }
    if (kind === "hue") {
      need(1);
      const sat = n.length > 1 ? frac(n[1]) : 0.7;
      const lig = n.length > 2 ? frac(n[2]) : 0.45;
      return hsl(n[0][0], sat, lig);
    }
    if (kind === "oklch") {
      need(3);
      return oklchToRgb(frac(n[0]), n[1][0], n[2][0]);
    }
    if (kind === "cmyk") {
      need(4);
      const [c, mm, y, k] = n.slice(0, 4).map(frac);
      return [c, mm, y].map((v) => pyRound(255 * (1 - v) * (1 - k)));
    }
    throw new Error("未対応の形式です: " + kind);
  }

  // ---------- 配色計算 ----------

  function luminance(rgb) {
    const [r, g, b] = rgb.map(srgbToLin);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function contrast(c1, c2) {
    const [y1, y2] = [luminance(c1), luminance(c2)].sort((a, b) => b - a);
    return (y1 + 0.05) / (y2 + 0.05);
  }

  function toHex(rgb) {
    return "#" + rgb.map((v) => v.toString(16).padStart(2, "0").toUpperCase()).join("");
  }

  const WHITE = [255, 255, 255], BLACK = [0, 0, 0];

  function palette(spec, target) {
    if (target === undefined) target = 7.0;
    const main = parseColor(spec);
    const [L0, C0, h0] = rgbToOklch(main);

    // 明るい色（黒字の背景）: 色相維持・高明度・低彩度
    const light = oklchToRgb(0.96, Math.min(C0 * 0.25, 0.04), h0);

    // 暗い色（白字の背景）: 彩度を残しつつ、白とのコントラストが target 以上になるまで暗く
    const Cd = Math.min(C0 * 0.8, 0.14);
    let Ld = 0.4;
    let dark = oklchToRgb(Ld, Cd, h0);
    while (contrast(dark, WHITE) < target && Ld > 0.05) {
      Ld -= 0.01;
      dark = oklchToRgb(Ld, Cd, h0);
    }

    // 強調色: 補色。無彩色に近い場合はオレンジ系に固定
    const ha = C0 >= 0.03 ? pyMod(h0 + 180, 360) : 50;
    const La = L0 < 0.6 ? 0.72 : 0.5;
    const accent = oklchToRgb(La, Math.max(C0, 0.15), ha);

    return {
      main, accent, light, dark,
      contrast_black_on_light: contrast(light, BLACK),
      contrast_white_on_dark: contrast(dark, WHITE),
      contrast_accent_vs_main: contrast(accent, main),
    };
  }

  const api = { parseColor, palette, contrast, luminance, toHex, rgbToOklch, oklchToRgb };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SlidePalette = api;
})(typeof window !== "undefined" ? window : this);
