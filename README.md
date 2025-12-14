# 📚 Japanese Vocabulary Anki Deck Generator

Công cụ tự động tạo Anki deck học từ vựng tiếng Nhật từ file EPUB.

## ✨ Tính năng

- **Parse EPUB** → Extract từ vựng tự động theo chapter
- **Sub-decks** → Mỗi chủ đề = 1 sub-deck riêng
- **Đa ngôn ngữ**: Tiếng Việt, Tiếng Anh, Hán Việt
- **Pitch Accent** → Biểu đồ SVG như Takoboto
- **Stroke Order** → Thứ tự nét viết từ KanjiVG
- **Audio TTS** → Google Text-to-Speech
- **Link từ điển** → Takoboto integration

## 📦 Cấu trúc Deck

```
Tiếng Nhật Theo Chủ Đề
├── Động vật
│   ├── Động vật có vú
│   ├── Con chim
│   └── ...
├── Thể thao
├── Địa lý
├── Cơ thể
├── Tính từ
├── Động từ
└── ... (22 chapters)
```

## 🔧 Cài đặt

```bash
# Clone hoặc download
cd japanese_anki

# Cài dependencies
pip install -r requirements.txt --break-system-packages
```

## 🚀 Sử dụng

### Quick Start

```bash
./run.sh <đường_dẫn_epub> [thư_mục_output]
```

### Manual

```bash
# Full mode (chậm, có audio + English)
python3 main.py sach.epub -o ./output

# Fast mode (nhanh, chỉ tiếng Việt)
python3 main.py sach.epub -o ./output --no-english --no-audio

# Xem help
python3 main.py --help
```

### Options

| Flag           | Mô tả                               |
| -------------- | ----------------------------------- |
| `--no-english` | Bỏ qua lookup tiếng Anh (nhanh hơn) |
| `--no-audio`   | Không generate audio                |
| `--no-pitch`   | Không generate pitch diagram        |
| `--no-stroke`  | Không generate stroke order         |
| `--delay N`    | Delay giữa API calls (giây)         |

## 📊 Output

```
output/
├── japanese_vocabulary.apkg  # File import vào Anki
├── audio/                    # Audio files
│   ├── a1b2c3d4.mp3
│   └── ...
└── cache/                    # Cached data
    └── kanjivg/
```

## 🎴 Card Format

### Front (Question)

```
┌─────────────────────┐
│        犬           │
│       いぬ          │
│        🔊           │
└─────────────────────┘
```

### Back (Answer)

```
┌─────────────────────┐
│        犬           │
│   いぬ (inu)        │
├─────────────────────┤
│ 🇻🇳 con chó         │
│ 🇬🇧 dog             │
│ 漢越: Khuyển        │
├─────────────────────┤
│   [Pitch Diagram]   │
│   い＼ぬ (2)         │
├─────────────────────┤
│  [Stroke Order]     │
├─────────────────────┤
│ Bộ thủ: 犬 (Khuyển) │
├─────────────────────┤
│   📖 Takoboto       │
└─────────────────────┘
```

## 🔌 APIs Used

| Source     | Data                             |
| ---------- | -------------------------------- |
| Jisho.org  | English meanings                 |
| KanjiVG    | Stroke order SVG                 |
| gTTS       | Audio synthesis                  |
| Offline DB | Pitch accent, Hán Việt, Radicals |

## 📝 Pitch Accent Legend

| Pattern | Name               | Example |
| ------- | ------------------ | ------- |
| 0       | 平板型 (Heiban)    | 水 みず |
| 1       | 頭高型 (Atamadaka) | 猫 ねこ |
| 2-n     | 中高型 (Nakadaka)  | 犬 いぬ |
| n       | 尾高型 (Odaka)     | 山 やま |

## 🗂 Files

```
japanese_anki/
├── main.py           # Main pipeline
├── pitch_accent.py   # Pitch accent module
├── stroke_order.py   # Stroke order module
├── requirements.txt  # Dependencies
├── run.sh           # Run script
└── README.md        # This file
```

## ⚠️ Notes

1. **API Rate Limiting**: Jisho có rate limit, dùng `--delay` để tránh bị block
2. **Audio Quality**: gTTS chất lượng 7/10, native speaker tốt hơn
3. **Pitch Data**: Database offline chưa đầy đủ, có thể thiếu một số từ
4. **Stroke Order**: Chỉ có cho single kanji, không có cho compound words

## 🔄 Mở rộng

### Thêm nguồn pitch accent

Edit `pitch_accent.py` → class `OfflinePitchDB.DATABASE`

### Thêm Hán Việt

Edit `main.py` → class `HanVietDB.HANVIET_MAP`

### Thêm bộ thủ

Edit `main.py` → class `RadicalDB.RADICALS`

## 📜 License

MIT - Sử dụng tự do

## 🙏 Credits

- [KanjiVG](https://kanjivg.tagaini.net/) - Stroke order data
- [Jisho.org](https://jisho.org/) - Dictionary API
- [genanki](https://github.com/kerrickstaley/genanki) - Anki deck generation
