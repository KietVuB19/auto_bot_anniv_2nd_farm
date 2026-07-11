# -*- coding: utf-8 -*-
"""
ex_arena_bot.py
----------------
Bot tu dong: vao EX Arena (Toram Online) -> danh boss lap combo hoi mana
+ skill damage -> qua man hinh ket qua -> lap lai.

QUAN TRONG - DOC TRUOC KHI CHAY:
  1) Game chay o do phan giai 960x540 (60fps). Neu cua so game tren may
     ban KHONG dung dung 960x540 (vd: fullscreen 1920x1080, hoac cua so
     windowed bi keo gian/thu nho), toa do se bi lech. TAT CA toa do
     trong CONFIG ben duoi la GIA TRI MAU (placeholder), ban PHAI tu
     hieu chinh bang calibrate.py (xem huong dan trong file do).
  2) Toram dung DirectInput nen click chuot/gui phim kieu "ao" thong
     thuong (pyautogui / SetCursorPos) nhieu khi bi game bo qua. Script
     nay dung ctypes SendInput (giong engine ban da dung o
     toram_collab_bot.py) de mo phong input o muc driver, dang tin cay
     hon.
  3) Bot uu tien nhan dien UI bang OpenCV template matching (anh mau
     ban tu chup bang calibrate.py, dat trong thu muc templates/). Neu
     khong tim thay template (chua chup / ten sai) thi se fallback ve
     click theo toa do co dinh + thoi gian cho co dinh (kem canh bao).
  4) Script gia dinh cua so game da o TRANG THAI FOREGROUND (dang active,
     dang duoc focus). Ham force_foreground() se co gang dua cua so len
     truoc, nhung cach chac chan nhat van la ban tu click vao cua so
     game truoc khi bam Start / chay script.

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
# CONFIG - CAN HIEU CHINH LAI THEO MAY / DO PHAN GIAI CUA BAN
# =====================================================================

WINDOW_TITLE_KEYWORD = "Toram Online"   # chuoi con trong title cua so game

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# --- Phim skill (theo mo ta cua ban: 6,7,8 la combo hoi mana; 4 la buff
#     30s; Q la skill damage chinh). Doi lai neu keybind trong game khac.
KEY_SKILL_6 = "6"
KEY_SKILL_7 = "7"
KEY_SKILL_8 = "8"
KEY_SKILL_4 = "4"
KEY_SKILL_Q = "q"
KEY_MOVE_FORWARD = "w"
KEY_INTERACT = "f"      # phim tuong tac / bam NEXT bang ban phim
KEY_ESC = "esc"

# --- Thoi gian (giay) - DUA TREN QUAN SAT VIDEO ~55s, HAY TINH CHINH LAI
#     bang cach bam giay hoac xem lai video neu combo bi lech.
DELAY_BETWEEN_COMBO_SKILL = 0.65   # doi giua click skill 6->7->8
DELAY_AFTER_SKILL4_BUFF = 0.5      # doi ngan sau khi bam skill 4
DELAY_HOLD_W = 1.4                 # giu W de di chuyen len 1 doan ngan
WAIT_AFTER_READY = 5.5             # doi man hinh mo man sau khi bam "I'm ready"
WAIT_SKILL_Q_CAST = 3.0            # doi skill Q (damage chinh) thuc hien xong
WAIT_VICTORY_OK = 6.5              # doi truoc khi bam OK / spam ESC o man ket qua
TEMPLATE_MATCH_THRESHOLD = 0.80    # do khop toi thieu (0-1) de chap nhan template
UI_WAIT_TIMEOUT = 12.0             # toi da cho bao lau de 1 UI xuat hien

# Do phan giai GOC cua game (theo xac nhan cua ban): 960x540 @ 60fps.
# Chi dung de tham chieu/ghi chu - KHONG dung de tinh toan neu cua so
# game tren may ban dang chay o kich thuoc khac.
GAME_W, GAME_H = 960, 540

# --- Toa do FALLBACK (dung khi KHONG tim thay template tuong ung).
#     Day la placeholder tinh theo % kich thuoc TOAN MAN HINH
#     (pyautogui.size()), khong phai % cua so game 960x540. Neu game
#     chay windowed (khong fullscreen) thi % nay se SAI vi cua so game
#     chi chiem 1 phan man hinh - luc do BAT BUOC phai dung calibrate.py
#     -> pos de lay toa do PIXEL that va thay truc tiep vao day.
SCREEN_W, SCREEN_H = pyautogui.size()

FALLBACK_POS = {
    # goc phai man hinh, gan minimap - vi tri NPC hinh cau hong (uoc luong)
    "npc_pink_orb": (0.90, 0.30),
    # dong lua chon dau tien trong bang 2 lua chon (EX Arena Entry)
    "dialog_option_1": (0.50, 0.42),
    # nut NEXT trang thong tin 2 va 3 (thuong o goc duoi-phai hop thoai)
    "next_button": (0.82, 0.80),
    # nut "I'm ready" man hinh EVENT BATTLE
    "ready_button": (0.50, 0.68),
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
    "q": 0x10, "e": 0x12, "esc": 0x01,
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
# CAC HANH DONG NGHIEP VU (theo dung 13 buoc ban mo ta)
# =====================================================================

def mana_combo():
    """Buoc 1 / 11 / 12(lap): click nhanh skill 6 -> 7 -> 8, doi skill
    truoc cast xong roi moi bam skill tiep theo (khong spam qua nhanh)."""
    print("[COMBO] 6 -> 7 -> 8")
    key_press(KEY_SKILL_6, hold=0.05)
    time.sleep(DELAY_BETWEEN_COMBO_SKILL)
    key_press(KEY_SKILL_7, hold=0.05)
    time.sleep(DELAY_BETWEEN_COMBO_SKILL)
    key_press(KEY_SKILL_8, hold=0.05)
    time.sleep(DELAY_BETWEEN_COMBO_SKILL)


def go_to_npc():
    """Buoc 2: di chuyen den NPC hinh cau hong o goc phai.
    Toram khong co pathfinding qua phim, cach on dinh nhat la CLICK
    truc tiep vao NPC tren man hinh (click-to-move), roi doi nhan vat
    di toi noi."""
    print("[DI CHUYEN] Toi NPC hinh cau hong...")
    pos = wait_for_template("npc_pink_orb.png", timeout=UI_WAIT_TIMEOUT)
    if pos:
        click_at(*pos)
    else:
        print("[CANH BAO] Khong thay template NPC, click theo toa do fallback.")
        click_at(*fallback_point("npc_pink_orb"))
    # doi nhan vat di chuyen toi gan NPC (chinh lai thoi gian neu can)
    time.sleep(2.0)


def enter_ex_arena_dialogs():
    """Buoc 3-6: click title -> chon dong 1 -> NEXT x2."""

    # Buoc 3: title "EX Arena Entry Required: Lv110+" xuat hien khi
    # dung gan NPC -> click vao title do de mo bang thoai.
    print("[DIALOG] Cho title 'EX Arena Entry Required' va click...")
    click_ui("title_ex_arena_required", "npc_pink_orb", timeout=UI_WAIT_TIMEOUT)
    time.sleep(0.6)

    # Buoc 4: bang 2 lua chon hien ra, chon dong dau tien "EX Arena Entry"
    print("[DIALOG] Chon dong 'EX Arena Entry' (lua chon 1/2)...")
    click_ui("dialog_option_1", "dialog_option_1", timeout=UI_WAIT_TIMEOUT)
    time.sleep(0.8)

    # Buoc 5: trang thong tin 2 + nut NEXT
    print("[DIALOG] Trang thong tin 2 -> bam NEXT...")
    found = wait_for_template("next_button.png", timeout=UI_WAIT_TIMEOUT)
    if found:
        click_at(found[0], found[1])
    else:
        key_press(KEY_INTERACT)  # phim F thay cho click NEXT
        print("[CANH BAO] Khong thay template NEXT, da dung phim F thay the.")
    time.sleep(0.8)

    # Buoc 6: trang thong tin 3 + nut NEXT (giong buoc 5)
    print("[DIALOG] Trang thong tin 3 -> bam NEXT...")
    found = wait_for_template("next_button.png", timeout=UI_WAIT_TIMEOUT)
    if found:
        click_at(found[0], found[1])
    else:
        key_press(KEY_INTERACT)
        print("[CANH BAO] Khong thay template NEXT, da dung phim F thay the.")
    time.sleep(0.8)


def confirm_ready():
    """Buoc 7-8: man hinh EVENT BATTLE + nut I'm ready -> click -> doi mo man."""
    print("[EVENT BATTLE] Cho va click nut 'I'm ready'...")
    click_ui("ready_button", "ready_button", timeout=UI_WAIT_TIMEOUT)
    print(f"[EVENT BATTLE] Doi {WAIT_AFTER_READY}s de mo man...")
    time.sleep(WAIT_AFTER_READY)


def move_toward_diamond_and_buff():
    """Buoc 9-10: giu W tien len gan kim cuong xanh, roi bam skill 4 (buff 30s, 1 lan)."""
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
    dang trong tran. Ban co the thay bang cach nhan dien thanh HP boss
    hoac icon boss neu co template rieng."""
    return not is_victory_screen_visible()


def combat_loop():
    """
    Buoc 11-12: sau buff -> combo hoi mana -> dung yen bam skill Q (damage
    chinh) -> doi 3s -> lai combo hoi mana -> lap lai cho toi khi thay
    man hinh ket qua (chien thang) xuat hien.
    """
    mana_combo()  # buoc 11: ngay sau buff skill 4

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
    Buoc 13:
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
    go_to_npc()                  # buoc 2
    enter_ex_arena_dialogs()     # buoc 3-6
    confirm_ready()              # buoc 7-8
    move_toward_diamond_and_buff()  # buoc 9-10
    combat_loop()                # buoc 11-12
    handle_end_screen()          # buoc 13


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
