#!/usr/bin/env python3
"""
Japanese Vocabulary Anki Deck Generator
========================================
Generates comprehensive Anki decks from EPUB vocabulary books with:
- Kanji, Kana, Romaji, Vietnamese, English meanings
- Hán Việt readings
- Pitch accent diagrams (SVG)
- Stroke order diagrams
- Audio (TTS)
- Example sentences
- Takoboto dictionary links

Author: Generated for Dong's Japanese learning project
"""

import os
import sys
import json
import hashlib
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Any
import re
import zipfile
import urllib.request
import urllib.parse
import time

# Third-party imports (install via pip)
try:
    import genanki
except ImportError:
    print("Installing genanki...")
    os.system("pip install genanki --break-system-packages")
    import genanki

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing beautifulsoup4...")
    os.system("pip install beautifulsoup4 --break-system-packages")
    from bs4 import BeautifulSoup

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip install requests --break-system-packages")
    import requests


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class VocabEntry:
    """Represents a single vocabulary entry"""

    word: str  # Kanji or Kana word
    reading: str  # Hiragana reading
    romaji: str  # Romaji
    meaning_vi: str  # Vietnamese meaning
    meaning_en: str = ""  # English meaning
    han_viet: str = ""  # Sino-Vietnamese reading
    pitch_pattern: str = ""  # Pitch accent pattern (e.g., "0", "1", "2")
    pitch_svg: str = ""  # SVG diagram for pitch
    stroke_order_svg: str = ""  # Stroke order diagram
    audio_file: str = ""  # Path to audio file
    example_sentences: List[str] = field(default_factory=list)
    radical_info: str = ""  # Bộ thủ information
    kanji_origin: str = ""  # Etymology/origin
    chapter: str = ""  # Source chapter
    sub_category: str = ""  # Sub-category within chapter
    takoboto_link: str = ""  # Takoboto dictionary link
    examples: str = ""  # Example sentences HTML
    # Kanji detail fields
    kanji_pinyin: str = ""  # Chinese pinyin
    kanji_kun: str = ""  # Kun-yomi
    kanji_on: str = ""  # On-yomi
    kanji_tu_ghep: str = ""  # Compound words HTML
    kanji_chi_tiet: str = ""  # Etymology explanation
    frequency_info: str = ""  # Frequency tier [S #8]
    # New fields
    jlpt_level: str = ""  # JLPT level (N5-N1)
    word_type: str = ""  # Part of speech (Noun, Verb, Adj, etc.)
    furigana: str = ""  # HTML ruby text
    conjugations: str = ""  # Verb conjugations HTML
    synonyms: str = ""  # Similar words
    antonyms: str = ""  # Opposite words

    def generate_takoboto_link(self):
        """Generate Takoboto dictionary link - web URL that opens app if installed"""
        encoded = urllib.parse.quote(self.word)
        # Simple web URL - Android will offer to open in Takoboto app if installed
        self.takoboto_link = f"https://takoboto.jp/?q={encoded}"
        return self.takoboto_link


# =============================================================================
# EPUB PARSER
# =============================================================================


class EPUBVocabParser:
    """Parse vocabulary from EPUB file"""

    def __init__(self, epub_path: str):
        self.epub_path = epub_path
        self.chapters = {}  # chapter_name -> list of VocabEntry

    def parse(self) -> Dict[str, List[VocabEntry]]:
        """Extract all vocabulary from EPUB"""
        with zipfile.ZipFile(self.epub_path, "r") as zf:
            # Find all chapter files
            chapter_files = sorted(
                [f for f in zf.namelist() if "chapter-" in f and f.endswith(".xhtml")],
                key=lambda x: int(re.search(r"chapter-(\d+)", x).group(1)),
            )

            for chapter_file in chapter_files:
                with zf.open(chapter_file) as f:
                    content = f.read().decode("utf-8")
                    self._parse_chapter(chapter_file, content)

        return self.chapters

    def _parse_chapter(self, filename: str, content: str):
        """Parse a single chapter"""
        soup = BeautifulSoup(content, "html.parser")

        # Get chapter title from h1
        h1 = soup.find("h1")
        chapter_name = h1.get_text().strip() if h1 else filename

        entries = []
        current_subcategory = ""

        # Find all h2 (subcategories) and vocabulary entries
        for element in soup.find_all(["h2", "div"]):
            if element.name == "h2":
                current_subcategory = element.get_text().strip()
            elif element.name == "div":
                classes = element.get("class") or []
                if "l_outer" in classes:
                    entry = self._parse_vocab_entry(
                        element, chapter_name, current_subcategory
                    )
                    if entry:
                        entries.append(entry)

        if entries:
            self.chapters[chapter_name] = entries

    def _parse_vocab_entry(
        self, div, chapter: str, subcategory: str
    ) -> Optional[VocabEntry]:
        """Parse a single vocabulary entry div"""
        try:
            # Vietnamese meaning
            trans_span = div.find("span", class_="top_trans")
            meaning_vi_raw = trans_span.get_text().strip() if trans_span else ""
            # Clean Vietnamese - remove any Japanese characters mixed in
            meaning_vi = self._clean_vietnamese(meaning_vi_raw)

            # Japanese word (Kanji or Kana)
            word_span = div.find("span", class_="top_word")
            word_raw = word_span.get_text().strip() if word_span else ""
            # Clean Japanese - only keep Japanese characters
            word = self._clean_japanese(word_raw)

            # Romaji reading
            post_span = div.find("span", class_="top_post")
            romaji_raw = post_span.get_text().strip() if post_span else ""
            # Remove parentheses and clean
            romaji = romaji_raw.strip("()").lower()
            romaji = "".join(c for c in romaji if c.isalpha() or c.isspace())

            if not word or not meaning_vi:
                return None

            entry = VocabEntry(
                word=word,
                reading=self._romaji_to_hiragana(romaji),
                romaji=romaji,
                meaning_vi=meaning_vi,
                chapter=chapter,
                sub_category=subcategory,
            )
            entry.generate_takoboto_link()

            return entry

        except Exception as e:
            print(f"Error parsing entry: {e}")
            return None

    def _clean_japanese(self, text: str) -> str:
        """Keep only Japanese characters (Hiragana, Katakana, Kanji)"""
        result = []
        for char in text:
            code = ord(char)
            # Hiragana: 3040-309F, Katakana: 30A0-30FF, Kanji: 4E00-9FFF, 々
            if (
                0x3040 <= code <= 0x309F  # Hiragana
                or 0x30A0 <= code <= 0x30FF  # Katakana
                or 0x4E00 <= code <= 0x9FFF  # Common Kanji
                or char == "々"
            ):  # Kanji repeat mark
                result.append(char)
        return "".join(result)

    def _clean_vietnamese(self, text: str) -> str:
        """Keep only Vietnamese/Latin characters, remove Japanese"""
        result = []
        for char in text:
            code = ord(char)
            # Skip Japanese characters
            if (
                0x3040 <= code <= 0x309F  # Hiragana
                or 0x30A0 <= code <= 0x30FF  # Katakana
                or 0x4E00 <= code <= 0x9FFF
            ):  # Kanji
                continue
            result.append(char)
        return "".join(result).strip()

    def _romaji_to_hiragana(self, romaji: str) -> str:
        """Convert romaji to hiragana (basic conversion)"""
        # This is a simplified conversion - for production, use a proper library
        romaji_map = {
            "a": "あ",
            "i": "い",
            "u": "う",
            "e": "え",
            "o": "お",
            "ka": "か",
            "ki": "き",
            "ku": "く",
            "ke": "け",
            "ko": "こ",
            "sa": "さ",
            "shi": "し",
            "su": "す",
            "se": "せ",
            "so": "そ",
            "ta": "た",
            "chi": "ち",
            "tsu": "つ",
            "te": "て",
            "to": "と",
            "na": "な",
            "ni": "に",
            "nu": "ぬ",
            "ne": "ね",
            "no": "の",
            "ha": "は",
            "hi": "ひ",
            "fu": "ふ",
            "he": "へ",
            "ho": "ほ",
            "ma": "ま",
            "mi": "み",
            "mu": "む",
            "me": "め",
            "mo": "も",
            "ya": "や",
            "yu": "ゆ",
            "yo": "よ",
            "ra": "ら",
            "ri": "り",
            "ru": "る",
            "re": "れ",
            "ro": "ろ",
            "wa": "わ",
            "wo": "を",
            "n": "ん",
            "ga": "が",
            "gi": "ぎ",
            "gu": "ぐ",
            "ge": "げ",
            "go": "ご",
            "za": "ざ",
            "ji": "じ",
            "zu": "ず",
            "ze": "ぜ",
            "zo": "ぞ",
            "da": "だ",
            "di": "ぢ",
            "du": "づ",
            "de": "で",
            "do": "ど",
            "ba": "ば",
            "bi": "び",
            "bu": "ぶ",
            "be": "べ",
            "bo": "ぼ",
            "pa": "ぱ",
            "pi": "ぴ",
            "pu": "ぷ",
            "pe": "ぺ",
            "po": "ぽ",
            "kya": "きゃ",
            "kyu": "きゅ",
            "kyo": "きょ",
            "sha": "しゃ",
            "shu": "しゅ",
            "sho": "しょ",
            "cha": "ちゃ",
            "chu": "ちゅ",
            "cho": "ちょ",
            "nya": "にゃ",
            "nyu": "にゅ",
            "nyo": "にょ",
            "hya": "ひゃ",
            "hyu": "ひゅ",
            "hyo": "ひょ",
            "mya": "みゃ",
            "myu": "みゅ",
            "myo": "みょ",
            "rya": "りゃ",
            "ryu": "りゅ",
            "ryo": "りょ",
            "gya": "ぎゃ",
            "gyu": "ぎゅ",
            "gyo": "ぎょ",
            "ja": "じゃ",
            "ju": "じゅ",
            "jo": "じょ",
            "bya": "びゃ",
            "byu": "びゅ",
            "byo": "びょ",
            "pya": "ぴゃ",
            "pyu": "ぴゅ",
            "pyo": "ぴょ",
            # Long vowels
            "ā": "ああ",
            "ī": "いい",
            "ū": "うう",
            "ē": "ええ",
            "ō": "おお",
        }

        result = romaji.lower()
        # Sort by length (longest first) to avoid partial replacements
        for r, h in sorted(romaji_map.items(), key=lambda x: -len(x[0])):
            result = result.replace(r, h)

        return result


# =============================================================================
# ENRICHMENT APIs
# =============================================================================


