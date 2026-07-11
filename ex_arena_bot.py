# -*- coding: utf-8 -*-
"""
ex_arena_bot.py
----------------
Bot tu dong: vao EX Arena (Toram Online) -> danh boss lap combo hoi mana
+ skill damage -> qua man hinh ket qua -> lap lai.

QUAN TRONG - DOC TRUOC KHI CHAY:
  1) Game chay o do phan giai 960x540 (60fps). 
  2) Toram dung DirectInput nen click chuot/gui phim kieu "ao" thong
     thuong (pyautogui / SetCursorPos) nhieu khi bi game bo qua. Script
     nay dung ctypes SendInput de mo phong input o muc driver
  3) Bot uu tien nhan dien UI bang OpenCV template matching (dat trong thu muc templates/). 
     Neu khong tim thay template (chua chup / ten sai) thi se fallback ve
     click theo toa do co dinh + thoi gian cho co dinh (kem canh bao).
  4) Script gia dinh cua so game da o TRANG THAI FOREGROUND (dang active,
     dang duoc focus). Ham force_foreground() se co gang dua cua so len
     truoc

Yeu cau cai dat:
    pip install pyautogui opencv-python numpy pillow pywin32

Chay:
    python ex_arena_bot.py
Dung khan cap:
    Di chuyen chuot len goc tren-trai man hinh (pyautogui FAILSAFE)
    hoac nhan Ctrl+C trong terminal.
"""

import ctypes
import time
import random
import os
import sys

import numpy as np
import pyautogui
import cv2

try:
    import win32gui
    import win32process
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pyautogui.FAILSAFE = True

# =====================================================================
# CONFIG - CAN HIEU CHINH LAI THEO MAY / DO PHAN GIAI
# =====================================================================

WINDOW_TITLE_KEYWORD = "Toram Online"   # chuoi con trong title cua so game

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# --- Phim skill (6,7,8 la combo hoi mana; 4 la buff 30s; Q la skill damage chinh). Doi lai neu keybind trong game khac.
KEY_SKILL_2 = "2"
KEY_SKILL_8 = "8"
KEY_SKILL_4 = "4"
KEY_SKILL_Q = "q"
KEY_MOVE_FORWARD = "w"
KEY_INTERACT = "f"      # phim tuong tac / bam NEXT bang ban phim
KEY_TAB = "tab"         # mo danh sach muc tieu / NPC gan do
KEY_ESC = "esc"

DELAY_SKILL2_TO_8 = 2.0            # doi giua skill 2 va skill 8 (combo hoi mana moi)
DELAY_AFTER_SKILL4_BUFF = 0.5      # doi ngan sau khi bam skill 4
DELAY_HOLD_W = 1.4                 # giu W de di chuyen len 1 doan ngan
WAIT_AFTER_READY = 7.0             # cho vao cho boss sau khi bam "I'm ready" (user xac nhan 7s)
WAIT_SKILL_Q_CAST = 3.0            # doi skill Q (damage chinh) thuc hien xong
WAIT_VICTORY_OK = 6.5              # doi truoc khi bam OK / spam ESC o man ket qua
TEMPLATE_MATCH_THRESHOLD = 0.80    # do khop toi thieu (0-1) de chap nhan template
UI_WAIT_TIMEOUT = 12.0             # toi da cho bao lau de 1 UI xuat hien

# Do phan giai cua game: 960x540 @ 60fps.
GAME_W, GAME_H = 960, 540

# --- Toa do FALLBACK (dung khi KHONG tim thay template tuong ung).
#     Day la placeholder tinh theo % kich thuoc TOAN MAN HINH
#     (pyautogui.size()), khong phai % cua so game 960x540. Neu game
#     chay windowed (khong fullscreen) thi % nay se SAI vi cua so game
#     chi chiem 1 phan man hinh - luc do BAT BUOC phai dung calibrate.py
#     -> pos de lay toa do PIXEL that va thay truc tiep vao day.
SCREEN_W, SCREEN_H = pyautogui.size()

FALLBACK_POS = {
    # vi tri dong NPC trong bang danh sach muc tieu (mo bang phim Tab)
    "npc_list_entry": (0.50, 0.35),
    # dong lua chon dau tien trong bang 3 lua chon (EX Arena Entry)
    "dialog_option_1": (0.50, 0.30),
    # nut NEXT trang Information
    "next_button": (0.82, 0.80),
    # nut "I'm ready" man hinh EVENT BATTLE
    "ready_button": (0.72, 0.68),
    # nut OK man hinh chien thang
    "victory_ok_button": (0.50, 0.62),
}


def fallback_point(name):
    fx, fy = FALLBACK_POS[name]
    return int(fx * SCREEN_W), int(fy * SCREEN_H)


