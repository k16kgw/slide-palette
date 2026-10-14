"""
Python 版（color_palette.py）と Web 版（palette.js）の計算結果が一致するかを確認する。
実行: python tests/check_consistency.py   （Node.js が必要）
"""
import json
import pathlib
import random
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import color_palette as cp  # noqa: E402

FIXED = [
    "#0066CC", "0066CC", "#06C", "#123", "336699", "#777777", "#F2C200", "#FFFFFF", "#000000",
    "rgb(0,102,204)", "rgb(10%, 50%, 90%)", "hsl(210,100%,40%)", "hsl(0, 0.7, 0.45)",
    "hsv(210,100%,80%)", "hsb(45, 90%, 95%)", "210", "0", "-30", "360", "hue(210)",
    "hue(10, 80%, 45%)", "oklch(0.55 0.15 250)", "oklch(55% 0.2 30)",
    "cmyk(100%,50%,0%,20%)", "cmyk(0, 0.8, 0.9, 0.1)",
]


def random_specs(n=400, seed=1):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        k = rnd.randrange(4)
        if k == 0:
            out.append("#%02X%02X%02X" % tuple(rnd.randrange(256) for _ in range(3)))
        elif k == 1:
            out.append("hsl(%d, %d%%, %d%%)" % (rnd.randrange(360), rnd.randrange(101), rnd.randrange(101)))
        elif k == 2:
            out.append("hsv(%d, %d%%, %d%%)" % (rnd.randrange(360), rnd.randrange(101), rnd.randrange(101)))
        else:
            out.append("hue(%d)" % rnd.randrange(360))
    return out


def main():
    specs = FIXED + random_specs()
    targets = [7.0, 4.5]

    js = r"""
    const P = require(process.argv[1]);
    const specs = JSON.parse(process.argv[2]);
    const targets = JSON.parse(process.argv[3]);
    const out = [];
    for (const t of targets) for (const s of specs) {
      const p = P.palette(s, t);
      out.push([p.main, p.accent, p.light, p.dark]);
    }
    console.log(JSON.stringify(out));
    """
    res = subprocess.run(
        ["node", "-e", js, str(ROOT / "palette.js"), json.dumps(specs), json.dumps(targets)],
        capture_output=True, text=True, check=True)
    js_out = json.loads(res.stdout)

    i = 0
    fails = 0
    for t in targets:
        for s in specs:
            p = cp.palette(s, t)
            py = [list(p[k]) for k in ("main", "accent", "light", "dark")]
            if py != js_out[i]:
                fails += 1
                print(f"不一致: {s} (target={t})\n  Python: {py}\n  JS:     {js_out[i]}")
            i += 1

    print(f"{i} 件中 {i - fails} 件一致")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