class JishoAPI:
    """Jisho.org API for English meanings and additional data"""

    BASE_URL = "https://jisho.org/api/v1/search/words"

    # Cache for full Jisho responses
    _jisho_cache_dir: Path = None
    _english_cache_dir: Path = None
    last_api_called: bool = False

    @classmethod
    def _init_cache(cls):
        if cls._english_cache_dir is None:
            cls._english_cache_dir = Path(__file__).parent / "data" / "english_cache"
            cls._english_cache_dir.mkdir(exist_ok=True)
        if cls._jisho_cache_dir is None:
            cls._jisho_cache_dir = Path(__file__).parent / "data" / "jisho_cache"
            cls._jisho_cache_dir.mkdir(exist_ok=True)

    @classmethod
    def _is_exact_match(cls, result: Dict, word: str) -> bool:
        """Check if Jisho result is an exact match for the word"""
        japanese = result.get("japanese", [])
        for jp in japanese:
            # Check word field
            if jp.get("word") == word:
                return True
            # Check reading field (for kana-only words)
            if jp.get("reading") == word:
                return True
        # Also check slug
        if result.get("slug") == word:
            return True
        return False

    @classmethod
    def lookup(cls, word: str, use_cache: bool = True) -> Dict:
        """Look up a word in Jisho with caching"""
        cls._init_cache()

        word_hash = hashlib.md5(word.encode()).hexdigest()[:12]
        cache_file = cls._jisho_cache_dir / f"{word_hash}.json"

        # Check cache
        if use_cache and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass

        # Fetch from API
        cls.last_api_called = True
        try:
            url = f"{cls.BASE_URL}?keyword={urllib.parse.quote(word)}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    # Find exact match first
                    for result in data["data"]:
                        if cls._is_exact_match(result, word):
                            # Cache result
                            try:
                                with open(cache_file, "w", encoding="utf-8") as f:
                                    json.dump(result, f, ensure_ascii=False)
                            except:
                                pass
                            return result

                    # No exact match found - cache empty result
                    # Don't return partial match as it causes wrong meanings!
                    try:
                        with open(cache_file, "w", encoding="utf-8") as f:
                            json.dump({}, f)
                    except:
                        pass
                    return {}
        except Exception as e:
            print(f"Jisho lookup error for {word}: {e}")

        # Cache empty result
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({}, f)
        except:
            pass
        return {}

    @classmethod
    def get_english_meaning(cls, word: str) -> str:
        """Get English meaning from Jisho with cache"""
        cls._init_cache()
        cls.last_api_called = False

        # Check old-style cache first (for backwards compatibility)
        word_hash = hashlib.md5(word.encode()).hexdigest()[:12]
        cache_file = cls._english_cache_dir / f"{word_hash}.txt"
        if cache_file.exists():
            cached = cache_file.read_text(encoding="utf-8")
            return "" if cached == "_EMPTY_" else cached

        # Get from full Jisho data
        data = cls.lookup(word)
        meaning = ""
        if data and "senses" in data:
            meanings = []
            for sense in data["senses"][:2]:  # First 2 senses
                if "english_definitions" in sense:
                    meanings.extend(sense["english_definitions"][:3])
            meaning = "; ".join(meanings)

        # Save to cache (including empty to avoid re-fetching)
        cache_file.write_text(meaning if meaning else "_EMPTY_", encoding="utf-8")

        return meaning

    @classmethod
    def get_reading(cls, word: str) -> str:
        """Get correct reading (furigana) from Jisho"""
        data = cls.lookup(word)
        if not data:
            return ""

        japanese = data.get("japanese", [])
        for jp in japanese:
            if jp.get("word") == word or jp.get("reading") == word:
                return jp.get("reading", "")

        if japanese and "reading" in japanese[0]:
            return japanese[0]["reading"]

        return ""

    @classmethod
    def get_word_type(cls, word: str) -> str:
        """Get part of speech from Jisho. Returns formatted string."""
        data = cls.lookup(word)
        if not data or "senses" not in data:
            return ""

        # Collect unique parts of speech
        pos_set = set()
        for sense in data.get("senses", [])[:2]:
            for pos in sense.get("parts_of_speech", []):
                pos_set.add(pos)

        if not pos_set:
            return ""

        # Translate common types to Vietnamese
        translations = {
            "Noun": "Danh từ",
            "Verb": "Động từ",
            "I-adjective": "Tính từ -い",
            "Na-adjective": "Tính từ -な",
            "Adverb": "Trạng từ",
            "Suru verb": "Động từ する",
            "Godan verb": "Động từ Godan",
            "Ichidan verb": "Động từ Ichidan",
            "Intransitive verb": "Tự động từ",
            "Transitive verb": "Tha động từ",
            "Expression": "Thành ngữ",
            "Particle": "Trợ từ",
            "Conjunction": "Liên từ",
            "Counter": "Trợ số từ",
            "Suffix": "Hậu tố",
            "Prefix": "Tiền tố",
        }

        result = []
        for pos in pos_set:
            # Try to translate, otherwise use original
            for en, vi in translations.items():
                if en.lower() in pos.lower():
                    result.append(vi)
                    break
            else:
                result.append(pos)

        return " • ".join(result[:3])  # Limit to 3

    @classmethod
    def get_synonyms_antonyms(cls, word: str) -> Tuple[str, str]:
        """Get synonyms and antonyms from Jisho with furigana. Returns (synonyms, antonyms)."""
        data = cls.lookup(word)
        if not data or "senses" not in data:
            return "", ""

        synonyms = []
        antonyms = []

        for sense in data.get("senses", []):
            # See also = similar words
            see_also = sense.get("see_also", [])
            synonyms.extend(see_also[:3])

            # Antonyms (less common in Jisho)
            ant = sense.get("antonyms", [])
            antonyms.extend(ant[:3])

        # Add furigana to each word
        syn_with_ruby = [SentenceFuriganaGenerator.generate(s) for s in synonyms[:4]]
        ant_with_ruby = [SentenceFuriganaGenerator.generate(a) for a in antonyms[:4]]

        return " • ".join(syn_with_ruby), " • ".join(ant_with_ruby)


class KanjiAPI:
    """KanjiAPI.dev for accurate kun/on readings"""

    BASE_URL = "https://kanjiapi.dev/v1/kanji"
    _cache_dir: Path = None
    last_api_called: bool = False

    @classmethod
    def _init_cache(cls):
        if cls._cache_dir is None:
            cls._cache_dir = Path(__file__).parent / "data" / "kanji_api_cache"
            cls._cache_dir.mkdir(exist_ok=True)

    @classmethod
    def lookup(cls, kanji: str, use_cache: bool = True) -> Dict:
        """Look up a single kanji character"""
        cls._init_cache()
        cls.last_api_called = False

        if len(kanji) != 1:
            return {}

        cache_file = cls._cache_dir / f"{ord(kanji)}.json"

        if use_cache and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass

        cls.last_api_called = True
        try:
            url = f"{cls.BASE_URL}/{urllib.parse.quote(kanji)}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                except:
                    pass
                return data
        except Exception as e:
            print(f"KanjiAPI error for {kanji}: {e}")

        return {}

    @classmethod
    def get_readings(cls, kanji: str) -> Tuple[List[str], List[str]]:
        """Get kun and on readings for a kanji"""
        data = cls.lookup(kanji)
        kun = data.get("kun_readings", [])
        on = data.get("on_readings", [])
        return kun, on


class PitchAccentAPI:
    """Fetch pitch accent data - loads from JSON with API fallback"""

    PITCH_DB: Dict[str, Tuple[str, List[str]]] = {}
    _loaded = False
    _cache_dir: Path = None
    last_api_called: bool = False

    @classmethod
    def _load(cls):
        """Load pitch data from JSON"""
        if cls._loaded:
            return

        cls._cache_dir = Path(__file__).parent / "data" / "pitch_cache"
        cls._cache_dir.mkdir(exist_ok=True)

        json_path = Path(__file__).parent / "data" / "pitch_accent.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.pop("_comment", None)
                # Convert: {"word": [["reading", pattern], ...]} -> {"word": (str(pattern), [morae])}
                for word, readings in data.items():
                    if readings:
                        reading, pattern = readings[0]  # Take first reading
                        morae = cls.split_morae(reading)
                        cls.PITCH_DB[word] = (str(pattern), morae)
        cls._loaded = True

    @classmethod
    def get_pitch_pattern(
        cls, word: str, reading: str, offline: bool = False
    ) -> Tuple[str, List[str]]:
        """Get pitch pattern for a word"""
        cls._load()
        cls.last_api_called = False

        # 1. Check local DB
        if word in cls.PITCH_DB:
            return cls.PITCH_DB[word]

        morae = cls.split_morae(reading)

        # 2. Check cache - use stable hash
        word_hash = hashlib.md5(word.encode()).hexdigest()[:12]
        cache_file = cls._cache_dir / f"{word_hash}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    return (str(cached.get("pattern", "?")), morae)
            except:
                pass

        # 3. Skip API if offline
        if offline:
            return ("?", morae)

        # 4. Fetch from Jisho API
        cls.last_api_called = True
        pattern = cls._fetch_from_jisho(word, reading)

        # 5. Save to cache (including '?' to avoid re-fetching)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"word": word, "reading": reading, "pattern": pattern}, f)
        except:
            pass

        return (pattern, morae)

    @classmethod
    def _fetch_from_jisho(cls, word: str, reading: str) -> str:
        """Fetch pitch from Jisho API (has partial pitch data)"""
        try:
            url = f"https://jisho.org/api/v1/search/words?keyword={urllib.parse.quote(word)}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("data", []):
                    japanese = item.get("japanese", [])
                    for jp in japanese:
                        if jp.get("word") == word or jp.get("reading") == reading:
                            # Jisho sometimes includes pitch in tags
                            tags = item.get("tags", [])
                            for tag in tags:
                                if "pitch" in tag.lower():
                                    # Extract number from tag
                                    nums = re.findall(r"\d+", tag)
                                    if nums:
                                        return nums[0]
        except:
            pass
        return "?"

    @staticmethod
    def split_morae(text: str) -> List[str]:
        """Split Japanese text into morae"""
        # Small kana that combine with previous
        small_kana = "ゃゅょャュョァィゥェォ"

        morae = []
        i = 0
        while i < len(text):
            if i + 1 < len(text) and text[i + 1] in small_kana:
                morae.append(text[i : i + 2])
                i += 2
            else:
                morae.append(text[i])
                i += 1
        return morae


class PitchDiagramGenerator:
    """Generate SVG pitch accent diagrams"""

    @staticmethod
    def generate_svg(reading: str, pattern: str, morae: List[str]) -> str:
        """
        Generate SVG pitch accent diagram similar to Takoboto/JapanDict

        Args:
            reading: Hiragana reading
            pattern: Pitch pattern number (0 = heiban, 1+ = accent position)
            morae: List of morae

        Returns:
            SVG string
        """
        if not morae:
            morae = PitchAccentAPI.split_morae(reading)

        num_morae = len(morae)
        if num_morae == 0:
            return ""

        # SVG dimensions
        mora_width = 30
        width = mora_width * num_morae + 40
        height = 80

        # Pitch levels
        high_y = 20
        low_y = 50
        text_y = 70

        # Determine pitch heights for each mora
        heights = []
        try:
            pattern_num = int(pattern) if pattern.isdigit() else -1
        except:
            pattern_num = -1

        if pattern_num == 0:
            # 平板型 (heiban): low-high-high-high...
            heights = [low_y] + [high_y] * (num_morae - 1)
        elif pattern_num == 1:
            # 頭高型 (atamadaka): high-low-low-low...
            heights = [high_y] + [low_y] * (num_morae - 1)
        elif pattern_num > 1:
            # 中高型 (nakadaka) or 尾高型 (odaka)
            heights = [low_y]  # First mora is low
            for i in range(1, num_morae):
                if i < pattern_num:
                    heights.append(high_y)
                else:
                    heights.append(low_y)
        else:
            # Unknown pattern - show flat
            heights = [high_y] * num_morae

        # Build SVG
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            "<style>",
            '  .mora-text { font-family: "Noto Sans JP", sans-serif; font-size: 16px; text-anchor: middle; }',
            "  .pitch-line { stroke: #e74c3c; stroke-width: 2; fill: none; }",
            "  .pitch-dot { fill: #e74c3c; }",
            "</style>",
        ]

        # Draw pitch line
        points = []
        for i, (mora, h) in enumerate(zip(morae, heights)):
            x = 20 + i * mora_width + mora_width // 2
            points.append(f"{x},{h}")

        if len(points) > 1:
            svg_parts.append(
                f'<polyline class="pitch-line" points="{" ".join(points)}" />'
            )

        # Draw dots and text
        for i, (mora, h) in enumerate(zip(morae, heights)):
            x = 20 + i * mora_width + mora_width // 2
            svg_parts.append(f'<circle class="pitch-dot" cx="{x}" cy="{h}" r="4" />')
            svg_parts.append(
                f'<text class="mora-text" x="{x}" y="{text_y}">{mora}</text>'
            )

        svg_parts.append("</svg>")

        return "\n".join(svg_parts)


