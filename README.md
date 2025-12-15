# 📚 Japanese Vocabulary Anki Deck Generator

> Awesome AI Assistant: Claude Opus 4.5 by Anthropic

Tạo Anki deck từ EPUB tiếng Nhật với đầy đủ enrichment.

## 🔧 Cài đặt

```bash
pip install -r requirements.txt --break-system-packages
```

## 🚀 Sử dụng

```bash
# Fast mode (nhanh, không audio)
python3 main.py sach.epub -o ./output --no-english --no-audio

# Full mode (chậm, có audio)
python3 main.py sach.epub -o ./output

# Force restart (xóa checkpoint)
python3 main.py sach.epub -o ./output --force-restart
```

## 🔊 Import Audio vào Anki

**QUAN TRỌNG:** Copy audio vào collection.media TRƯỚC khi import .apkg!

### Bước 1: Tìm thư mục collection.media

| OS      | Đường dẫn                                                         |
| ------- | ----------------------------------------------------------------- |
| Windows | `%APPDATA%\Anki2\<profile>\collection.media\`                     |
| macOS   | `~/Library/Application Support/Anki2/<profile>/collection.media/` |
| Linux   | `~/.local/share/Anki2/<profile>/collection.media/`                |

### Bước 2: Copy audio

```bash
# Linux/macOS
cp ./output/audio/*.mp3 ~/.local/share/Anki2/User\ 1/collection.media/

# Windows (PowerShell)
Copy-Item .\output\audio\*.mp3 "$env:APPDATA\Anki2\User 1\collection.media\"
```

### Bước 3: Import .apkg

File → Import trong Anki.

## 🗂 Data Files (Edit để mở rộng)

```
data/
├── hanviet.json           # Kanji → Hán Việt
├── radicals.json          # 48 bộ thủ
├── pitch_accent.json      # Pitch patterns (0=heiban, 1=atamadaka, 2+=nakadaka)
└── example_sentences.json # Câu ví dụ [["JP", "VN"], ...]
```

## Options

| Flag              | Mô tả                        |
| ----------------- | ---------------------------- |
| `--no-english`    | Bỏ lookup tiếng Anh          |
| `--no-audio`      | Không generate audio         |
| `--no-pitch`      | Không generate pitch diagram |
| `--no-stroke`     | Không generate stroke order  |
| `--delay N`       | Delay API calls (giây)       |
| `--force-restart` | Xóa checkpoint, chạy lại     |
