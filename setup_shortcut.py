"""
AdBot Setup - icon + desktop shortcut
Run once: python setup_shortcut.py
"""

import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


# ── 1. 아이콘 생성 ─────────────────────────────────────────────

def make_icon() -> Path:
    ico_path = BASE_DIR / "adbot.ico"
    if ico_path.exists():
        print(f"[icon] already exists: {ico_path.name}")
        return ico_path

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[icon] Pillow not found - skipping icon creation")
        return ico_path  # 없어도 바로가기는 만듦

    sizes  = [256, 128, 64, 48, 32, 16]
    frames = []

    for sz in sizes:
        img  = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy, r = sz // 2, sz // 2, sz // 2 - 2

        # 그라데이션 배경 원
        for i in range(r, 0, -1):
            t = i / r
            draw.ellipse(
                [cx - i, cy - i, cx + i, cy + i],
                fill=(int(10 + 5 * t), int(20 + 30 * t), int(50 + 60 * t), 255),
            )

        # 골드 테두리
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(240, 192, 64, 220),
            width=max(1, sz // 48),
        )

        # 상승 차트 라인
        if sz >= 32:
            pts = [
                (int(cx + (x - 0.5) * sz * 0.8), int(cy + (y - 0.5) * sz * 0.8))
                for x, y in [(0.1, 0.75), (0.3, 0.6), (0.5, 0.65), (0.7, 0.45), (0.9, 0.25)]
            ]
            for i in range(len(pts) - 1):
                draw.line([pts[i], pts[i + 1]], fill=(100, 180, 255, 160), width=max(1, sz // 48))

        # "A" 텍스트
        font_sz = max(8, int(sz * 0.52))
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_sz)
        except Exception:
            font = ImageFont.load_default()

        shadow = max(1, sz // 80)
        draw.text((cx + shadow, cy - sz // 10 + shadow), "A", font=font,
                  fill=(0, 0, 0, 120), anchor="mm")
        draw.text((cx, cy - sz // 10), "A", font=font,
                  fill=(255, 255, 255, 245), anchor="mm")

        # 원형 마스크 적용
        mask = Image.new("L", (sz, sz), 0)
        ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        img.putalpha(mask)
        frames.append(img)

    frames[0].save(
        str(ico_path), format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"[icon] created: {ico_path.name}")
    return ico_path


# ── 2. 바탕화면 경로 탐색 ──────────────────────────────────────

def find_desktop() -> Path:
    candidates = [
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("USERPROFILE", "")) / "바탕 화면",  # 바탕 화면
        Path.home() / "Desktop",
        Path.home() / "바탕 화면",
    ]
    # SHGetKnownFolderPath 로 정확한 경로 시도
    try:
        import ctypes
        import uuid
        FOLDERID_Desktop = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(0, 0, 0, 0, buf)
        desktop_via_api = Path(buf.value)
        if desktop_via_api.exists():
            return desktop_via_api
    except Exception:
        pass

    for p in candidates:
        if p.exists():
            return p

    # 없으면 생성
    fallback = Path.home() / "Desktop"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


# ── 3. pythonw.exe 경로 확인 ──────────────────────────────────

def find_pythonw() -> Path:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if pythonw.exists():
        return pythonw
    # python.exe 폴더 내 탐색
    for p in Path(sys.executable).parent.glob("pythonw*.exe"):
        return p
    return Path(sys.executable)  # 없으면 python.exe 사용


# ── 4. 바탕화면 바로가기 생성 (VBScript, PowerShell 불필요) ───

def make_shortcut(ico_path: Path) -> bool:
    desktop     = find_desktop()
    pythonw     = find_pythonw()
    pyw_file    = BASE_DIR / "AdBot.pyw"
    lnk_path    = desktop / "AdBot.lnk"

    # 경로에 백슬래시 사용 (VBScript 표준)
    def w(p: Path) -> str:
        return str(p).replace("/", "\\")

    vbs_lines = [
        'Set sh = WScript.CreateObject("WScript.Shell")',
        f'Set lnk = sh.CreateShortcut("{w(lnk_path)}")',
        f'lnk.TargetPath = "{w(pythonw)}"',
        f'lnk.Arguments = Chr(34) & "{w(pyw_file)}" & Chr(34)',
        f'lnk.WorkingDirectory = "{w(BASE_DIR)}"',
        f'lnk.IconLocation = "{w(ico_path)}, 0"',
        'lnk.WindowStyle = 1',
        'lnk.Save',
    ]
    vbs_content = "\r\n".join(vbs_lines) + "\r\n"

    vbs_path = BASE_DIR / "_temp_setup.vbs"
    vbs_path.write_bytes(vbs_content.encode("cp949", errors="replace"))

    ret = subprocess.call(["cscript", "//nologo", str(vbs_path)])
    vbs_path.unlink(missing_ok=True)

    if lnk_path.exists():
        print(f"[shortcut] created: {lnk_path}")
        return True
    else:
        print(f"[shortcut] FAILED (cscript returned {ret})")
        return False


# ── 5. 실행 ────────────────────────────────────────────────────

def main():
    print("=" * 48)
    print("  AdBot Setup")
    print("=" * 48)

    ico  = make_icon()
    ok   = make_shortcut(ico)

    print()
    if ok:
        print("Setup complete!")
        print("-> Double-click [AdBot] on your Desktop to launch.")
    else:
        print("Shortcut creation failed.")
        print("-> You can still run AdBot by double-clicking AdBot.pyw")

    print()
    input("Press Enter to close...")


if __name__ == "__main__":
    main()