class StrokeOrderAPI:
    """Generate stroke order diagrams using KanjiVG data"""

    KANJIVG_URL = (
        "https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{}.svg"
    )

    @staticmethod
    def get_stroke_order_svg(kanji: str) -> str:
        """Get stroke order SVG for a single kanji"""
        if len(kanji) != 1:
            return ""

        # Get unicode code point
        code = format(ord(kanji), "05x")
        url = StrokeOrderAPI.KANJIVG_URL.format(code)

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return StrokeOrderAPI._add_stroke_numbers(response.text)
        except Exception as e:
            print(f"Stroke order fetch error for {kanji}: {e}")

        return ""

    @staticmethod
    def _add_stroke_numbers(svg_content: str) -> str:
        """Clean and simplify SVG for Anki display with dark mode support"""
        import re

        # Remove XML declaration and comments
        svg_content = re.sub(r"<\?xml[^>]*\?>", "", svg_content)
        svg_content = re.sub(r"<!--.*?-->", "", svg_content, flags=re.DOTALL)

        # Remove problematic attributes and elements
        svg_content = re.sub(r'xmlns:kvg="[^"]*"', "", svg_content)
        svg_content = re.sub(r'kvg:[a-z]+="[^"]*"', "", svg_content)

        # CRITICAL: Remove inline fill and stroke attributes for dark mode support
        # This allows CSS to control the colors
        svg_content = re.sub(r'\s+fill="[^"]*"', "", svg_content)
        svg_content = re.sub(r'\s+stroke="[^"]*"', "", svg_content)

        # Keep only essential SVG content
        svg_match = re.search(r"(<svg[^>]*>.*</svg>)", svg_content, re.DOTALL)
        if svg_match:
            svg_content = svg_match.group(1)

        # Set viewBox and size - use class for theme support
        svg_content = re.sub(
            r"<svg([^>]*)>",
            '<svg viewBox="0 0 109 109" width="120" height="120" class="stroke-svg">',
            svg_content,
        )

        return svg_content.strip()


class TTSGenerator:
    """Generate audio using Microsoft Edge TTS (better Japanese pronunciation)"""

    # Japanese voice options:
    # ja-JP-NanamiNeural (female, natural)
    # ja-JP-KeitaNeural (male, natural)
    VOICE = "ja-JP-NanamiNeural"

    @staticmethod
    def generate_audio(text: str, output_path: str, lang: str = "ja") -> bool:
        """Generate TTS audio file using edge-tts"""
        try:
            import edge_tts
            import asyncio

            async def _generate():
                communicate = edge_tts.Communicate(text, TTSGenerator.VOICE)
                await communicate.save(output_path)

            asyncio.run(_generate())
            return True
        except ImportError:
            print("Installing edge-tts...")
            os.system("pip install edge-tts --break-system-packages")
            try:
                import edge_tts
                import asyncio

                async def _generate():
                    communicate = edge_tts.Communicate(text, TTSGenerator.VOICE)
                    await communicate.save(output_path)

                asyncio.run(_generate())
                return True
            except Exception as e:
                print(f"TTS error: {e}")
                return False
        except Exception as e:
            print(f"TTS error for {text}: {e}")
            return False
            return False


# =============================================================================
# HÁN VIỆT DATABASE
# =============================================================================


class HanVietDB:
    """Sino-Vietnamese reading database - loads from JSON"""

    HANVIET_MAP: Dict[str, str] = {}
    _loaded = False

    @classmethod
    def _load(cls):
        """Load data from JSON file"""
        if cls._loaded:
            return

        json_path = Path(__file__).parent / "data" / "hanviet.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Remove comment key
                data.pop("_comment", None)
                cls.HANVIET_MAP = data
        cls._loaded = True

    @staticmethod
    def get_hanviet(word: str) -> str:
        """Get Hán Việt reading for a word"""
        HanVietDB._load()
        result = []
        for char in word:
            if char in HanVietDB.HANVIET_MAP:
                result.append(HanVietDB.HANVIET_MAP[char])
        return " ".join(result) if result else ""


# =============================================================================
# 48 BỘ THỦ (RADICALS)
# =============================================================================


class RadicalDB:
    """214 Kangxi radicals database with jamdict integration"""

    RADICALS: List[Dict] = []
    RADICAL_BY_SYMBOL: Dict[str, Dict] = {}
    RADICAL_BY_VARIANT: Dict[str, Dict] = {}
    _jamdict = None
    _jamdict_cache: Dict[str, List[str]] = {}  # kanji -> [normalized components]
    _cache_path: Path = None
    _loaded = False

    @classmethod
    def _load(cls):
        """Load data from radicals.py and initialize jamdict"""
        if cls._loaded:
            return

        # Load Vietnamese meanings and importance data
        try:
            from data.radicals import RADICALS_DATA

            cls.RADICALS = RADICALS_DATA

            for rad in cls.RADICALS:
                cls.RADICAL_BY_SYMBOL[rad["symbol"]] = rad
                for var in rad["variants"]:
                    cls.RADICAL_BY_VARIANT[var] = rad
        except ImportError:
            # Fallback to old JSON if new file not available
            json_path = Path(__file__).parent / "data" / "radicals.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data.pop("_comment", None)
                    for symbol, info in data.items():
                        rad = {
                            "symbol": symbol,
                            "variants": info.get("variants", []),
                            "meaning_vn": info.get("name_vn", ""),
                            "meaning_en": info.get("name_en", ""),
                            "frequency": 50,
                            "joyo_freq": 0,
                        }
                        cls.RADICALS.append(rad)
                        cls.RADICAL_BY_SYMBOL[symbol] = rad
                        for var in rad["variants"]:
                            cls.RADICAL_BY_VARIANT[var] = rad

        # Load jamdict cache
        cls._cache_path = Path(__file__).parent / "data" / "jamdict_cache.json"
        if cls._cache_path.exists():
            try:
                with open(cls._cache_path, "r", encoding="utf-8") as f:
                    cls._jamdict_cache = json.load(f)
            except:
                cls._jamdict_cache = {}

        # Initialize jamdict for accurate radical lookup
        try:
            from jamdict import Jamdict

            cls._jamdict = Jamdict()
        except ImportError:
            print("Warning: jamdict not installed, using fallback radical detection")
            cls._jamdict = None

        cls._loaded = True

    @classmethod
    def _save_cache(cls):
        """Save jamdict cache to disk"""
        if cls._cache_path and cls._jamdict_cache:
            try:
                with open(cls._cache_path, "w", encoding="utf-8") as f:
                    json.dump(cls._jamdict_cache, f, ensure_ascii=False, indent=2)
            except:
                pass

    @classmethod
    def _get_components(cls, kanji: str) -> List[str]:
        """Get normalized components for a kanji (cached)"""
        cls._load()

        # Check cache first
        if kanji in cls._jamdict_cache:
            return cls._jamdict_cache[kanji]

        # Query jamdict
        components = []
        if cls._jamdict:
            try:
                result = cls._jamdict.lookup(kanji)
                if result.chars:
                    raw_comps = result.chars[0].components or []
                    components = [unicodedata.normalize("NFKC", c) for c in raw_comps]
                    # Cache it
                    cls._jamdict_cache[kanji] = components
            except:
                pass

        return components

    @classmethod
    def get_importance_label(cls, frequency: int, joyo_freq: int) -> str:
        """Determine importance based on frequency data"""
        if joyo_freq and joyo_freq > 0:
            return "⭐ Thiết yếu"
        elif frequency >= 500:
            return "🔥 Rất phổ biến"
        elif frequency >= 200:
            return "📌 Phổ biến"
        elif frequency >= 50:
            return "📖 Thường gặp"
        else:
            return "📝 Ít gặp"

    @classmethod
    def identify_radical(cls, kanji: str) -> Dict:
        """Identify the main radical of a kanji using jamdict"""
        cls._load()

        # First check if kanji itself is a radical
        if kanji in cls.RADICAL_BY_SYMBOL:
            rad = cls.RADICAL_BY_SYMBOL[kanji]
            return {"radical": kanji, **rad}

        # Use jamdict for accurate radical lookup
        if cls._jamdict:
            try:
                result = cls._jamdict.lookup(kanji)
                if result.chars:
                    char_info = result.chars[0]

                    # Parse radical string like "水-water[sc:4]"
                    rad_str = str(char_info.radical) if char_info.radical else ""
                    if rad_str and "-" in rad_str:
                        jamdict_radical = rad_str.split("-")[0]  # e.g., "水", "辵"
                        # Normalize components using NFKC (fixes CJK Compatibility chars)
                        raw_components = char_info.components or []
                        components = [
                            unicodedata.normalize("NFKC", c) for c in raw_components
                        ]

                        # Step 1: Find our database entry for this radical
                        db_radical = None
                        db_rad_info = None

                        # Check if jamdict_radical is directly in our symbols
                        if jamdict_radical in cls.RADICAL_BY_SYMBOL:
                            db_radical = jamdict_radical
                            db_rad_info = cls.RADICAL_BY_SYMBOL[jamdict_radical]
                        # Or if jamdict_radical is one of our variants (e.g., 辵 -> ⻌)
                        elif jamdict_radical in cls.RADICAL_BY_VARIANT:
                            db_rad_info = cls.RADICAL_BY_VARIANT[jamdict_radical]
                            db_radical = db_rad_info["symbol"]

                        if db_rad_info:
                            # Step 2: Find which form is actually used in the kanji
                            # Prioritize variant if found (e.g., 氵 over 水)
                            variant_used = None
                            for var in db_rad_info.get("variants", []):
                                if var in components:
                                    variant_used = var
                                    break

                            result_dict = {"radical": db_radical, **db_rad_info}
                            if variant_used:
                                result_dict["found_as"] = variant_used
                            return result_dict
            except Exception as e:
                pass  # Fall through to fallback

        # Fallback: check if any radical/variant is substring
        for variant, rad in cls.RADICAL_BY_VARIANT.items():
            if variant in kanji:
                return {"radical": rad["symbol"], "found_as": variant, **rad}

        for symbol, rad in cls.RADICAL_BY_SYMBOL.items():
            if symbol in kanji and symbol != kanji:
                return {"radical": symbol, **rad}

        return {}

    @classmethod
    def identify_all_radicals(cls, kanji: str) -> List[Dict]:
        """Identify ALL component radicals of a kanji (not just main radical)"""
        cls._load()

        results = []
        seen_symbols = set()

        # If kanji itself is a radical
        if kanji in cls.RADICAL_BY_SYMBOL:
            rad = cls.RADICAL_BY_SYMBOL[kanji]
            return [{"radical": kanji, **rad}]

        # Get components (cached)
        components = cls._get_components(kanji)

        if components:
            # Check each component against our radical database
            for comp in components:
                # Check if component is a radical symbol
                if comp in cls.RADICAL_BY_SYMBOL:
                    rad = cls.RADICAL_BY_SYMBOL[comp]
                    if rad["symbol"] not in seen_symbols:
                        seen_symbols.add(rad["symbol"])
                        results.append({"radical": comp, **rad})
                # Check if component is a variant
                elif comp in cls.RADICAL_BY_VARIANT:
                    rad = cls.RADICAL_BY_VARIANT[comp]
                    if rad["symbol"] not in seen_symbols:
                        seen_symbols.add(rad["symbol"])
                        results.append(
                            {"radical": rad["symbol"], "found_as": comp, **rad}
                        )

            if results:
                return results

        # Fallback to main radical only
        main_rad = cls.identify_radical(kanji)
        if main_rad:
            return [main_rad]
        return []


class KanjiFrequencyDB:
    """Kanji frequency database - loads from JSON"""

    FREQ: Dict[str, Dict] = {}
    _loaded = False

    @classmethod
    def _load(cls):
        if cls._loaded:
            return

        json_path = Path(__file__).parent / "data" / "kanji_frequency.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                cls.FREQ = json.load(f)
        cls._loaded = True

    @classmethod
    def get_frequency(cls, kanji: str) -> Dict:
        """Get frequency info for a kanji. Returns {'rank': int, 'tier': str}"""
        cls._load()
        return cls.FREQ.get(kanji, {})

    @classmethod
    def get_word_frequency(cls, word: str) -> Dict:
        """Get frequency info for first kanji in word with frequency data"""
        cls._load()
        for char in word:
            if char in cls.FREQ:
                return {**cls.FREQ[char], "kanji": char}
        return {}


# =============================================================================
# JLPT LEVEL DATABASE
# =============================================================================


class JLPTDB:
    """JLPT level database - O(1) lookup"""

    LEVELS: Dict[str, str] = {}
    _loaded = False

    @classmethod
    def _load(cls):
        if cls._loaded:
            return

        json_path = Path(__file__).parent / "data" / "jlpt.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                cls.LEVELS = json.load(f)
        cls._loaded = True

    @classmethod
    def get_level(cls, word: str) -> str:
        """Get JLPT level for a word. Returns 'N5'-'N1' or ''"""
        cls._load()
        return cls.LEVELS.get(word, "")


