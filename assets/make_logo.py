"""프로필 로고 PNG 생성 (Pillow만 사용)"""
import math
from PIL import Image, ImageDraw, ImageFont

W, H = 400, 400
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 배경 원 (네이비 그라디언트 대신 단색)
cx, cy, r = 200, 200, 196
for i in range(r, 0, -1):
    ratio = i / r
    rc = int(10 + (13 - 10) * ratio)
    gc = int(15 + (42 - 15) * ratio)
    bc = int(46 + (110 - 46) * ratio)
    draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(rc, gc, bc, 255))

# 골드 외곽 링
for t in range(3):
    draw.ellipse([cx - r + t, cy - r + t, cx + r - t, cy + r - t],
                 outline=(240, 192, 64, 200), width=1)

# 격자 배경 (원 안에만)
grid_color = (79, 158, 255, 15)
for y in range(0, H, 50):
    draw.line([(0, y), (W, y)], fill=grid_color, width=1)
for x in range(0, W, 50):
    draw.line([(x, 0), (x, H)], fill=grid_color, width=1)

# 차트 라인 (하단)
chart_pts = [(20,320),(60,290),(100,300),(140,240),(180,260),
             (220,190),(260,210),(300,150),(340,170),(380,110)]
for i in range(len(chart_pts)-1):
    x1,y1 = chart_pts[i]
    x2,y2 = chart_pts[i+1]
    # 그라데이션 색
    ratio = i / len(chart_pts)
    b = int(79 + (0 - 79) * ratio)
    g = int(158 + (229 - 158) * ratio)
    draw.line([(x1,y1),(x2,y2)], fill=(b, g, 255, 160), width=3)

# AI 노드 (좌측 상단)
nodes = [(40,80),(90,60),(80,110),(130,85),(140,45)]
edges = [(0,1),(0,2),(1,3),(2,3),(1,4),(3,4)]
for a,b in edges:
    x1,y1 = nodes[a]; x2,y2 = nodes[b]
    draw.line([(x1,y1),(x2,y2)], fill=(79,158,255,70), width=2)
for nx,ny in nodes:
    draw.ellipse([nx-5,ny-5,nx+5,ny+5], fill=(79,158,255,120))

# 중앙 T 텍스트
try:
    font_big = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 160)
    font_small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
except:
    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

# T 그림자/글로우
for offset in [(3,3),(2,2),(-1,-1)]:
    draw.text((cx + offset[0], cy - 20 + offset[1]), "T",
              font=font_big, fill=(79,158,255,60), anchor="mm")
# T 메인
draw.text((cx, cy - 20), "T", font=font_big, fill=(255,255,255,245), anchor="mm")

# 골드 언더라인
draw.rounded_rectangle([cx-65, cy+58, cx+65, cy+64], radius=3, fill=(240,192,64,230))

# 하단 TREND 텍스트
draw.text((cx, cy+88), "T R E N D", font=font_small,
          fill=(160,196,255,200), anchor="mm")

# 원형 마스크 적용
mask = Image.new("L", (W, H), 0)
mask_draw = ImageDraw.Draw(mask)
mask_draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=255)
img.putalpha(mask)

out_path = "profile_logo.png"
img.save(out_path, "PNG")
print(f"저장 완료: {out_path}")
