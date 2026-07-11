# EX Arena Bot - Toram Online

Bot tự động thực hiện quy trình: combo hồi mana (skill 6→7→8) → di chuyển
đến NPC hình cầu hồng → vào EX Arena → xác nhận sẵn sàng → di chuyển vào
vị trí → buff (skill 4) → đánh boss lặp combo (skill Q + combo hồi mana)
→ xử lý màn hình kết thúc → lặp lại.

## 1. Cài đặt

```bash
pip install pyautogui opencv-python numpy pillow pywin32
```

Không cần cài package `keyboard` — `calibrate.py` đọc phím ESC bằng
`win32api.GetAsyncKeyState` (cùng cách bạn đã dùng trong
`toram_collab_bot.py` trước đó để đọc phím F8/F9), nên chỉ cần
`pywin32` là đủ.

Chạy trên Windows (vì dùng `pywin32` và `SendInput` để tương thích với
DirectInput của game). Nên chạy terminal với quyền **Administrator** để
SendInput không bị chặn bởi UAC khi game chạy quyền cao hơn.

## 2. Vì sao phải hiệu chỉnh (calibrate) trước khi chạy?

Game chạy ở độ phân giải gốc **960x540 (60fps)**. Nhưng toạ độ click
trong bot lại phụ thuộc vào **kích thước cửa sổ hiển thị thực tế trên
màn hình bạn** — nếu bạn chạy fullscreen ở 1920x1080, hoặc chạy
windowed nhưng kéo giãn/thu nhỏ cửa sổ, thì toạ độ pixel sẽ khác hẳn
960x540. Vì vậy toạ độ "đoán" từ video sẽ **sai** trên máy bạn.
`ex_arena_bot.py` có 2 lớp phòng hộ:

1. **Template matching (chính xác nhất)**: bot chụp màn hình và tìm
   ảnh mẫu (ví dụ nút NEXT, nút "I'm ready"...) bằng OpenCV. Cần bạn tự
   chụp các ảnh mẫu này **trên chính máy/độ phân giải bạn sẽ chạy bot**.
2. **Toạ độ fallback (dự phòng)**: nếu không tìm thấy ảnh mẫu, bot click
   vào toạ độ cố định khai báo trong `FALLBACK_POS` (đầu file
   `ex_arena_bot.py`). Đây chỉ là toạ độ tạm/ước lượng, bạn nên thay
   bằng toạ độ thật lấy từ bước dưới.

## 3. Các bước hiệu chỉnh

### 3.1. Lấy toạ độ fallback (dự phòng) bằng chuột

```bash
python calibrate.py pos
```

Di chuột đến từng vị trí sau trong game rồi nhấn `ESC` để in toạ độ,
rồi cập nhật vào `FALLBACK_POS` trong `ex_arena_bot.py` (dùng toạ độ
pixel thật, không cần tính theo %):

- NPC hình cầu hồng
- Dòng "EX Arena Entry" trong bảng 2 lựa chọn
- Nút NEXT (trang thông tin 2 và 3)
- Nút "I'm ready"
- Nút OK ở màn hình chiến thắng

### 3.2. Chụp ảnh mẫu (template) cho từng UI

```bash
python calibrate.py crop
```

Làm lần lượt cho từng UI, đặt tên file **đúng như bên dưới** (bot tìm
đúng các tên này trong thư mục `templates/`):

| Tên file cần lưu              | Chụp lúc nào |
|--------------------------------|--------------|
| `npc_pink_orb.png`             | Vòng tròn hồng của NPC hiện trên màn hình |
| `title_ex_arena_required.png`  | Dòng chữ "EX Arena Entry Required: Lv110+" |
| `dialog_option_1.png`          | Dòng "EX Arena Entry" trong bảng 2 lựa chọn |
| `next_button.png`              | Nút NEXT ở trang thông tin 2 hoặc 3 |
| `ready_button.png`             | Nút "I'm ready" |
| `victory_ok_button.png`        | Nút OK ở màn hình chiến thắng |
| `victory_screen.png`           | Một vùng đặc trưng của màn hình chiến thắng (dùng để bot biết trận đã kết thúc — nên chọn logo/chữ "BATTLE FINISHED" hoặc khung phần thưởng) |

**Mẹo chụp**: crop vùng càng nhỏ và đặc trưng (icon, chữ, khung viền)
càng dễ match chính xác — tránh crop cả vùng nền lớn vì nền game hay
đổi (hiệu ứng, ánh sáng), dễ làm match sai.

## 4. Tinh chỉnh thời gian (timing)

Các hằng số thời gian ở đầu `ex_arena_bot.py` được ước lượng từ video
~55s bạn gửi. Nếu combo bị hụt (skill sau bắn trước khi skill trước
xong) hoặc chờ quá lâu, chỉnh các giá trị này:

```python
DELAY_BETWEEN_COMBO_SKILL = 0.65   # giãn cách giữa skill 6 -> 7 -> 8
DELAY_HOLD_W = 1.4                 # thời gian giữ W để tiến lên
WAIT_AFTER_READY = 5.5             # chờ mở màn sau khi bấm "I'm ready"
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
  hạn** bước 12 — bắt buộc phải chụp template này trước khi chạy thật.
- Bước 2 (di chuyển đến NPC) dùng click-to-move (click thẳng vào NPC
  trên màn hình) vì Toram không hỗ trợ pathfinding qua phím một cách
  đáng tin cậy. Nếu nhân vật ở quá xa hoặc bị vật cản, có thể cần click
  nhiều lần — bạn có thể sửa `go_to_npc()` để click lặp lại vài lần
  nếu nhân vật thường xuất phát ở vị trí xa NPC.
- Bước 13 phân biệt "màn hình chờ" và "màn hình chiến thắng thật" bằng
  cách thử tìm `victory_ok_button.png` trước; nếu không thấy thì spam
  ESC. Nếu 2 màn hình này dễ nhầm lẫn ở máy bạn, nên chụp thêm template
  riêng cho từng loại và tách logic rõ hơn trong `handle_end_screen()`.