# =============================================================================
# FURIGANA GENERATOR
# =============================================================================


class FuriganaGenerator:
    """Generate HTML ruby text for furigana display - O(n)"""

    _kakasi = None

    @classmethod
    def _init_kakasi(cls):
        """Initialize pykakasi (lazy loading)"""
        if cls._kakasi is None:
            try:
                import pykakasi

                cls._kakasi = pykakasi.kakasi()
            except ImportError:
                cls._kakasi = False

    @staticmethod
    def _is_kanji(c: str) -> bool:
        return "\u4e00" <= c <= "\u9fff"

    @staticmethod
    def _is_hiragana(c: str) -> bool:
        return "\u3040" <= c <= "\u309f"

    @staticmethod
    def _is_katakana(c: str) -> bool:
        return "\u30a0" <= c <= "\u30ff"

    @classmethod
    def _get_full_reading(cls, word: str) -> str:
        """Get full hiragana reading for a word using pykakasi"""
        cls._init_kakasi()
        if cls._kakasi is False:
            return ""

        try:
            result = cls._kakasi.convert(word)
            return "".join(item["hira"] for item in result)
        except:
            return ""

    @classmethod
    def _katakana_to_hiragana(cls, text: str) -> str:
        """Convert katakana to hiragana for comparison"""
        result = []
        for c in text:
            if cls._is_katakana(c):
                # Katakana to hiragana: subtract 0x60
                result.append(chr(ord(c) - 0x60))
            else:
                result.append(c)
        return "".join(result)

    @classmethod
    def _validate_reading(cls, word: str, reading: str) -> str:
        """Validate and fix reading if it doesn't match word properly.

        Problems this fixes:
        - あなたの猫 with reading あなた → should be あなたのねこ
        - スポーツ用品店 with reading スポーツ → should be スポーツようひんてん

        Does NOT override:
        - 髭剃り器 with reading ひげそりき (even if pykakasi says うつわ)
        """
        if not word or not reading:
            return reading

        # Count kana in word
        word_kanji = sum(1 for c in word if cls._is_kanji(c))
        word_kana = sum(1 for c in word if cls._is_hiragana(c) or cls._is_katakana(c))

        # If no kanji, no need to validate
        if word_kanji == 0:
            return reading

        # Normalize reading for comparison
        reading_normalized = cls._katakana_to_hiragana(reading)

        # Check if kana parts of word are present in reading
        # This indicates the reading is probably correct
        word_kana_parts = "".join(c for c in word if cls._is_hiragana(c))
        word_kana_parts_hira = cls._katakana_to_hiragana(
            "".join(c for c in word if cls._is_hiragana(c) or cls._is_katakana(c))
        )

        # If all kana parts from word are in reading, it's likely correct
        if word_kana_parts and word_kana_parts in reading_normalized:
            return reading

        # Expected reading length: at least 1 char per kanji + word's kana
        min_expected_len = word_kanji + word_kana

        # If reading is too short, it's likely incomplete
        if len(reading_normalized) < min_expected_len:
            # Get full reading using pykakasi
            full_reading = cls._get_full_reading(word)

            if full_reading and len(full_reading) > len(reading_normalized):
                # Reading is incomplete - use full reading
                # Try to preserve original katakana if present in word
                kata_prefix = ""
                for c in word:
                    if cls._is_katakana(c) or c == "ー":
                        kata_prefix += c
                    else:
                        break

                if kata_prefix:
                    # Replace hiragana prefix with original katakana
                    kata_len = len(kata_prefix)
                    return kata_prefix + full_reading[kata_len:]

                return full_reading

        return reading

    @classmethod
    def generate(cls, word: str, reading: str) -> str:
        """Generate furigana HTML. Returns <ruby>漢字<rt>かんじ</rt></ruby>

        Handles mixed kanji/hiragana/katakana like:
        - 閉める → <ruby>閉<rt>し</rt></ruby>める
        - 彼女のドレス → <ruby>彼女<rt>かのじょ</rt></ruby>のドレス
        """
        # If word is all hiragana/katakana, no furigana needed
        has_kanji = any(cls._is_kanji(c) for c in word)
        if not has_kanji:
            return word

        # Validate and fix reading if needed
        reading = cls._validate_reading(word, reading)

        # If reading equals word (already kana), no furigana needed
        if word == reading:
            return word

        # If reading is empty after validation, try to get it
        if not reading:
            reading = cls._get_full_reading(word)
            if not reading:
                return word

        # Segment word into blocks: kanji vs kana (hiragana/katakana)
        segments = []  # List of (text, is_kanji)
        current = ""
        current_is_kanji = None

        for c in word:
            is_kanji = cls._is_kanji(c)
            if current_is_kanji is None:
                current_is_kanji = is_kanji

            if is_kanji == current_is_kanji:
                current += c
            else:
                if current:
                    segments.append((current, current_is_kanji))
                current = c
                current_is_kanji = is_kanji

        if current:
            segments.append((current, current_is_kanji))

        # If only one segment and it's all kanji, simple wrap
        if len(segments) == 1 and segments[0][1]:
            return f"<ruby>{word}<rt>{reading}</rt></ruby>"

        # Try to match kana segments in reading to extract kanji readings
        # Convert reading to hiragana for matching
        reading_hira = cls._katakana_to_hiragana(reading)

        # Build result by matching segments
        result = ""
        reading_pos = 0

        for i, (seg_text, is_kanji) in enumerate(segments):
            if not is_kanji:
                # This is a kana segment - find it in reading
                seg_hira = cls._katakana_to_hiragana(seg_text)

                # Find this kana in reading starting from current position
                match_pos = reading_hira.find(seg_hira, reading_pos)

                if match_pos != -1:
                    # Extract kanji reading before this kana segment
                    if match_pos > reading_pos:
                        # There's kanji reading between current pos and match
                        kanji_reading = reading[reading_pos:match_pos]

                        # Find the kanji segment(s) before this kana
                        # Look back for kanji segments that need this reading
                        kanji_segments = []
                        for j in range(i - 1, -1, -1):
                            if segments[j][1]:  # is kanji
                                kanji_segments.insert(0, segments[j][0])
                            else:
                                break

                        if kanji_segments and kanji_reading:
                            kanji_text = "".join(kanji_segments)
                            # Remove already added kanji from result and re-add with ruby
                            result = (
                                result[: -len(kanji_text)]
                                if result.endswith(kanji_text)
                                else result
                            )
                            result += (
                                f"<ruby>{kanji_text}<rt>{kanji_reading}</rt></ruby>"
                            )

                    # Add the kana segment as-is
                    result += seg_text
                    reading_pos = match_pos + len(seg_hira)
                else:
                    # Couldn't find match, just add segment
                    result += seg_text
            else:
                # Kanji segment - will be processed when we hit next kana segment
                result += seg_text

        # Handle trailing kanji (no kana after it)
        if segments and segments[-1][1]:  # Last segment is kanji
            # Find remaining reading
            if reading_pos < len(reading):
                kanji_reading = reading[reading_pos:]
                kanji_text = segments[-1][0]
                # Remove the trailing kanji we added and re-add with ruby
                if result.endswith(kanji_text):
                    result = result[: -len(kanji_text)]
                    result += f"<ruby>{kanji_text}<rt>{kanji_reading}</rt></ruby>"

        # Fallback: if result looks wrong, use simple wrap
        if not result or result == word:
            return f"<ruby>{word}<rt>{reading}</rt></ruby>"

        return result

    @classmethod
    def generate_per_char(cls, word: str, reading: str) -> str:
        """Try to generate per-character furigana (best effort)"""
        has_kanji = any(cls._is_kanji(c) for c in word)
        if not has_kanji:
            return word

        # If single kanji, simple wrap
        if len(word) == 1:
            return f"<ruby>{word}<rt>{reading}</rt></ruby>"

        # Use smart generate for mixed words
        return cls.generate(word, reading)


class SentenceFuriganaGenerator:
    """Generate furigana for Japanese sentences using pykakasi"""

    _kakasi = None

    @classmethod
    def _init_kakasi(cls):
        """Initialize pykakasi (lazy loading)"""
        if cls._kakasi is None:
            try:
                import pykakasi

                cls._kakasi = pykakasi.kakasi()
            except ImportError:
                print(
                    "Warning: pykakasi not installed. Run: pip install pykakasi --break-system-packages"
                )
                cls._kakasi = False

    @classmethod
    def generate(cls, sentence: str) -> str:
        """Generate furigana HTML for a sentence"""
        cls._init_kakasi()

        if cls._kakasi is False or not sentence:
            return sentence

        try:
            result = cls._kakasi.convert(sentence)
            html_parts = []

            for item in result:
                orig = item["orig"]
                hira = item["hira"]

                # Check if has kanji
                has_kanji = any("\u4e00" <= c <= "\u9fff" for c in orig)

                if has_kanji and orig != hira:
                    html_parts.append(f"<ruby>{orig}<rt>{hira}</rt></ruby>")
                else:
                    html_parts.append(orig)

            return "".join(html_parts)
        except Exception as e:
            # Fallback to original sentence
            return sentence


# =============================================================================
# VERB CONJUGATION
# =============================================================================


