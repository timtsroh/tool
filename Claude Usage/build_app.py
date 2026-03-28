#!/usr/bin/env python3
"""Claude Usage.app 번들 생성 + 아이콘 (색상 반전 클로드 로고)"""

import os, sys, math, shutil, subprocess, tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
APP_PATH   = SCRIPT_DIR / "Claude Usage.app"

# 클로드 원래 색상: 코랄(#CC785C) 배경 + 흰색 마크
# ↓ 반전: 흰색 배경 + 코랄 마크
BG  = (255, 255, 255, 255)
FG  = (204, 120, 92,  255)
TRANSPARENT = (0, 0, 0, 0)


# ── 아이콘 생성 ────────────────────────────────────────────────
def make_icon(size: int) -> "Image":
    from PIL import Image, ImageDraw
    img  = Image.new("RGBA", (size, size), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    # 둥근 사각형 배경 (macOS 스타일)
    r = int(size * 0.22)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)

    cx, cy   = size // 2, size // 2
    outer_r  = int(size * 0.365)
    inner_r  = int(size * 0.215)
    ring_mid = (outer_r + inner_r) // 2

    # ① 채워진 원 → ② 안쪽 원 잘라내기 → ③ 오른쪽 섹터 잘라내기
    draw.ellipse([cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r], fill=FG)
    draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill=BG)

    gap = 54   # ± 도
    pts = [(cx, cy)]
    for a in range(-gap, gap + 1, 2):
        rad = math.radians(a)
        pts.append((cx + (outer_r + 4) * math.cos(rad),
                    cy + (outer_r + 4) * math.sin(rad)))
    draw.polygon(pts, fill=BG)

    # 터미널 스트로크 (C 끝의 짧은 가로 획)
    stroke_half_h = max(1, int(size * 0.038))
    stroke_reach  = int(size * 0.11)

    for sign in (-1, 1):          # 위쪽(-1) / 아래쪽(+1)
        a   = math.radians(sign * gap)
        tx  = cx + ring_mid * math.cos(a)
        ty  = cy + ring_mid * math.sin(a)

        # 획의 방향: C 안쪽(왼쪽)으로 뻗는 수평 막대
        x0  = int(tx - stroke_reach * 0.15)
        x1  = int(tx + stroke_reach * 0.85)
        y0  = int(ty - stroke_half_h)
        y1  = int(ty + stroke_half_h)
        draw.rectangle([x0, y0, x1, y1], fill=FG)

    return img


# ── iconset → icns ─────────────────────────────────────────────
ICON_SIZES = [16, 32, 128, 256, 512]

def build_icns(dest_icns: Path):
    iconset = Path(tempfile.mkdtemp(suffix=".iconset"))
    try:
        for s in ICON_SIZES:
            make_icon(s).save(str(iconset / f"icon_{s}x{s}.png"))
            make_icon(s * 2).save(str(iconset / f"icon_{s}x{s}@2x.png"))
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(dest_icns)],
            check=True
        )
        print(f"  ✓ 아이콘 생성: {dest_icns.name}")
    finally:
        shutil.rmtree(iconset, ignore_errors=True)


# ── .app 번들 ──────────────────────────────────────────────────
PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>            <string>Claude Usage</string>
    <key>CFBundleDisplayName</key>     <string>Claude Usage</string>
    <key>CFBundleIdentifier</key>      <string>local.claude-usage</string>
    <key>CFBundleVersion</key>         <string>1.0</string>
    <key>CFBundleExecutable</key>      <string>claude_usage</string>
    <key>CFBundleIconFile</key>        <string>AppIcon</string>
    <key>CFBundlePackageType</key>     <string>APPL</string>
    <key>LSMinimumSystemVersion</key>  <string>12.0</string>
    <key>NSHighResolutionCapable</key> <true/>
    <key>LSUIElement</key>             <false/>
</dict>
</plist>
"""

LAUNCHER = """\
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../../../" && pwd)"
cd "$DIR"
exec /usr/bin/env python3 "$DIR/claude_usage.py"
"""


def build_app():
    if APP_PATH.exists():
        shutil.rmtree(APP_PATH)
        print(f"  ↺ 기존 앱 삭제 후 재생성")

    macos_dir = APP_PATH / "Contents" / "MacOS"
    res_dir   = APP_PATH / "Contents" / "Resources"
    macos_dir.mkdir(parents=True)
    res_dir.mkdir(parents=True)

    # Info.plist
    (APP_PATH / "Contents" / "Info.plist").write_text(PLIST)
    print("  ✓ Info.plist")

    # 런처 스크립트
    launcher = macos_dir / "claude_usage"
    launcher.write_text(LAUNCHER)
    launcher.chmod(0o755)
    print("  ✓ 런처 실행 파일")

    # 아이콘
    build_icns(res_dir / "AppIcon.icns")

    print(f"\n✅  {APP_PATH.name}  생성 완료!")
    print(f"   경로: {APP_PATH}")


if __name__ == "__main__":
    print("Claude Usage.app 빌드 중...\n")
    build_app()