# =====================================================================
# LOP INPUT MUC THAP (SendInput) - de tuong thich voi DirectInput
# =====================================================================

PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


class InputUnion(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", InputUnion)]


INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# Bang scan code (set 1) cho cac phim hay dung. Them neu can.
SCANCODES = {
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "w": 0x11, "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21,
    "q": 0x10, "e": 0x12, "esc": 0x01, "tab": 0x0F,
}


def _send_key(scan_code, key_up=False):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
    extra = ctypes.c_ulong(0)
    ii_ = InputUnion()
    ii_.ki = KeyBdInput(0, scan_code, flags, 0, ctypes.pointer(extra))
    x = Input(INPUT_KEYBOARD, ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))


def key_press(key, hold=0.05):
    """Nhan tha nhanh 1 phim (scancode-based SendInput)."""
    sc = SCANCODES.get(key.lower())
    if sc is None:
        # fallback ve pyautogui neu khong co scancode dinh nghia san
        pyautogui.keyDown(key)
        time.sleep(hold)
        pyautogui.keyUp(key)
        return
    _send_key(sc, key_up=False)
    time.sleep(hold)
    _send_key(sc, key_up=True)


def key_down(key):
    sc = SCANCODES.get(key.lower())
    if sc is None:
        pyautogui.keyDown(key)
        return
    _send_key(sc, key_up=False)


def key_up(key):
    sc = SCANCODES.get(key.lower())
    if sc is None:
        pyautogui.keyUp(key)
        return
    _send_key(sc, key_up=True)


def hold_key_for(key, duration):
    key_down(key)
    time.sleep(duration)
    key_up(key)


def _send_mouse_click(x, y):
    """Click chuot trai tai toa do man hinh tuyet doi (x, y), dung SendInput."""
    norm_x = int(x * 65535 / SCREEN_W)
    norm_y = int(y * 65535 / SCREEN_H)
    extra = ctypes.c_ulong(0)

    ii_move = InputUnion()
    ii_move.mi = MouseInput(norm_x, norm_y, 0,
                             MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0,
                             ctypes.pointer(extra))
    move = Input(INPUT_MOUSE, ii_move)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(move), ctypes.sizeof(move))
    time.sleep(0.05)

    ii_down = InputUnion()
    ii_down.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
    down = Input(INPUT_MOUSE, ii_down)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(down), ctypes.sizeof(down))
    time.sleep(0.07)

    ii_up = InputUnion()
    ii_up.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))
    up = Input(INPUT_MOUSE, ii_up)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(up), ctypes.sizeof(up))


def click_at(x, y, jitter=3):
    """Click co jitter nho de trong tu nhien hon, tranh bi phat hien pattern qua deu."""
    jx = x + random.randint(-jitter, jitter)
    jy = y + random.randint(-jitter, jitter)
    _send_mouse_click(jx, jy)


def double_click_at(x, y, jitter=3, gap=0.12):
    """Double-click (vd: double-click 1 dong NPC trong danh sach muc tieu
    de tu dong di chuyen toi NPC do)."""
    jx = x + random.randint(-jitter, jitter)
    jy = y + random.randint(-jitter, jitter)
    _send_mouse_click(jx, jy)
    time.sleep(gap)
    _send_mouse_click(jx, jy)


# =====================================================================
# CUA SO GAME: dua len foreground
# =====================================================================