class VerbConjugator:
    """Japanese verb conjugation - O(1) pattern matching"""

    # Godan verb endings and their conjugations
    GODAN_ENDINGS = {
        "う": {
            "masu": "います",
            "te": "って",
            "ta": "った",
            "nai": "わない",
            "potential": "える",
        },
        "く": {
            "masu": "きます",
            "te": "いて",
            "ta": "いた",
            "nai": "かない",
            "potential": "ける",
        },
        "ぐ": {
            "masu": "ぎます",
            "te": "いで",
            "ta": "いだ",
            "nai": "がない",
            "potential": "げる",
        },
        "す": {
            "masu": "します",
            "te": "して",
            "ta": "した",
            "nai": "さない",
            "potential": "せる",
        },
        "つ": {
            "masu": "ちます",
            "te": "って",
            "ta": "った",
            "nai": "たない",
            "potential": "てる",
        },
        "ぬ": {
            "masu": "にます",
            "te": "んで",
            "ta": "んだ",
            "nai": "なない",
            "potential": "ねる",
        },
        "ぶ": {
            "masu": "びます",
            "te": "んで",
            "ta": "んだ",
            "nai": "ばない",
            "potential": "べる",
        },
        "む": {
            "masu": "みます",
            "te": "んで",
            "ta": "んだ",
            "nai": "まない",
            "potential": "める",
        },
        "る": {
            "masu": "ります",
            "te": "って",
            "ta": "った",
            "nai": "らない",
            "potential": "れる",
        },
    }

    # Irregular verbs
    IRREGULARS = {
        "する": {
            "masu": "します",
            "te": "して",
            "ta": "した",
            "nai": "しない",
            "potential": "できる",
            "type": "suru",
        },
        "来る": {
            "masu": "来ます",
            "te": "来て",
            "ta": "来た",
            "nai": "来ない",
            "potential": "来られる",
            "type": "kuru",
        },
        "くる": {
            "masu": "きます",
            "te": "きて",
            "ta": "きた",
            "nai": "こない",
            "potential": "こられる",
            "type": "kuru",
        },
        "行く": {
            "masu": "行きます",
            "te": "行って",
            "ta": "行った",
            "nai": "行かない",
            "potential": "行ける",
            "type": "iku",
        },
        "いく": {
            "masu": "いきます",
            "te": "いって",
            "ta": "いった",
            "nai": "いかない",
            "potential": "いける",
            "type": "iku",
        },
        "ある": {
            "masu": "あります",
            "te": "あって",
            "ta": "あった",
            "nai": "ない",
            "potential": "ありえる",
            "type": "aru",
        },
    }

    # Common ichidan (る) verbs that end in える/いる
    ICHIDAN_COMMON = {
        "食べる",
        "見る",
        "起きる",
        "寝る",
        "着る",
        "出る",
        "開ける",
        "閉める",
        "教える",
        "考える",
        "答える",
        "忘れる",
        "覚える",
        "始める",
        "終わる",
        "たべる",
        "みる",
        "おきる",
        "ねる",
        "きる",
        "でる",
        "あける",
        "しめる",
    }

    @classmethod
    def detect_verb_type(cls, word: str, word_type: str = "") -> str:
        """Detect verb type: ichidan, godan, irregular, or not_verb"""
        # Check if it's marked as a verb (English, Japanese, or Vietnamese)
        verb_markers = ["Verb", "動詞", "Động từ", "verb"]
        if word_type and not any(m in word_type for m in verb_markers):
            return "not_verb"

        # Check irregulars first
        if word in cls.IRREGULARS:
            return cls.IRREGULARS[word].get("type", "irregular")

        # Check if ends with する (suru compound)
        if word.endswith("する"):
            return "suru"

        # Detect from word_type string
        ichidan_markers = ["Ichidan", "ichidan", "一段"]
        godan_markers = ["Godan", "godan", "五段"]

        if word_type:
            if any(m in word_type for m in ichidan_markers):
                return "ichidan"
            if any(m in word_type for m in godan_markers):
                return "godan"

        # Check common ichidan verbs
        if word in cls.ICHIDAN_COMMON:
            return "ichidan"

        # Check ending
        if not word:
            return "not_verb"

        last_char = word[-1]

        # Ichidan verbs end in る with え-row or い-row vowel before
        if last_char == "る" and len(word) >= 2:
            prev_char = word[-2]
            # え-row: え, け, せ, て, ね, へ, め, れ, げ, ぜ, で, べ, ぺ
            e_row = "えけせてねへめれげぜでべぺ"
            # い-row: い, き, し, ち, に, ひ, み, り, ぎ, じ, ぢ, び, ぴ
            i_row = "いきしちにひみりぎじぢびぴ"
            if prev_char in e_row or prev_char in i_row:
                # Could be ichidan - but many are actually godan
                # Default to ichidan for common patterns
                return "ichidan"

        # Godan verbs end in う-row
        if last_char in cls.GODAN_ENDINGS:
            return "godan"

        return "not_verb"

    @classmethod
    def conjugate(
        cls, word: str, reading: str = "", word_type: str = ""
    ) -> Dict[str, str]:
        """Conjugate a verb. Returns dict with masu, te, ta, nai, potential forms"""
        verb_type = cls.detect_verb_type(word, word_type)

        if verb_type == "not_verb":
            return {}

        # Handle irregulars
        if word in cls.IRREGULARS:
            return {k: v for k, v in cls.IRREGULARS[word].items() if k != "type"}

        # Handle する compounds
        if verb_type == "suru" and word.endswith("する"):
            stem = word[:-2]
            return {
                "masu": f"{stem}します",
                "te": f"{stem}して",
                "ta": f"{stem}した",
                "nai": f"{stem}しない",
                "potential": f"{stem}できる",
            }

        if not word:
            return {}

        last_char = word[-1]
        stem = word[:-1]

        # Ichidan verbs - just drop る and add endings
        if verb_type == "ichidan":
            return {
                "masu": f"{stem}ます",
                "te": f"{stem}て",
                "ta": f"{stem}た",
                "nai": f"{stem}ない",
                "potential": f"{stem}られる",
            }

        # Godan verbs
        if verb_type == "godan" and last_char in cls.GODAN_ENDINGS:
            endings = cls.GODAN_ENDINGS[last_char]
            return {
                "masu": f"{stem}{endings['masu']}",
                "te": f"{stem}{endings['te']}",
                "ta": f"{stem}{endings['ta']}",
                "nai": f"{stem}{endings['nai']}",
                "potential": f"{stem}{endings['potential']}",
            }

        return {}

    @classmethod
    def format_conjugations(
        cls, word: str, reading: str = "", word_type: str = ""
    ) -> str:
        """Format conjugations as HTML string with furigana"""
        conj = cls.conjugate(word, reading, word_type)
        if not conj:
            return ""

        parts = []
        labels = {
            "masu": "Lịch sự",
            "te": "Thể て",
            "ta": "Quá khứ",
            "nai": "Phủ định",
            "potential": "Khả năng",
        }
        for key in ["masu", "te", "ta", "nai", "potential"]:
            if key in conj:
                # Add furigana to conjugated form
                conj_with_ruby = SentenceFuriganaGenerator.generate(conj[key])
                parts.append(f"{labels[key]}: {conj_with_ruby}")
        return " | ".join(parts)


class ExampleSentencesDB:
    """Example sentences database - loads from JSON with API fallback"""

    SENTENCES: Dict[str, List[List[str]]] = {}
    _loaded = False
    _cache_dir: Path = None
    last_api_called: bool = False

    @classmethod
    def _load(cls):
        """Load sentences from JSON"""
        if cls._loaded:
            return

        cls._cache_dir = Path(__file__).parent / "data" / "examples_cache"
        cls._cache_dir.mkdir(exist_ok=True)

        json_path = Path(__file__).parent / "data" / "example_sentences.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.pop("_comment", None)
                cls.SENTENCES = data
        cls._loaded = True

    @classmethod
    def get_examples(
        cls, word: str, limit: int = 2, offline: bool = False
    ) -> List[str]:
        """Get example sentences for a word"""
        cls._load()
        cls.last_api_called = False

        # Build search variations
        search_words = [word]

        # For suru verbs: 失敗する → also try 失敗
        if word.endswith("する"):
            search_words.append(word[:-2])
        elif word.endswith("す"):
            search_words.append(word[:-1])

        # For Katakana words: add hiragana version
        # コンピューター → こんぴゅーたー
        if cls._is_katakana_word(word):
            hiragana = cls._katakana_to_hiragana(word)
            if hiragana and hiragana != word:
                search_words.append(hiragana)

        for search_word in search_words:
            if search_word in cls.SENTENCES:
                examples = cls.SENTENCES[search_word][:limit]
                return [f"{jp} → {vi}" for jp, vi in examples]

        # Check cache - use stable hash
        word_hash = hashlib.md5(word.encode()).hexdigest()[:12]
        cache_file = cls._cache_dir / f"{word_hash}.json"
        if cache_file and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if cached:  # Only return if not empty
                        return cached[:limit]
            except:
                pass

        # Skip API if offline
        if offline:
            return []

        # Fetch from APIs - try each variation
        cls.last_api_called = True
        examples = []

        for search_word in search_words:
            # Try Tatoeba first
            examples = cls._fetch_tatoeba(search_word, limit)
            if examples:
                break

            # Try Jisho sentences as fallback
            examples = cls._fetch_jisho_sentences(search_word, limit)
            if examples:
                break

        # Save to cache (including empty to avoid re-fetching)
        if cache_file:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(examples, f, ensure_ascii=False)
            except:
                pass

        return examples

    @staticmethod
    def _is_katakana_word(word: str) -> bool:
        """Check if word is primarily Katakana"""
        if not word:
            return False
        katakana_count = sum(1 for c in word if "\u30a1" <= c <= "\u30f6" or c == "ー")
        return katakana_count > len(word) * 0.5

    @staticmethod
    def _katakana_to_hiragana(text: str) -> str:
        """Convert Katakana to Hiragana"""
        result = []
        for c in text:
            # Standard Katakana (ァ-ヶ): U+30A1 to U+30F6
            if "\u30a1" <= c <= "\u30f6":
                # Katakana to Hiragana: subtract 0x60
                result.append(chr(ord(c) - 0x60))
            elif c == "ー":
                # Long vowel mark - keep as is or use hiragana equivalent
                result.append("ー")
            else:
                result.append(c)
        return "".join(result)

    @classmethod
    def _fetch_tatoeba(cls, word: str, limit: int = 2) -> List[str]:
        """Fetch examples from Tatoeba API"""
        try:
            # Try Vietnamese first
            url = f"https://tatoeba.org/en/api_v0/search?from=jpn&to=vie&query={urllib.parse.quote(word)}&limit={limit}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get("results", [])[:limit]:
                    jp = item.get("text", "")
                    translations = item.get("translations", [[]])
                    if translations and translations[0]:
                        vi = translations[0][0].get("text", "")
                        if jp and vi:
                            results.append(f"{jp} → {vi}")
                if results:
                    return results

            # Fallback to English if no Vietnamese
            url = f"https://tatoeba.org/en/api_v0/search?from=jpn&to=eng&query={urllib.parse.quote(word)}&limit={limit}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get("results", [])[:limit]:
                    jp = item.get("text", "")
                    translations = item.get("translations", [[]])
                    if translations and translations[0]:
                        en = translations[0][0].get("text", "")
                        if jp and en:
                            results.append(f"{jp} → {en}")
                return results
        except:
            pass
        return []

    @classmethod
    def _fetch_jisho_sentences(cls, word: str, limit: int = 2) -> List[str]:
        """Fetch example sentences from Jisho.org by scraping"""
        try:
            url = f"https://jisho.org/search/{urllib.parse.quote(word)}%20%23sentences"
            headers = {"User-Agent": "Mozilla/5.0 (compatible; AnkiDeckGenerator/1.0)"}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                results = []
                html = response.text

                # Simple regex extraction for sentence pairs
                # Jisho format: Japanese sentence followed by English translation
                import re

                # Find sentence blocks
                sentence_pattern = r'class="sentence_content"[^>]*>.*?<span class="text">([^<]+)</span>.*?<span class="english">([^<]+)</span>'
                matches = re.findall(sentence_pattern, html, re.DOTALL)

                for jp, en in matches[:limit]:
                    jp = jp.strip()
                    en = en.strip()
                    if jp and en:
                        results.append(f"{jp} → {en}")

                # Alternative pattern if above doesn't work
                if not results:
                    # Look for Japanese text followed by English
                    jp_pattern = r'<span class="japanese[^"]*"[^>]*>(.*?)</span>'
                    en_pattern = r'<span class="english">(.*?)</span>'

                    jp_matches = re.findall(jp_pattern, html)
                    en_matches = re.findall(en_pattern, html)

                    for jp, en in zip(jp_matches[:limit], en_matches[:limit]):
                        # Clean HTML tags
                        jp = re.sub(r"<[^>]+>", "", jp).strip()
                        en = re.sub(r"<[^>]+>", "", en).strip()
                        if jp and en:
                            results.append(f"{jp} → {en}")

                return results
        except:
            pass
        return []


class KanjiDB:
    """Full kanji database with chiết tự - loads from JSON"""

    DATABASE: Dict[str, Dict] = {}
    _loaded = False

    @classmethod
    def _load(cls):
        """Load kanji database from JSON"""
        if cls._loaded:
            return

        json_path = Path(__file__).parent / "data" / "kanji_database.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                cls.DATABASE = json.load(f)
        cls._loaded = True

    @classmethod
    def get_kanji_info(cls, kanji: str) -> Dict:
        """Get full info for a single kanji"""
        cls._load()
        return cls.DATABASE.get(kanji, {})

    @classmethod
    def get_word_info(cls, word: str) -> Dict:
        """Get combined info for all kanji in a word"""
        cls._load()

        result = {
            "han_viet": [],
            "pinyin": [],
            "kun": [],
            "on": [],
            "tu_ghep": [],
            "chi_tiet": [],
        }

        for char in word:
            info = cls.DATABASE.get(char, {})
            if info:
                if info.get("han_viet"):
                    result["han_viet"].append(f"{char}({info['han_viet']})")
                if info.get("pinyin"):
                    result["pinyin"].append(info["pinyin"])
                if info.get("kun"):
                    result["kun"].append(info["kun"])
                if info.get("on"):
                    result["on"].append(info["on"])
                if info.get("tu_ghep"):
                    result["tu_ghep"].extend(info["tu_ghep"][:2])
                if info.get("chi_tiet"):
                    result["chi_tiet"].append(f"【{char}】{info['chi_tiet']}")

        return result


# =============================================================================
# ANKI DECK GENERATOR
# =============================================================================


