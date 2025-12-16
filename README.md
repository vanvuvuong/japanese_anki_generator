# 📚 Japanese Vocabulary Anki Deck Generator

> Awesome AI Assistant: Claude Opus 4.5 by Anthropic

Tạo Anki deck từ EPUB tiếng Nhật với đầy đủ enrichment.

## ✨ Features

- **Furigana** (ruby text) cho từ vựng và câu ví dụ
- **JLPT Level** (N5→N1) với badge màu
- **Pitch Accent** diagram
- **Hán Việt** readings
- **Stroke Order** diagrams (dark mode supported)
- **Audio TTS** cho từ vựng + câu ví dụ (Edge TTS)
- **Verb Conjugation** (ます/て/た/ない/可能)
- **Synonyms/Antonyms**
- **Reverse Cards** (Việt→Nhật)

## 🔧 Cài đặt

```bash
pip install -r requirements.txt --break-system-packages
```

## 🚀 Sử dụng

```bash
# Full mode (khuyên dùng)
python3 main.py sach.epub -o ./output

# Fast mode (không audio, không English)
python3 main.py sach.epub -o ./output --no-english --no-audio

# Verbose mode (xem chi tiết)
python3 main.py sach.epub -o ./output --verbose

# Force restart (xóa cache, chạy lại từ đầu)
python3 main.py sach.epub -o ./output --force-restart
```

## 📦 Import vào Anki

**Chỉ cần import file `.apkg`** - audio đã được đóng gói tự động!

```
File → Import → chọn output/japanese_vocabulary.apkg
```

## 🗂 Cấu trúc Output

```
output/
├── japanese_vocabulary.apkg   ← Import file này
├── audio/
│   ├── words/                 ← Cache audio từ vựng
│   └── examples/              ← Cache audio câu ví dụ
├── stroke_cache/              ← Cache stroke order SVG
└── checkpoint.json            ← Resume point
```

## 🗂 Data Files

```
data/
├── hanviet.json           # Kanji → Hán Việt
├── kanji_database.json    # Full kanji data (chiết tự, từ ghép...)
├── jlpt.json              # JLPT levels (N5-N1)
├── radicals.json          # 48 bộ thủ
├── pitch_accent.json      # Pitch patterns
├── example_sentences.json # Câu ví dụ offline
├── english_cache/         # Cache English meanings
├── pitch_cache/           # Cache pitch API
└── examples_cache/        # Cache examples API
```

## ⚙️ Options

| Flag              | Mô tả                                |
| ----------------- | ------------------------------------ |
| `--no-english`    | Bỏ lookup tiếng Anh                  |
| `--no-audio`      | Không generate audio                 |
| `--no-pitch`      | Không generate pitch diagram         |
| `--no-stroke`     | Không generate stroke order          |
| `--delay N`       | Delay API calls (giây, default: 0.5) |
| `--force-restart` | Xóa checkpoint, chạy lại             |
| `--verbose`       | Hiển thị chi tiết API calls          |
| `--offline`       | Chỉ dùng local data                  |

## 🔄 Caching

- Lần chạy đầu: Chậm (API calls)
- Lần chạy sau: Nhanh (từ cache)
- Cache chia sẻ giữa các EPUB