def force_foreground():
    if not HAS_WIN32:
        return False
    hwnd = win32gui.FindWindow(None, None)
    target = None

    def _enum(h, _):
        nonlocal target
        if win32gui.IsWindowVisible(h) and WINDOW_TITLE_KEYWORD.lower() in win32gui.GetWindowText(h).lower():
            target = h
    win32gui.EnumWindows(_enum, None)

    if not target:
        return False

    fg = win32gui.GetForegroundWindow()
    fg_thread = win32process.GetWindowThreadProcessId(fg)[0]
    target_thread = win32process.GetWindowThreadProcessId(target)[0]
    cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()

    ctypes.windll.user32.AttachThreadInput(cur_thread, fg_thread, True)
    ctypes.windll.user32.AttachThreadInput(cur_thread, target_thread, True)
    win32gui.ShowWindow(target, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(target)
    ctypes.windll.user32.AttachThreadInput(cur_thread, fg_thread, False)
    ctypes.windll.user32.AttachThreadInput(cur_thread, target_thread, False)
    return True


# =====================================================================
# NHAN DIEN UI BANG TEMPLATE MATCHING
# =====================================================================

def screenshot_np():
    img = pyautogui.screenshot()
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def find_template(template_name, threshold=TEMPLATE_MATCH_THRESHOLD):
    """
    Tim 1 template (anh PNG trong templates/) tren man hinh hien tai.
    Tra ve (center_x, center_y, score) neu tim thay, None neu khong.
    """
    path = os.path.join(TEMPLATE_DIR, template_name)
    if not os.path.isfile(path):
        return None

    template = cv2.imread(path, cv2.IMREAD_COLOR)
    if template is None:
        return None

    screen = screenshot_np()
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < threshold:
        return None

    h, w = template.shape[:2]
    cx = max_loc[0] + w // 2
    cy = max_loc[1] + h // 2
    return cx, cy, max_val


def wait_for_template(template_name, timeout=UI_WAIT_TIMEOUT, poll=0.3):
    """Cho toi khi template xuat hien, tra ve (x,y) hoac None neu timeout."""
    start = time.time()
    while time.time() - start < timeout:
        found = find_template(template_name)
        if found:
            return found[0], found[1]
        time.sleep(poll)
    return None


def click_ui(template_name, fallback_key, timeout=UI_WAIT_TIMEOUT, extra_wait=0.0):
    """
    Doi UI xuat hien (qua template) roi click vao do.
    Neu khong tim thay template trong 'timeout' giay -> canh bao va
    click theo toa do fallback co dinh (FALLBACK_POS[fallback_key]).
    """
    pos = wait_for_template(f"{template_name}.png", timeout=timeout)
    if extra_wait:
        time.sleep(extra_wait)

    if pos:
        print(f"[UI] Tim thay '{template_name}' tai {pos}, click.")
        click_at(*pos)
        return True

    print(f"[CANH BAO] Khong tim thay template '{template_name}.png' sau {timeout}s "
          f"-> dung toa do fallback '{fallback_key}'. Hay chup template bang "
          f"calibrate.py de tang do chinh xac.")
    click_at(*fallback_point(fallback_key))
    return False


# =====================================================================
# CAC HANH DONG NGHIEP VU (13 buoc)
# =====================================================================

def mana_combo():
    """Buoc 1 / 9 / (lap trong combat_loop): bam skill 2, cho 2s de skill
    cast xong, roi bam skill 8 de hoi mana."""
    print("[COMBO] Skill 2 -> (cho %.1fs) -> Skill 8" % DELAY_SKILL2_TO_8)
    key_press(KEY_SKILL_2, hold=0.05)
    time.sleep(DELAY_SKILL2_TO_8)
    key_press(KEY_SKILL_8, hold=0.05)


def go_to_npc_via_list():
    """Buoc 2 (moi): mo danh sach muc tieu bang Tab, double-click dong NPC
    de nhan vat TU DONG di chuyen toi va tu mo bang 3 lua chon (EX Arena
    Entry / Prize Exchange / Quit)."""
    print("[NPC] Mo danh sach muc tieu (phim Tab)...")
    key_press(KEY_TAB, hold=0.05)
    time.sleep(0.6)

    pos = wait_for_template("npc_list_entry.png", timeout=UI_WAIT_TIMEOUT)
    if pos:
        print(f"[NPC] Tim thay dong NPC trong danh sach tai {pos}, double-click...")
        double_click_at(*pos)
    else:
        print("[CANH BAO] Khong tim thay template 'npc_list_entry.png' -> dung "
              "toa do fallback. Hay chup template nay bang calibrate.py (crop "
              "dong ten NPC trong bang hien ra sau khi bam Tab).")
        double_click_at(*fallback_point("npc_list_entry"))

    print("[NPC] Doi nhan vat tu dong di chuyen toi NPC va bang lua chon mo ra...")
    # thoi gian tu-di-chuyen phu thuoc khoang cach, cho lau hon binh thuong
    wait_for_template("dialog_option_1.png", timeout=UI_WAIT_TIMEOUT * 1.5)


def enter_ex_arena():
    """Buoc 3-4 (moi):
    - Bang 3 lua chon da mo san (tu go_to_npc_via_list) -> click 'EX Arena Entry'.
    - Trang Information hien ra kem nut NEXT -> click NEXT (hoac phim F).
    - Chuyen thang sang trang EVENT BATTLE (xu ly o confirm_ready)."""
    print("[DIALOG] Chon 'EX Arena Entry' (dong dau trong 3 lua chon)...")
    click_ui("dialog_option_1", "dialog_option_1", timeout=UI_WAIT_TIMEOUT)
    time.sleep(0.6)

    print("[DIALOG] Trang Information -> bam NEXT...")
    found = wait_for_template("next_button.png", timeout=UI_WAIT_TIMEOUT)
    if found:
        click_at(found[0], found[1])
    else:
        key_press(KEY_INTERACT)  # phim F thay cho click NEXT
        print("[CANH BAO] Khong thay template NEXT, da dung phim F thay the.")
    time.sleep(0.8)


def confirm_ready():
    """Buoc 5-6 (moi): man hinh EVENT BATTLE + nut I'm ready -> click -> doi 7s vao cho boss."""
    print("[EVENT BATTLE] Cho va click nut 'I'm ready'...")
    click_ui("ready_button", "ready_button", timeout=UI_WAIT_TIMEOUT)
    print(f"[EVENT BATTLE] Doi {WAIT_AFTER_READY}s de den cho boss...")
    time.sleep(WAIT_AFTER_READY)


def move_toward_diamond_and_buff():
    """Buoc 7-8: giu W tien len gan kim cuong xanh, roi bam skill 4 (buff 30s, 1 lan)."""
    print(f"[DI CHUYEN] Giu W trong {DELAY_HOLD_W}s de tien len gan kim cuong xanh...")
    hold_key_for(KEY_MOVE_FORWARD, DELAY_HOLD_W)
    time.sleep(0.3)

    print("[BUFF] Bam skill 4 (buff 30s, chi 1 lan dau tran)...")
    key_press(KEY_SKILL_4, hold=0.08)
    time.sleep(DELAY_AFTER_SKILL4_BUFF)


def is_victory_screen_visible():
    return find_template("victory_screen.png") is not None


def is_still_in_combat():
    """Heuristic: neu KHONG thay man hinh chien thang thi coi nhu van
    dang trong tran."""
    return not is_victory_screen_visible()


def combat_loop():
    """
    Buoc 9-10: sau buff -> combo hoi mana -> dung yen bam skill Q (damage
    chinh) -> doi 3s -> lai combo hoi mana -> lap lai cho toi khi thay
    man hinh ket qua (chien thang) xuat hien.
    """
    mana_combo()  # buoc 9: ngay sau buff skill 4

    print("[COMBAT] Bat dau vong lap: Q (damage) -> combo hoi mana -> lap lai...")
    while is_still_in_combat():
        print("[COMBAT] Bam skill Q, dung yen cho ~%.1fs..." % WAIT_SKILL_Q_CAST)
        key_press(KEY_SKILL_Q, hold=0.08)
        time.sleep(WAIT_SKILL_Q_CAST)

        if not is_still_in_combat():
            break

        mana_combo()

    print("[COMBAT] Phat hien man hinh ket qua (hoac het thoi gian cho), thoat vong lap.")


def handle_end_screen():
    """
    Buoc 11:
      - Neu la man hinh "cho boss" (khong phai man chien thang that su):
        spam ESC de bo qua, doi 6-7s.
      - Neu la man hinh chien thang that: bam OK, doi 6-7s.
    Vi rat kho phan biet 2 loai man hinh nay chi bang mau/khong co
    template rieng, script se: thu tim template 'victory_ok_button.png'
    truoc; neu co thi click OK; neu KHONG thay trong vai giay thi spam
    ESC nhu mo ta cho truong hop con lai.
    """
    print("[KET THUC TRAN] Kiem tra loai man hinh ket qua...")
    ok_pos = wait_for_template("victory_ok_button.png", timeout=3.0)

    if ok_pos:
        print("[KET THUC TRAN] Thay nut OK -> click OK.")
        click_at(*ok_pos)
    else:
        print("[KET THUC TRAN] Khong thay nut OK -> spam phim ESC de bo qua man cho.")
        for _ in range(10):
            key_press(KEY_ESC, hold=0.05)
            time.sleep(0.3)

    print(f"[KET THUC TRAN] Doi {WAIT_VICTORY_OK}s truoc khi lap lai tu dau...")
    time.sleep(WAIT_VICTORY_OK)


# =====================================================================
# STATE MACHINE CHINH
# =====================================================================

def run_once():
    mana_combo()                 # buoc 1
    go_to_npc_via_list()         # buoc 2 (Tab -> double-click NPC trong list)
    enter_ex_arena()             # buoc 3-4 (chon EX Arena Entry -> NEXT)
    confirm_ready()              # buoc 5-6 (I'm ready -> cho 7s vao boss)
    move_toward_diamond_and_buff()  # buoc 7-8
    combat_loop()                # buoc 9-10
    handle_end_screen()          # buoc 11


def main():
    print("=" * 70)
    print("EX ARENA BOT - Toram Online")
    print("Ban co 5 giay de chuyen sang cua so game truoc khi bot bat dau...")
    print("(di chuyen chuot len goc tren-trai man hinh de dung khan cap)")
    print("=" * 70)
    for i in range(5, 0, -1):
        print(i, "...")
        time.sleep(1)

    force_foreground()

    run_count = 0
    try:
        while True:
            run_count += 1
            print(f"\n########## LUOT CHAY #{run_count} ##########")
            run_once()
    except KeyboardInterrupt:
        print("\nDa dung bot theo yeu cau (Ctrl+C).")
    except pyautogui.FailSafeException:
        print("\nDa dung bot (kich hoat FAILSAFE - chuot len goc tren-trai).")


if __name__ == "__main__":
    main()