class AnkiDeckGenerator:
    """Generate Anki deck with custom note type"""

    # Unique IDs for model and deck (generate once, keep consistent)
    MODEL_ID = 1607392319
    DECK_ID_BASE = 2059400110

    def __init__(self, deck_name: str = "Japanese Vocabulary"):
        self.deck_name = deck_name
        self.model = self._create_model()
        self.decks = {}  # chapter_name -> genanki.Deck
        self.media_files = []  # List of media files to include

    def _create_model(self) -> genanki.Model:
        """Create custom Anki note type with all fields"""

        # CSS styling
        css = """
/* Reset và box-sizing */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html, body {
    width: 100%;
    max-width: 100vw;
    overflow-x: hidden;
    margin: 0;
    padding: 0;
}

/* Hide scrollbar but allow scrolling */
html, body, .card {
    scrollbar-width: none;           /* Firefox */
    -ms-overflow-style: none;        /* IE/Edge */
}

html::-webkit-scrollbar,
body::-webkit-scrollbar,
.card::-webkit-scrollbar {
    display: none;                   /* Chrome/Safari/Opera */
    width: 0;
    height: 0;
}

.card {
    font-family: "Noto Sans JP", "Yu Gothic", "Hiragino Sans", sans-serif;
    font-size: 20px;
    text-align: center;
    color: #333;
    background-color: #fafafa;
    padding: 15px;
    width: 100%;
    max-width: 100vw;
    overflow-x: hidden;
    margin: 0 auto;
}

.word {
    font-size: 48px;
    font-weight: bold;
    color: #2c3e50;
    margin: 20px 0;
}

.reading {
    font-size: 24px;
    color: #7f8c8d;
    margin: 10px 0;
}

.romaji {
    font-size: 16px;
    color: #95a5a6;
    font-style: italic;
}

.meaning {
    font-size: 22px;
    margin: 15px 0;
}

.meaning-vi {
    color: #27ae60;
    font-weight: 500;
    font-size: 20px;
    margin-bottom: 5px;
}

.meaning-en {
    color: #3498db;
    margin-bottom: 5px;
}

.hanviet {
    font-size: 18px;
    color: #e74c3c;
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px dashed #ddd;
}

.pitch-diagram {
    margin: 10px auto;
    display: block;
    max-width: 100%;
    overflow: hidden;
}

.pitch-diagram svg {
    max-width: 100%;
    height: auto;
}

.stroke-order {
    margin: 10px auto;
    max-width: 100%;
    overflow: hidden;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 5px;
}

.stroke-order::-webkit-scrollbar {
    display: none;
}

.example {
    font-size: 16px;
    color: #555;
    text-align: left;
    margin: 10px 5px;
    padding: 10px;
    background: #ecf0f1;
    border-radius: 5px;
    word-break: break-word;
    overflow-wrap: break-word;
}

.radical {
    font-size: 15px;
    color: #8e44ad;
    margin: 8px 0 12px 0;
    padding: 8px 12px;
    background: linear-gradient(135deg, #f5eef8 0%, #ebdef0 100%);
    border-radius: 8px;
    border-left: 3px solid #9b59b6;
}

.origin {
    font-size: 14px;
    color: #666;
    font-style: italic;
    margin: 10px 0;
}

.kanji-detail {
    text-align: left;
    margin: 10px 5px;
    padding: 10px;
    background: #f8f9fa;
    border-left: 3px solid #9b59b6;
    border-radius: 5px;
    word-break: break-word;
    overflow-wrap: break-word;
}

.kanji-detail-title {
    font-size: 14px;
    font-weight: bold;
    color: #9b59b6;
    margin-bottom: 8px;
}

.kanji-pinyin {
    font-size: 13px;
    color: #e67e22;
    margin: 5px 0;
}

.kanji-reading {
    font-size: 13px;
    color: #16a085;
    margin: 5px 0;
}

.kanji-compound {
    font-size: 14px;
    color: #2980b9;
    margin: 5px 0;
}

.kanji-etymology {
    font-size: 13px;
    color: #555;
    line-height: 1.5;
    margin: 8px 0;
    padding: 8px;
    background: #fff;
    border-radius: 3px;
}

/* Dark theme support */
.stroke-svg {
    stroke: #333;
    stroke-width: 3;
    fill: none;
    max-width: 100px;
    height: auto;
}

.stroke-svg path {
    stroke: #333;
    fill: none;
}

.stroke-svg text {
    fill: #3498db;
    stroke: none;
    font-size: 8px;
}

.night_mode .stroke-svg {
    stroke: #e0e0e0;
}

.night_mode .stroke-svg path {
    stroke: #e0e0e0;
    fill: none;
}

.night_mode .stroke-svg text {
    fill: #64b5f6;
}

/* Night mode - main text elements */
.night_mode .word {
    color: #f5f5f5;
}

.night_mode .reading {
    color: #b0b0b0;
}

.night_mode .romaji {
    color: #b0bec5;
}

.night_mode ruby rt {
    color: #b0b0b0;
}

/* Night mode - pitch diagram */
.night_mode .pitch-diagram svg text {
    fill: #e0e0e0;
}

.night_mode .pitch-diagram svg .pitch-line {
    stroke: #ff7043;
}

.night_mode .pitch-diagram svg .pitch-dot {
    fill: #ff7043;
}

.night_mode .kanji-detail {
    background: #2d2d2d;
    border-left-color: #bb86fc;
}

.night_mode .kanji-detail-title {
    color: #bb86fc;
}

.night_mode .hanviet {
    border-bottom-color: #555;
}

.night_mode .kanji-pinyin {
    color: #ffb74d;
}

.night_mode .kanji-reading {
    color: #4db6ac;
}

.night_mode .kanji-compound {
    color: #64b5f6;
}

.night_mode .kanji-etymology {
    background: #1e1e1e;
    color: #e0e0e0;
}

.night_mode .example {
    background: #2d2d2d;
    color: #e0e0e0;
}

.night_mode .radical {
    color: #ce93d8;
    background: linear-gradient(135deg, #2d2d3d 0%, #3d3050 100%);
    border-left: 3px solid #ce93d8;
}

/* Frequency tier badges */
.frequency-info {
    font-size: 14px;
    color: #8e44ad;
    margin: 5px 0;
}

.freq-S { background: #e74c3c; color: white; padding: 2px 8px; border-radius: 10px; font-weight: bold; }
.freq-A { background: #e67e22; color: white; padding: 2px 8px; border-radius: 10px; font-weight: bold; }
.freq-B { background: #f1c40f; color: #333; padding: 2px 8px; border-radius: 10px; font-weight: bold; }
.freq-C { background: #27ae60; color: white; padding: 2px 8px; border-radius: 10px; font-weight: bold; }
.freq-D { background: #95a5a6; color: white; padding: 2px 8px; border-radius: 10px; font-weight: bold; }

.night_mode .frequency-info { color: #bb86fc; }
.night_mode .freq-B { color: #1a1a1a; }

/* JLPT Level badges */
.jlpt-level {
    display: inline-block;
    font-size: 12px;
    font-weight: bold;
    padding: 2px 10px;
    border-radius: 12px;
    margin: 5px 0;
}

.jlpt-N5 { background: #27ae60; color: white; }
.jlpt-N4 { background: #2ecc71; color: white; }
.jlpt-N3 { background: #f39c12; color: white; }
.jlpt-N2 { background: #e67e22; color: white; }
.jlpt-N1 { background: #e74c3c; color: white; }

/* Word type (part of speech) */
.word-type {
    font-size: 13px;
    color: #8e44ad;
    font-style: italic;
    margin: 5px 0;
}

.night_mode .word-type {
    color: #bb86fc;
}

/* Separator between meaning and chiết tự */
.kanji-detail-separator {
    border-top: 1px dashed #ccc;
    margin: 10px 0;
}

.night_mode .kanji-detail-separator {
    border-color: #555;
}

/* Furigana styling */
ruby {
    ruby-position: over;
}

ruby rt {
    font-size: 0.6em;
    color: #888;
}

.night_mode ruby rt {
    color: #aaa;
}

/* Verb conjugations */
.conjugations {
    font-size: 13px;
    color: #16a085;
    margin: 8px 0;
    padding: 8px;
    background: #e8f6f3;
    border-radius: 5px;
    word-break: break-word;
    overflow-wrap: break-word;
}

.night_mode .conjugations {
    background: #1a332e;
    color: #4db6ac;
}

/* Synonyms & Antonyms */
.synonyms, .antonyms {
    font-size: 13px;
    margin: 5px 0;
}

.synonyms {
    color: #2980b9;
}

.antonyms {
    color: #c0392b;
}

.night_mode .synonyms { color: #64b5f6; }
.night_mode .antonyms { color: #ef5350; }

.tags {
    font-size: 12px;
    color: #bdc3c7;
    margin-top: 20px;
}

.dictionary-link {
    margin-top: 15px;
}

.dictionary-link a {
    color: #3498db;
    text-decoration: none;
    padding: 5px 15px;
    border: 1px solid #3498db;
    border-radius: 20px;
}

.dictionary-link a:hover {
    background: #3498db;
    color: white;
}

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 20px 0;
}
"""

        # Front template (Question) - pitch ở đây để học phát âm
        front_template = """
<div class="word">{{Furigana}}</div>
{{#JLPTLevel}}<div class="jlpt-level jlpt-{{JLPTLevel}}">{{JLPTLevel}}</div>{{/JLPTLevel}}
{{#PitchDiagram}}<div class="pitch-diagram">{{PitchDiagram}}</div>{{/PitchDiagram}}
{{#Audio}}{{Audio}}{{/Audio}}
"""

        # Back template (Answer)
        back_template = """
<div class="word">{{Furigana}}</div>
{{#JLPTLevel}}<div class="jlpt-level jlpt-{{JLPTLevel}}">{{JLPTLevel}}</div>{{/JLPTLevel}}
{{#PitchDiagram}}<div class="pitch-diagram">{{PitchDiagram}}</div>{{/PitchDiagram}}
<div class="romaji">{{Romaji}}</div>

{{#Audio}}{{Audio}}{{/Audio}}

<hr>

<div class="kanji-detail">
    <div class="meaning meaning-vi">🇻🇳 {{MeaningVI}}</div>
    {{#MeaningEN}}<div class="meaning meaning-en">🇬🇧 {{MeaningEN}}</div>{{/MeaningEN}}
    {{#WordType}}<div class="word-type">📗 {{WordType}}</div>{{/WordType}}
    {{#HanViet}}<div class="hanviet">Hán Việt: {{HanViet}}</div>{{/HanViet}}
    {{#RadicalInfo}}<div class="radical">🔠 Bộ thủ: {{RadicalInfo}}</div>{{/RadicalInfo}}
    {{#FrequencyInfo}}<div class="frequency-info">Tần suất: {{FrequencyInfo}}</div>{{/FrequencyInfo}}
    {{#Conjugations}}<div class="conjugations">🔄 {{Conjugations}}</div>{{/Conjugations}}
    {{#Synonyms}}<div class="synonyms">≈ Đồng nghĩa: {{Synonyms}}</div>{{/Synonyms}}
    {{#Antonyms}}<div class="antonyms">≠ Trái nghĩa: {{Antonyms}}</div>{{/Antonyms}}
    {{#KanjiChiTiet}}
    <div class="kanji-detail-separator"></div>
    <div class="kanji-detail-title">📚 Chiết tự Hán</div>
    {{#KanjiPinyin}}<div class="kanji-pinyin">🔊 Pinyin: {{KanjiPinyin}}</div>{{/KanjiPinyin}}
    {{#KanjiKun}}<div class="kanji-reading">Kun: {{KanjiKun}}</div>{{/KanjiKun}}
    {{#KanjiOn}}<div class="kanji-reading">On: {{KanjiOn}}</div>{{/KanjiOn}}
    {{#KanjiTuGhep}}<div class="kanji-compound">📝 Từ ghép: {{KanjiTuGhep}}</div>{{/KanjiTuGhep}}
    <div class="kanji-etymology">{{KanjiChiTiet}}</div>
    {{/KanjiChiTiet}}
</div>

{{#StrokeOrder}}
<hr>
<div class="stroke-order">{{StrokeOrder}}</div>
{{/StrokeOrder}}

{{#Examples}}
<hr>
<div class="example">{{Examples}}</div>
{{/Examples}}

<div class="dictionary-link">
    <a href="{{TakobotoLink}}" target="_blank">📖 Takoboto</a>
</div>

<div class="tags">{{Chapter}} / {{SubCategory}}</div>
"""

        # Reverse card template (Vietnamese → Japanese)
        reverse_front = """
<div class="meaning meaning-vi" style="font-size: 28px;">🇻🇳 {{MeaningVI}}</div>
{{#MeaningEN}}<div class="meaning meaning-en">🇬🇧 {{MeaningEN}}</div>{{/MeaningEN}}
{{#JLPTLevel}}<div class="jlpt-level jlpt-{{JLPTLevel}}">{{JLPTLevel}}</div>{{/JLPTLevel}}
"""

        reverse_back = """
<div class="meaning meaning-vi" style="font-size: 28px;">🇻🇳 {{MeaningVI}}</div>
{{#MeaningEN}}<div class="meaning meaning-en">🇬🇧 {{MeaningEN}}</div>{{/MeaningEN}}

<hr>

<div class="word">{{Furigana}}</div>
{{#JLPTLevel}}<div class="jlpt-level jlpt-{{JLPTLevel}}">{{JLPTLevel}}</div>{{/JLPTLevel}}
{{#PitchDiagram}}<div class="pitch-diagram">{{PitchDiagram}}</div>{{/PitchDiagram}}
<div class="romaji">{{Romaji}}</div>

{{#Audio}}{{Audio}}{{/Audio}}

{{#WordType}}<div class="word-type">📗 {{WordType}}</div>{{/WordType}}
{{#HanViet}}<div class="hanviet">Hán Việt: {{HanViet}}</div>{{/HanViet}}
{{#RadicalInfo}}<div class="radical">🔠 Bộ thủ: {{RadicalInfo}}</div>{{/RadicalInfo}}
{{#Conjugations}}<div class="conjugations">🔄 {{Conjugations}}</div>{{/Conjugations}}

<div class="dictionary-link">
    <a href="{{TakobotoLink}}" target="_blank">📖 Takoboto</a>
</div>

<div class="tags">{{Chapter}} / {{SubCategory}}</div>
"""

        return genanki.Model(
            self.MODEL_ID,
            "Japanese Vocabulary Enhanced",
            fields=[
                {"name": "Word"},
                {"name": "Reading"},
                {"name": "Romaji"},
                {"name": "MeaningVI"},
                {"name": "MeaningEN"},
                {"name": "HanViet"},
                {"name": "PitchPattern"},
                {"name": "PitchDiagram"},
                {"name": "StrokeOrder"},
                {"name": "Audio"},
                {"name": "Examples"},
                {"name": "RadicalInfo"},
                {"name": "FrequencyInfo"},
                {"name": "KanjiPinyin"},
                {"name": "KanjiKun"},
                {"name": "KanjiOn"},
                {"name": "KanjiTuGhep"},
                {"name": "KanjiChiTiet"},
                {"name": "Chapter"},
                {"name": "SubCategory"},
                {"name": "TakobotoLink"},
                # New fields
                {"name": "JLPTLevel"},
                {"name": "WordType"},
                {"name": "Furigana"},
                {"name": "Conjugations"},
                {"name": "Synonyms"},
                {"name": "Antonyms"},
            ],
            templates=[
                {
                    "name": "Recognition",
                    "qfmt": front_template,
                    "afmt": back_template,
                },
                {
                    "name": "Production",
                    "qfmt": reverse_front,
                    "afmt": reverse_back,
                },
            ],
            css=css,
        )

    def add_entry(self, entry: VocabEntry, chapter: str):
        """Add a vocabulary entry to the appropriate deck"""
        # Create deck if not exists
        if chapter not in self.decks:
            deck_id = self.DECK_ID_BASE + hash(chapter) % 1000000
            deck = genanki.Deck(deck_id, f"{self.deck_name}::{chapter}")
            self.decks[chapter] = deck

        # Build tags
        tags = [
            entry.chapter.replace(" ", "_"),
            entry.sub_category.replace(" ", "_") if entry.sub_category else "",
        ]
        if entry.jlpt_level:
            tags.append(entry.jlpt_level)  # Add JLPT level as tag for filtering

        # Create note
        note = genanki.Note(
            model=self.model,
            fields=[
                entry.word or "",
                entry.reading or "",
                entry.romaji or "",
                entry.meaning_vi or "",
                entry.meaning_en or "",
                entry.han_viet or "",
                entry.pitch_pattern or "",
                entry.pitch_svg or "",
                entry.stroke_order_svg or "",
                f"[sound:{Path(entry.audio_file).name}]" if entry.audio_file else "",
                entry.examples or "",
                entry.radical_info or "",
                entry.frequency_info or "",
                entry.kanji_pinyin or "",
                entry.kanji_kun or "",
                entry.kanji_on or "",
                entry.kanji_tu_ghep or "",
                entry.kanji_chi_tiet or "",
                entry.chapter or "",
                entry.sub_category or "",
                entry.takoboto_link or "",
                entry.jlpt_level or "",
                entry.word_type or "",
                entry.furigana or "",
                entry.conjugations or "",
                entry.synonyms or "",
                entry.antonyms or "",
            ],
            tags=tags,
        )

        self.decks[chapter].add_note(note)

        # Track audio file
        if entry.audio_file and os.path.exists(entry.audio_file):
            self.media_files.append(entry.audio_file)

            # Track example audio files (inline in entry.examples)
            if entry.examples:
                import re

                examples_dir = Path(entry.audio_file).parent.parent / "examples"
                for match in re.findall(r"\[sound:([^\]]+)\]", entry.examples):
                    audio_path = examples_dir / match
                    if audio_path.exists():
                        self.media_files.append(str(audio_path))

    def export(self, output_path: str):
        """Export all decks to a single .apkg file"""
        # Create package with all decks
        package = genanki.Package(list(self.decks.values()))
        package.media_files = self.media_files
        package.write_to_file(output_path)
        print(f"Exported deck to: {output_path}")
        return output_path


