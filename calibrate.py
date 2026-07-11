# -*- coding: utf-8 -*-
"""
calibrate.py
------------
Cong cu ho tro HIEU CHINH (calibration) truoc khi chay ex_arena_bot.py.

Vi video mau chi co do phan giai 962x572, con man hinh that cua ban co
the khac (fullscreen / windowed khac ty le), nen KHONG the dung thang
toa do rut ra tu video. Ban can chay tool nay de:

  1) Lay toa do CHUOT (mouse position) cho tung diem can click
     -> chay: python calibrate.py pos
     -> di chuyen chuot toi vi tri muon lay (vd: nut NEXT, nut I'm ready...)
        roi nhan phim ESC de in ra toa do hien tai, lap lai cho tung diem.

  2) Chup mot vung man hinh nho lam TEMPLATE (anh mau) de bot tu nhan
     dien UI bang OpenCV template matching (chinh xac hon la click
     "mu" theo toa do co dinh, vi UI co the doi vi tri 1-2px hoac popup
     xuat hien tre/som).
     -> chay: python calibrate.py crop
     -> nhap toa do vung (left, top, right, bottom) va ten file, tool
        se chup man hinh hien tai va crop luu vao thu muc templates/.

Yeu cau: pip install pyautogui pillow opencv-python numpy pywin32
(KHONG can package "keyboard" - dung win32api.GetAsyncKeyState de doc
phim, giong cach toram_collab_bot.py ban da lam truoc do. Chay voi
quyen Administrator tren Windows de SendInput/PostMessage trong
ex_arena_bot.py hoat dong dung voi game DirectInput.)
"""

import sys
import os
import time

import win32api

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)

VK_ESCAPE = 0x1B


def _wait_for_esc_press():
    """Poll GetAsyncKeyState cho ESC, khong can package 'keyboard'."""
    was_down = False
    while True:
        down = bool(win32api.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
        if down and not was_down:
            was_down = down
            return
        was_down = down
        time.sleep(0.03)


def mode_pos():
    import pyautogui

    print("=== CHE DO LAY TOA DO CHUOT ===")
    print("Di chuyen chuot den vi tri can lay, nhan ESC de in toa do.")
    print("Nhan Ctrl+C de thoat.\n")
    try:
        while True:
            _wait_for_esc_press()
            x, y = pyautogui.position()
            print(f"Toa do hien tai: x={x}, y={y}")
            time.sleep(0.3)  # tranh in lap do giu phim
    except KeyboardInterrupt:
        print("Thoat.")


def mode_crop():
    import pyautogui

    print("=== CHE DO CHUP TEMPLATE ===")
    print("Dua chuot ra ngoai vung can chup truoc, script se cho ban")
    print("5 giay de chuyen sang cua so game va cho hien UI can chup.\n")

    name = input("Ten file template (vd: title_ex_arena.png): ").strip()
    if not name:
        print("Ten khong hop le.")
        return
    if not name.lower().endswith(".png"):
        name += ".png"

    try:
        left = int(input("left   (x1): ").strip())
        top = int(input("top    (y1): ").strip())
        right = int(input("right  (x2): ").strip())
        bottom = int(input("bottom (y2): ").strip())
    except ValueError:
        print("Toa do khong hop le.")
        return

    print("Chuan bi chup sau 5 giay, hay chuyen sang cua so game ngay...")
    for i in range(5, 0, -1):
        print(i, "...")
        time.sleep(1)

    shot = pyautogui.screenshot(region=(left, top, right - left, bottom - top))
    out_path = os.path.join(TEMPLATE_DIR, name)
    shot.save(out_path)
    print(f"Da luu template: {out_path}  (kich thuoc {shot.size})")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("pos", "crop"):
        print("Cach dung:")
        print("  python calibrate.py pos    # lay toa do chuot")
        print("  python calibrate.py crop   # chup anh template cho 1 vung UI")
        sys.exit(1)

    if sys.argv[1] == "pos":
        mode_pos()
    else:
        mode_crop()
