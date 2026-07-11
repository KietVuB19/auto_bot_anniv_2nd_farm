# EX Arena Bot - Toram Online

Bot tự động thực hiện quy trình: combo hồi mana (skill 2 → chờ 2s → skill 8)
→ mở danh sách mục tiêu bằng phím **Tab**, double-click NPC để tự động di
chuyển tới và mở bảng lựa chọn → chọn "EX Arena Entry" → NEXT → "I'm ready"
→ chờ 7s vào trận → di chuyển vào vị trí → buff (skill 4) → đánh boss lặp
combo (skill Q + combo hồi mana) → xử lý màn hình kết thúc → lặp lại.

## 1. Cài đặt

```bash
pip install pyautogui opencv-python numpy pillow pywin32
```

Chạy trên Windows (vì dùng `pywin32` và `SendInput` để tương thích với
DirectInput của game). Nên chạy terminal với quyền **Administrator** để
SendInput không bị chặn bởi UAC khi game chạy quyền cao hơn.

## 2. Vì sao phải hiệu chỉnh (calibrate) trước khi chạy?

Game chạy ở độ phân giải gốc **960x540 (60fps)**. 
`ex_arena_bot.py` có 2 lớp phòng hộ:

1. **Template matching (chính xác nhất)**: bot chụp màn hình và tìm
   ảnh mẫu (ví dụ nút NEXT, nút "I'm ready"...) bằng OpenCV. Cần tự
   chụp các ảnh mẫu này **trên chính máy/độ phân giải sẽ chạy bot**.
2. **Toạ độ fallback (dự phòng)**: nếu không tìm thấy ảnh mẫu, bot click
   vào toạ độ cố định khai báo trong `FALLBACK_POS` (đầu file
   `ex_arena_bot.py`). Đây chỉ là toạ độ tạm/ước lượng, nên thay
   bằng toạ độ thật lấy từ bước dưới.

## 3. Các bước hiệu chỉnh

### 3.1. Lấy toạ độ fallback (dự phòng) bằng chuột

```bash
python calibrate.py pos
```

Di chuột đến từng vị trí sau trong game rồi nhấn `ESC` để in toạ độ,
rồi cập nhật vào `FALLBACK_POS` trong `ex_arena_bot.py` (dùng toạ độ
pixel thật, không cần tính theo %):

- Dòng NPC trong bảng danh sách mục tiêu (mở bằng phím Tab)
- Dòng "EX Arena Entry" trong bảng 3 lựa chọn
- Nút NEXT ở trang Information
- Nút "I'm ready"
- Nút OK ở màn hình chiến thắng

### 3.2. Chụp ảnh mẫu (template) cho từng UI

```bash
python calibrate.py crop
```

**3 template đã có sẵn trong `templates/`**:

| File có sẵn | Nội dung |
|---|---|
| `dialog_option_1.png` | Dòng "EX Arena Entry" trong bảng 3 lựa chọn |
| `next_button.png` | Nút NEXT ở trang Information |
| `ready_button.png` | Nút "I'm ready!!" ở trang EVENT BATTLE |

**Còn 3 template bạn cần tự chụp** (vì phụ thuộc vào NPC cụ thể / màn
hình kết thúc trận mà video/ảnh mẫu chưa có):

| Tên file cần lưu | Chụp lúc nào |
|---|---|
| `npc_list_entry.png` | Bấm Tab để mở bảng danh sách mục tiêu, crop dòng tên NPC cần double-click |
| `victory_ok_button.png` | Nút OK ở màn hình chiến thắng |
| `victory_screen.png` | Một vùng đặc trưng của màn hình chiến thắng (dùng để bot biết trận đã kết thúc — nên chọn logo/chữ "BATTLE FINISHED" hoặc khung phần thưởng) |

**Mẹo chụp**: crop vùng càng nhỏ và đặc trưng (icon, chữ, khung viền)
càng dễ match chính xác — tránh crop cả vùng nền lớn vì nền game hay
đổi (hiệu ứng, ánh sáng), dễ làm match sai. Với `npc_list_entry.png`,
nếu danh sách Tab hiển thị nhiều NPC/quái cùng lúc, hãy crop sát vào
đúng dòng tên NPC bạn muốn (tránh crop luôn dòng bên trên/dưới, dễ
match nhầm mục tiêu khác).

## 4. Tinh chỉnh thời gian (timing)

Các hằng số thời gian ở đầu `ex_arena_bot.py` được ước lượng từ video
~55s bạn gửi. Nếu combo bị hụt (skill sau bắn trước khi skill trước
xong) hoặc chờ quá lâu, chỉnh các giá trị này:

```python
DELAY_SKILL2_TO_8 = 2.0            # chờ giữa skill 2 -> skill 8 (combo hồi mana)
DELAY_HOLD_W = 1.4                 # thời gian giữ W để tiến lên
WAIT_AFTER_READY = 7.0             # chờ vào chỗ boss sau khi bấm "I'm ready"
WAIT_SKILL_Q_CAST = 3.0            # chờ skill Q đánh xong
WAIT_VICTORY_OK = 6.5              # chờ ở màn hình kết thúc trước khi lặp lại
```

## 5. Chạy bot

```bash
python ex_arena_bot.py
```

Bạn có 5 giây để chuyển sang cửa sổ game trước khi bot bắt đầu. Dừng
khẩn cấp bằng cách di chuột lên góc trên-trái màn hình (pyautogui
FAILSAFE) hoặc `Ctrl+C` trong terminal.

## 6. Giới hạn đã biết

- `combat_loop()` hiện chỉ dừng vòng lặp khi tìm thấy
  `victory_screen.png`. Nếu chưa chụp template này, bot sẽ **lặp vô
  hạn** ở bước đánh boss — bắt buộc phải chụp template này trước khi
  chạy thật.
- Bước mở danh sách mục tiêu (Tab) giả định NPC cần double-click luôn
  xuất hiện ở vị trí ổn định trong danh sách. Nếu danh sách có nhiều
  mục (quái, NPC khác) và thứ tự thay đổi liên tục, `npc_list_entry.png`
  cần crop đủ đặc trưng (sát tên NPC) để không match nhầm dòng khác.
- Sau khi double-click NPC trong danh sách, nhân vật cần thời gian tự
  di chuyển tới nơi trước khi bảng 3 lựa chọn hiện ra — bot đang chờ
  `dialog_option_1.png` xuất hiện trong tối đa `UI_WAIT_TIMEOUT * 1.5`
  giây; nếu NPC ở rất xa, có thể cần tăng `UI_WAIT_TIMEOUT`.
- Bước cuối phân biệt "màn hình chờ" và "màn hình chiến thắng thật" bằng
  cách thử tìm `victory_ok_button.png` trước; nếu không thấy thì spam
  ESC.