# =============================================================================
# MAIN PIPELINE
# =============================================================================


class JapaneseVocabPipeline:
    """Main pipeline to generate Anki deck"""

    def __init__(self, epub_path: str, output_dir: str = "./output"):
        self.epub_path = epub_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Split audio into words and examples folders
        self.audio_dir = self.output_dir / "audio"
        self.audio_dir.mkdir(exist_ok=True)
        self.words_audio_dir = self.audio_dir / "words"
        self.words_audio_dir.mkdir(exist_ok=True)
        self.examples_audio_dir = self.audio_dir / "examples"
        self.examples_audio_dir.mkdir(exist_ok=True)

        # Migrate old audio files from audio/ to audio/words/
        self._migrate_old_audio()

        self.stroke_dir = self.output_dir / "stroke_cache"
        self.stroke_dir.mkdir(exist_ok=True)

        # Checkpoint file
        self.checkpoint_file = self.output_dir / "checkpoint.json"
        self.processed: set = set()
        self._load_checkpoint()

        # Components
        self.parser = EPUBVocabParser(epub_path)
        self.deck_generator = AnkiDeckGenerator("Tiếng Nhật Theo Chủ Đề")

        # Stats
        self.stats = {
            "total_words": 0,
            "chapters": 0,
            "audio_generated": 0,
            "audio_cached": 0,
            "example_audio_generated": 0,
            "example_audio_cached": 0,
            "stroke_generated": 0,
            "stroke_cached": 0,
            "pitch_found": 0,
            "hanviet_found": 0,
            "chiettu_found": 0,
            "skipped_cached": 0,
        }

    def _migrate_old_audio(self):
        """Migrate old audio files from audio/ root to audio/words/"""
        import shutil

        migrated = 0
        for mp3_file in self.audio_dir.glob("*.mp3"):
            # Only move files in root audio/, not in subfolders
            if mp3_file.parent == self.audio_dir:
                dest = self.words_audio_dir / mp3_file.name
                if not dest.exists():
                    shutil.move(str(mp3_file), str(dest))
                    migrated += 1
        if migrated > 0:
            print(f"Migrated {migrated} audio files to audio/words/")

    def _load_checkpoint(self):
        """Load processed entries from checkpoint"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.processed = set(data.get("processed", []))
                    print(
                        f"Loaded checkpoint: {len(self.processed)} entries already processed"
                    )
            except Exception as e:
                print(f"Warning: Could not load checkpoint: {e}")
                self.processed = set()

    def _save_checkpoint(self):
        """Save checkpoint to file"""
        try:
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "processed": list(self.processed),
                        "epub": self.epub_path,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            # Also save RadicalDB jamdict cache
            RadicalDB._save_cache()
        except Exception as e:
            print(f"Warning: Could not save checkpoint: {e}")

    def _get_entry_key(self, entry: VocabEntry, chapter: str = "") -> str:
        """Generate unique key for an entry"""
        return f"{entry.word}::{entry.reading}::{entry.meaning_vi}"

    def clear_checkpoint(self):
        """Clear checkpoint to start fresh"""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        self.processed = set()
        print("Checkpoint cleared")

    def run(
        self,
        enrich_english: bool = True,
        generate_audio: bool = True,
        generate_pitch: bool = True,
        generate_stroke: bool = True,
        generate_example: bool = True,
        rate_limit_delay: float = 0.5,
        force_restart: bool = False,
        offline: bool = False,
        verbose: bool = False,
    ):
        """Run the full pipeline"""

        self.offline = offline
        self._last_api_called = False
        self.verbose = verbose
        self.generate_example = generate_example

        if force_restart:
            self.clear_checkpoint()

        print("=" * 60)
        print("JAPANESE VOCABULARY ANKI DECK GENERATOR")
        print("=" * 60)
        if offline:
            print("[MODE] Offline - no API calls")
        if verbose:
            print("[MODE] Verbose output enabled")

        # Phase 1: Parse EPUB
        print("\n[Phase 1] Parsing EPUB...")
        chapters = self.parser.parse()
        self.stats["chapters"] = len(chapters)
        print(f"Found {len(chapters)} chapters")

        # Phase 2: Enrich and generate
        print("\n[Phase 2] Enriching vocabulary...")

        for chapter_name, entries in chapters.items():
            print(f"\n  Processing: {chapter_name} ({len(entries)} words)")

            for i, entry in enumerate(entries):
                self.stats["total_words"] += 1

                # Progress indicator
                if (i + 1) % 20 == 0:
                    print(f"    {i + 1}/{len(entries)} processed...")

                # Enrich entry (individual APIs have their own cache)
                self._enrich_entry(
                    entry,
                    enrich_english=enrich_english,
                    generate_audio=generate_audio,
                    generate_pitch=generate_pitch,
                    generate_stroke=generate_stroke,
                )

                # Add to deck
                self.deck_generator.add_entry(entry, chapter_name)

                # Rate limiting only when API was actually called
                if self._last_api_called:
                    time.sleep(rate_limit_delay)

        # Phase 3: Export
        print("\n[Phase 3] Exporting Anki deck...")
        output_path = self.output_dir / "japanese_vocabulary.apkg"
        self.deck_generator.export(str(output_path))

        # Print stats
        print("\n" + "=" * 60)
        print("GENERATION COMPLETE")
        print("=" * 60)
        print(f"Total chapters: {self.stats['chapters']}")
        print(f"Total words processed: {self.stats['total_words']}")
        print(f"Word audio generated: {self.stats['audio_generated']}")
        print(f"Word audio cached: {self.stats['audio_cached']}")
        print(f"Example audio generated: {self.stats['example_audio_generated']}")
        print(f"Example audio cached: {self.stats['example_audio_cached']}")
        print(f"Stroke generated: {self.stats['stroke_generated']}")
        print(f"Stroke cached (skipped): {self.stats['stroke_cached']}")
        print(f"Pitch patterns found: {self.stats['pitch_found']}")
        print(f"Hán Việt found: {self.stats['hanviet_found']}")
        print(f"Chiết tự found: {self.stats['chiettu_found']}")
        print(f"\nOutput: {output_path}")
        print(f"Checkpoint: {self.checkpoint_file}")

        return str(output_path)

    def _enrich_entry(
        self,
        entry: VocabEntry,
        enrich_english: bool,
        generate_audio: bool,
        generate_pitch: bool,
        generate_stroke: bool,
    ):
        """Enrich a single vocabulary entry"""

        self._last_api_called = False
        api_calls = []
        # === VALIDATE READING FROM JISHO ===
        jisho_reading = JishoAPI.get_reading(entry.word)
        if jisho_reading and jisho_reading != entry.reading:
            if self.verbose:
                print(f"      [FIX] {entry.word}: {entry.reading} → {jisho_reading}")
            entry.reading = jisho_reading

        # === VALIDATE READING COMPLETENESS ===
        # Fix incomplete readings like あなた for あなたの猫 → あなたのねこ
        validated_reading = FuriganaGenerator._validate_reading(
            entry.word, entry.reading
        )
        if validated_reading and validated_reading != entry.reading:
            if self.verbose:
                print(
                    f"      [FIX-READING] {entry.word}: {entry.reading} → {validated_reading}"
                )
            entry.reading = validated_reading

        if self.verbose:
            print(f"      → {entry.word} ({entry.reading})", end="")

        # Kanji database - full info including chiết tự
        kanji_info = KanjiDB.get_word_info(entry.word)

        # Hán Việt from kanji_info
        if kanji_info["han_viet"]:
            entry.han_viet = " ".join(kanji_info["han_viet"])
            self.stats["hanviet_found"] += 1

        # Pinyin
        if kanji_info["pinyin"]:
            entry.kanji_pinyin = ", ".join(kanji_info["pinyin"])

        # Kun/On readings - ưu tiên KanjiAPI, fallback local
        first_kanji = next((c for c in entry.word if "\u4e00" <= c <= "\u9fff"), None)
        if first_kanji:
            kun_api, on_api = KanjiAPI.get_readings(first_kanji)
            if kun_api or on_api:
                if kun_api:
                    entry.kanji_kun = " | ".join(kun_api)
                if on_api:
                    entry.kanji_on = " | ".join(on_api)
            else:
                # Fallback to local database
                if kanji_info["kun"]:
                    entry.kanji_kun = " | ".join(kanji_info["kun"])
                if kanji_info["on"]:
                    entry.kanji_on = " | ".join(kanji_info["on"])

        # Từ ghép (compound words)
        if kanji_info["tu_ghep"]:
            tu_ghep_html = []
            for tg in kanji_info["tu_ghep"][:4]:
                if isinstance(tg, dict):
                    han_part = tg.get("han", "")
                    viet_part = tg.get("viet", "")
                    # Add furigana to Japanese part
                    han_with_ruby = (
                        SentenceFuriganaGenerator.generate(han_part) if han_part else ""
                    )
                    tu_ghep_html.append(f"{viet_part} {han_with_ruby}")
                else:
                    tu_ghep_html.append(str(tg))
            entry.kanji_tu_ghep = " • ".join(tu_ghep_html)

        # Chi tiết chiết tự
        if kanji_info["chi_tiet"]:
            entry.kanji_chi_tiet = "<br><br>".join(kanji_info["chi_tiet"][:2])
            self.stats["chiettu_found"] += 1

        # Radical info - collect ALL component radicals from each kanji
        radical_parts = []
        seen_radicals = set()
        for char in entry.word:
            if "\u4e00" <= char <= "\u9fff":  # Is kanji
                # Get all radicals for this kanji
                all_radicals = RadicalDB.identify_all_radicals(char)
                for radical_info in all_radicals:
                    if radical_info and radical_info.get("symbol") not in seen_radicals:
                        seen_radicals.add(radical_info.get("symbol"))
                        # Format: 心 (忄) • tim, tâm [⭐ Thiết yếu]
                        rad_symbol = radical_info.get("symbol", "")
                        found_as = radical_info.get("found_as", "")
                        meaning_vn = radical_info.get("meaning_vn", "")
                        freq = radical_info.get("frequency", 0)
                        joyo = radical_info.get("joyo_freq", 0)
                        importance = RadicalDB.get_importance_label(freq, joyo)

                        # Show variant if different from main symbol
                        if found_as and found_as != rad_symbol:
                            radical_parts.append(
                                f"{rad_symbol} ({found_as}) • {meaning_vn} [{importance}]"
                            )
                        else:
                            radical_parts.append(
                                f"{rad_symbol} • {meaning_vn} [{importance}]"
                            )

        if radical_parts:
            entry.radical_info = " | ".join(radical_parts)  # Show all radicals

        # Frequency info - handle compound words (each kanji)
        freq_parts = []
        for char in entry.word:
            if "\u4e00" <= char <= "\u9fff":  # Is kanji
                freq = KanjiFrequencyDB.get_frequency(char)
                if freq:
                    tier = freq["tier"]
                    rank = freq["rank"]
                    freq_parts.append(
                        f'<span class="freq-{tier}">{char} [{tier} #{rank}]</span>'
                    )
        if freq_parts:
            entry.frequency_info = " ".join(freq_parts)

        # === NEW ENRICHMENTS ===

        # JLPT Level - O(1) lookup
        entry.jlpt_level = JLPTDB.get_level(entry.word)
        if not entry.jlpt_level:
            # Try reading if word not found
            entry.jlpt_level = JLPTDB.get_level(entry.reading)

        # Furigana - O(n)
        entry.furigana = FuriganaGenerator.generate(entry.word, entry.reading)

        # Word type - from cached Jisho data, O(1) if cached
        entry.word_type = JishoAPI.get_word_type(entry.word)

        # Synonyms/Antonyms - from cached Jisho data, O(1) if cached
        entry.synonyms, entry.antonyms = JishoAPI.get_synonyms_antonyms(entry.word)

        # Verb conjugation - O(1) pattern matching
        if entry.word_type and (
            "Động từ" in entry.word_type or "Verb" in entry.word_type
        ):
            entry.conjugations = VerbConjugator.format_conjugations(
                entry.word, entry.reading, entry.word_type
            )

        # === END NEW ENRICHMENTS ===

        # Example sentences - with furigana and inline audio
        if self.generate_example:
            examples = ExampleSentencesDB.get_examples(
                entry.word, limit=2, offline=self.offline
            )
            if ExampleSentencesDB.last_api_called:
                self._last_api_called = True
                api_calls.append("EX")
            if examples:
                import re

                examples_final = []
                example_audio_generated = False

                for i, ex in enumerate(examples):
                    if "→" in ex:
                        jp_part, vi_part = ex.split("→", 1)
                        jp_part = jp_part.strip()
                        vi_part = vi_part.strip()

                        # Add furigana
                        jp_with_ruby = SentenceFuriganaGenerator.generate(jp_part)

                        # Generate audio for this sentence (inline at end)
                        audio_tag = ""
                        if generate_audio and not self.offline:
                            ex_hash = hashlib.md5(
                                f"{entry.word}_{i}_{jp_part}".encode()
                            ).hexdigest()[:10]
                            ex_audio_filename = f"ex_{ex_hash}.mp3"
                            ex_audio_path = self.examples_audio_dir / ex_audio_filename

                            if ex_audio_path.exists():
                                audio_tag = f" [sound:{ex_audio_filename}]"
                                self.stats["example_audio_cached"] += 1
                            else:
                                if TTSGenerator.generate_audio(
                                    jp_part, str(ex_audio_path)
                                ):
                                    audio_tag = f" [sound:{ex_audio_filename}]"
                                    self.stats["example_audio_generated"] += 1
                                    example_audio_generated = True

                        # Combine: Japanese (with ruby) → Vietnamese [audio]
                        examples_final.append(f"{jp_with_ruby} → {vi_part}{audio_tag}")
                    else:
                        examples_final.append(ex)

                entry.examples = "<br>".join(examples_final)

                if example_audio_generated:
                    self._last_api_called = True
                    api_calls.append("EX_AUDIO")

        # English meaning (API call) - skip in offline mode
        if enrich_english and not self.offline:
            try:
                entry.meaning_en = JishoAPI.get_english_meaning(entry.word)
                if JishoAPI.last_api_called:
                    self._last_api_called = True
                    api_calls.append("EN")
            except:
                pass

        # Pitch accent - offline mode uses local DB only
        if generate_pitch:
            pattern, morae = PitchAccentAPI.get_pitch_pattern(
                entry.word, entry.reading, offline=self.offline
            )
            if PitchAccentAPI.last_api_called:
                self._last_api_called = True
                api_calls.append("PITCH")
            entry.pitch_pattern = pattern
            if pattern != "?":
                self.stats["pitch_found"] += 1
            entry.pitch_svg = PitchDiagramGenerator.generate_svg(
                entry.reading, pattern, morae
            )

        # Stroke order - handle compound words (each kanji separately)
        if generate_stroke:
            stroke_svgs = []
            stroke_api_called = False
            for char in entry.word:
                # Skip non-kanji (hiragana, katakana, punctuation)
                if not ("\u4e00" <= char <= "\u9fff"):
                    continue

                stroke_cache_file = self.stroke_dir / f"{ord(char)}.svg"

                if stroke_cache_file.exists():
                    # Load from cache
                    svg = stroke_cache_file.read_text(encoding="utf-8")
                    stroke_svgs.append(svg)
                    self.stats["stroke_cached"] += 1
                elif not self.offline:
                    try:
                        self._last_api_called = True
                        stroke_api_called = True
                        svg = StrokeOrderAPI.get_stroke_order_svg(char)
                        if svg:
                            stroke_svgs.append(svg)
                            # Save to cache
                            stroke_cache_file.write_text(svg, encoding="utf-8")
                            self.stats["stroke_generated"] += 1
                    except:
                        pass

            if stroke_api_called:
                api_calls.append("STROKE")

            # Combine all stroke SVGs
            if stroke_svgs:
                entry.stroke_order_svg = "".join(stroke_svgs)

        # Audio for word - check if already exists
        if generate_audio:
            audio_filename = f"{hashlib.md5(entry.word.encode()).hexdigest()[:8]}.mp3"
            audio_path = self.words_audio_dir / audio_filename

            if audio_path.exists():
                # Audio already exists, skip generation
                entry.audio_file = str(audio_path)
                self.stats["audio_cached"] += 1
            elif not self.offline:
                self._last_api_called = True
                api_calls.append("AUDIO")
                if TTSGenerator.generate_audio(entry.word, str(audio_path)):
                    entry.audio_file = str(audio_path)
                    self.stats["audio_generated"] += 1

        # Debug: show which APIs were called
        if self.verbose:
            if api_calls:
                print(f" [API: {','.join(api_calls)}]")
            else:
                # Show cached details
                cached_items = []
                if entry.audio_file:
                    cached_items.append("audio")
                if entry.meaning_en:
                    cached_items.append("en")
                if entry.pitch_pattern:
                    cached_items.append("pitch")
                if entry.examples:
                    cached_items.append("ex")
                print(f" [cached: {','.join(cached_items) if cached_items else 'all'}]")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate Anki deck from Japanese vocabulary EPUB"
    )
    parser.add_argument("epub_path", help="Path to EPUB file")
    parser.add_argument("-o", "--output", default="./output", help="Output directory")
    parser.add_argument(
        "--no-english", action="store_true", help="Skip English meanings (faster)"
    )
    parser.add_argument("--no-audio", action="store_true", help="Skip audio generation")
    parser.add_argument("--no-pitch", action="store_true", help="Skip pitch diagrams")
    parser.add_argument("--no-stroke", action="store_true", help="Skip stroke order")
    parser.add_argument(
        "--no-example", action="store_true", help="Skip example sentences"
    )
    parser.add_argument(
        "--delay", type=float, default=0.5, help="API rate limit delay (seconds)"
    )
    parser.add_argument(
        "--force-restart", action="store_true", help="Clear checkpoint and start fresh"
    )
    parser.add_argument(
        "--offline", action="store_true", help="No API calls, use local data only"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print detailed progress"
    )

    args = parser.parse_args()

    pipeline = JapaneseVocabPipeline(args.epub_path, args.output)
    pipeline.run(
        enrich_english=not args.no_english,
        generate_audio=not args.no_audio,
        generate_pitch=not args.no_pitch,
        generate_stroke=not args.no_stroke,
        generate_example=not args.no_example,
        rate_limit_delay=args.delay,
        force_restart=args.force_restart,
        offline=args.offline,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
