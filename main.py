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
    word: str                          # Kanji or Kana word
    reading: str                       # Hiragana reading
    romaji: str                        # Romaji
    meaning_vi: str                    # Vietnamese meaning
    meaning_en: str = ""               # English meaning
    han_viet: str = ""                 # Sino-Vietnamese reading
    pitch_pattern: str = ""            # Pitch accent pattern (e.g., "0", "1", "2")
    pitch_svg: str = ""                # SVG diagram for pitch
    stroke_order_svg: str = ""         # Stroke order diagram
    audio_file: str = ""               # Path to audio file
    example_sentences: List[str] = field(default_factory=list)
    radical_info: str = ""             # Bộ thủ information
    kanji_origin: str = ""             # Etymology/origin
    chapter: str = ""                  # Source chapter
    sub_category: str = ""             # Sub-category within chapter
    takoboto_link: str = ""            # Takoboto dictionary link
    examples: str = ""                 # Example sentences HTML
    # Kanji detail fields
    kanji_pinyin: str = ""             # Chinese pinyin
    kanji_kun: str = ""                # Kun-yomi
    kanji_on: str = ""                 # On-yomi
    kanji_tu_ghep: str = ""            # Compound words HTML
    kanji_chi_tiet: str = ""           # Etymology explanation
    frequency_info: str = ""           # Frequency tier [S #8]
    # New fields
    jlpt_level: str = ""               # JLPT level (N5-N1)
    word_type: str = ""                # Part of speech (Noun, Verb, Adj, etc.)
    furigana: str = ""                 # HTML ruby text
    conjugations: str = ""             # Verb conjugations HTML
    synonyms: str = ""                 # Similar words
    antonyms: str = ""                 # Opposite words

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
        with zipfile.ZipFile(self.epub_path, 'r') as zf:
            # Find all chapter files
            chapter_files = sorted([
                f for f in zf.namelist()
                if 'chapter-' in f and f.endswith('.xhtml')
            ], key=lambda x: int(re.search(r'chapter-(\d+)', x).group(1)))

            for chapter_file in chapter_files:
                with zf.open(chapter_file) as f:
                    content = f.read().decode('utf-8')
                    self._parse_chapter(chapter_file, content)

        return self.chapters

    def _parse_chapter(self, filename: str, content: str):
        """Parse a single chapter"""
        soup = BeautifulSoup(content, 'html.parser')

        # Get chapter title from h1
        h1 = soup.find('h1')
        chapter_name = h1.get_text().strip() if h1 else filename

        entries = []
        current_subcategory = ""

        # Find all h2 (subcategories) and vocabulary entries
        for element in soup.find_all(['h2', 'div']):
            if element.name == 'h2':
                current_subcategory = element.get_text().strip()
            elif element.name == 'div':
                classes = element.get('class') or []
                if 'l_outer' in classes:
                    entry = self._parse_vocab_entry(element, chapter_name, current_subcategory)
                    if entry:
                        entries.append(entry)

        if entries:
            self.chapters[chapter_name] = entries

    def _parse_vocab_entry(self, div, chapter: str, subcategory: str) -> Optional[VocabEntry]:
        """Parse a single vocabulary entry div"""
        try:
            # Vietnamese meaning
            trans_span = div.find('span', class_='top_trans')
            meaning_vi_raw = trans_span.get_text().strip() if trans_span else ""
            # Clean Vietnamese - remove any Japanese characters mixed in
            meaning_vi = self._clean_vietnamese(meaning_vi_raw)

            # Japanese word (Kanji or Kana)
            word_span = div.find('span', class_='top_word')
            word_raw = word_span.get_text().strip() if word_span else ""
            # Clean Japanese - only keep Japanese characters
            word = self._clean_japanese(word_raw)

            # Romaji reading
            post_span = div.find('span', class_='top_post')
            romaji_raw = post_span.get_text().strip() if post_span else ""
            # Remove parentheses and clean
            romaji = romaji_raw.strip('()').lower()
            romaji = ''.join(c for c in romaji if c.isalpha() or c.isspace())

            if not word or not meaning_vi:
                return None

            entry = VocabEntry(
                word=word,
                reading=self._romaji_to_hiragana(romaji),
                romaji=romaji,
                meaning_vi=meaning_vi,
                chapter=chapter,
                sub_category=subcategory
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
            if (0x3040 <= code <= 0x309F or  # Hiragana
                0x30A0 <= code <= 0x30FF or  # Katakana
                0x4E00 <= code <= 0x9FFF or  # Common Kanji
                char == '々'):                # Kanji repeat mark
                result.append(char)
        return ''.join(result)

    def _clean_vietnamese(self, text: str) -> str:
        """Keep only Vietnamese/Latin characters, remove Japanese"""
        result = []
        for char in text:
            code = ord(char)
            # Skip Japanese characters
            if (0x3040 <= code <= 0x309F or  # Hiragana
                0x30A0 <= code <= 0x30FF or  # Katakana
                0x4E00 <= code <= 0x9FFF):   # Kanji
                continue
            result.append(char)
        return ''.join(result).strip()

    def _romaji_to_hiragana(self, romaji: str) -> str:
        """Convert romaji to hiragana (basic conversion)"""
        # This is a simplified conversion - for production, use a proper library
        romaji_map = {
            'a': 'あ', 'i': 'い', 'u': 'う', 'e': 'え', 'o': 'お',
            'ka': 'か', 'ki': 'き', 'ku': 'く', 'ke': 'け', 'ko': 'こ',
            'sa': 'さ', 'shi': 'し', 'su': 'す', 'se': 'せ', 'so': 'そ',
            'ta': 'た', 'chi': 'ち', 'tsu': 'つ', 'te': 'て', 'to': 'と',
            'na': 'な', 'ni': 'に', 'nu': 'ぬ', 'ne': 'ね', 'no': 'の',
            'ha': 'は', 'hi': 'ひ', 'fu': 'ふ', 'he': 'へ', 'ho': 'ほ',
            'ma': 'ま', 'mi': 'み', 'mu': 'む', 'me': 'め', 'mo': 'も',
            'ya': 'や', 'yu': 'ゆ', 'yo': 'よ',
            'ra': 'ら', 'ri': 'り', 'ru': 'る', 're': 'れ', 'ro': 'ろ',
            'wa': 'わ', 'wo': 'を', 'n': 'ん',
            'ga': 'が', 'gi': 'ぎ', 'gu': 'ぐ', 'ge': 'げ', 'go': 'ご',
            'za': 'ざ', 'ji': 'じ', 'zu': 'ず', 'ze': 'ぜ', 'zo': 'ぞ',
            'da': 'だ', 'di': 'ぢ', 'du': 'づ', 'de': 'で', 'do': 'ど',
            'ba': 'ば', 'bi': 'び', 'bu': 'ぶ', 'be': 'べ', 'bo': 'ぼ',
            'pa': 'ぱ', 'pi': 'ぴ', 'pu': 'ぷ', 'pe': 'ぺ', 'po': 'ぽ',
            'kya': 'きゃ', 'kyu': 'きゅ', 'kyo': 'きょ',
            'sha': 'しゃ', 'shu': 'しゅ', 'sho': 'しょ',
            'cha': 'ちゃ', 'chu': 'ちゅ', 'cho': 'ちょ',
            'nya': 'にゃ', 'nyu': 'にゅ', 'nyo': 'にょ',
            'hya': 'ひゃ', 'hyu': 'ひゅ', 'hyo': 'ひょ',
            'mya': 'みゃ', 'myu': 'みゅ', 'myo': 'みょ',
            'rya': 'りゃ', 'ryu': 'りゅ', 'ryo': 'りょ',
            'gya': 'ぎゃ', 'gyu': 'ぎゅ', 'gyo': 'ぎょ',
            'ja': 'じゃ', 'ju': 'じゅ', 'jo': 'じょ',
            'bya': 'びゃ', 'byu': 'びゅ', 'byo': 'びょ',
            'pya': 'ぴゃ', 'pyu': 'ぴゅ', 'pyo': 'ぴょ',
            # Long vowels
            'ā': 'ああ', 'ī': 'いい', 'ū': 'うう', 'ē': 'ええ', 'ō': 'おお',
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
    def lookup(cls, word: str, use_cache: bool = True) -> Dict:
        """Look up a word in Jisho with caching"""
        cls._init_cache()

        word_hash = hashlib.md5(word.encode()).hexdigest()[:12]
        cache_file = cls._jisho_cache_dir / f"{word_hash}.json"

        # Check cache
        if use_cache and cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
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
                if data.get('data'):
                    result = data['data'][0]
                    # Cache result
                    try:
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False)
                    except:
                        pass
                    return result
        except Exception as e:
            print(f"Jisho lookup error for {word}: {e}")

        # Cache empty result
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
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
            cached = cache_file.read_text(encoding='utf-8')
            return "" if cached == "_EMPTY_" else cached

        # Get from full Jisho data
        data = cls.lookup(word)
        meaning = ""
        if data and 'senses' in data:
            meanings = []
            for sense in data['senses'][:2]:  # First 2 senses
                if 'english_definitions' in sense:
                    meanings.extend(sense['english_definitions'][:3])
            meaning = "; ".join(meanings)

        # Save to cache (including empty to avoid re-fetching)
        cache_file.write_text(meaning if meaning else "_EMPTY_", encoding='utf-8')

        return meaning

    @classmethod
    def get_word_type(cls, word: str) -> str:
        """Get part of speech from Jisho. Returns formatted string."""
        data = cls.lookup(word)
        if not data or 'senses' not in data:
            return ""

        # Collect unique parts of speech
        pos_set = set()
        for sense in data.get('senses', [])[:2]:
            for pos in sense.get('parts_of_speech', []):
                pos_set.add(pos)

        if not pos_set:
            return ""

        # Translate common types to Vietnamese
        translations = {
            'Noun': 'Danh từ',
            'Verb': 'Động từ',
            'I-adjective': 'Tính từ -い',
            'Na-adjective': 'Tính từ -な',
            'Adverb': 'Trạng từ',
            'Suru verb': 'Động từ する',
            'Godan verb': 'Động từ Godan',
            'Ichidan verb': 'Động từ Ichidan',
            'Intransitive verb': 'Tự động từ',
            'Transitive verb': 'Tha động từ',
            'Expression': 'Thành ngữ',
            'Particle': 'Trợ từ',
            'Conjunction': 'Liên từ',
            'Counter': 'Trợ số từ',
            'Suffix': 'Hậu tố',
            'Prefix': 'Tiền tố',
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

        return ' • '.join(result[:3])  # Limit to 3

    @classmethod
    def get_synonyms_antonyms(cls, word: str) -> Tuple[str, str]:
        """Get synonyms and antonyms from Jisho. Returns (synonyms, antonyms)."""
        data = cls.lookup(word)
        if not data or 'senses' not in data:
            return "", ""

        synonyms = []
        antonyms = []

        for sense in data.get('senses', []):
            # See also = similar words
            see_also = sense.get('see_also', [])
            synonyms.extend(see_also[:3])

            # Antonyms (less common in Jisho)
            ant = sense.get('antonyms', [])
            antonyms.extend(ant[:3])

        return ' • '.join(synonyms[:4]), ' • '.join(antonyms[:4])


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
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.pop('_comment', None)
                # Convert: {"word": [["reading", pattern], ...]} -> {"word": (str(pattern), [morae])}
                for word, readings in data.items():
                    if readings:
                        reading, pattern = readings[0]  # Take first reading
                        morae = cls.split_morae(reading)
                        cls.PITCH_DB[word] = (str(pattern), morae)
        cls._loaded = True

    @classmethod
    def get_pitch_pattern(cls, word: str, reading: str, offline: bool = False) -> Tuple[str, List[str]]:
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
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    return (str(cached.get('pattern', '?')), morae)
            except:
                pass

        # 3. Skip API if offline
        if offline:
            return ('?', morae)

        # 4. Fetch from Jisho API
        cls.last_api_called = True
        pattern = cls._fetch_from_jisho(word, reading)

        # 5. Save to cache (including '?' to avoid re-fetching)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'word': word, 'reading': reading, 'pattern': pattern}, f)
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
                for item in data.get('data', []):
                    japanese = item.get('japanese', [])
                    for jp in japanese:
                        if jp.get('word') == word or jp.get('reading') == reading:
                            # Jisho sometimes includes pitch in tags
                            tags = item.get('tags', [])
                            for tag in tags:
                                if 'pitch' in tag.lower():
                                    # Extract number from tag
                                    nums = re.findall(r'\d+', tag)
                                    if nums:
                                        return nums[0]
        except:
            pass
        return '?'

    @staticmethod
    def split_morae(text: str) -> List[str]:
        """Split Japanese text into morae"""
        # Small kana that combine with previous
        small_kana = 'ゃゅょャュョァィゥェォ'

        morae = []
        i = 0
        while i < len(text):
            if i + 1 < len(text) and text[i + 1] in small_kana:
                morae.append(text[i:i+2])
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
            '<style>',
            '  .mora-text { font-family: "Noto Sans JP", sans-serif; font-size: 16px; text-anchor: middle; }',
            '  .pitch-line { stroke: #e74c3c; stroke-width: 2; fill: none; }',
            '  .pitch-dot { fill: #e74c3c; }',
            '</style>',
        ]

        # Draw pitch line
        points = []
        for i, (mora, h) in enumerate(zip(morae, heights)):
            x = 20 + i * mora_width + mora_width // 2
            points.append(f"{x},{h}")

        if len(points) > 1:
            svg_parts.append(f'<polyline class="pitch-line" points="{" ".join(points)}" />')

        # Draw dots and text
        for i, (mora, h) in enumerate(zip(morae, heights)):
            x = 20 + i * mora_width + mora_width // 2
            svg_parts.append(f'<circle class="pitch-dot" cx="{x}" cy="{h}" r="4" />')
            svg_parts.append(f'<text class="mora-text" x="{x}" y="{text_y}">{mora}</text>')

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)


class StrokeOrderAPI:
    """Generate stroke order diagrams using KanjiVG data"""

    KANJIVG_URL = "https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{}.svg"

    @staticmethod
    def get_stroke_order_svg(kanji: str) -> str:
        """Get stroke order SVG for a single kanji"""
        if len(kanji) != 1:
            return ""

        # Get unicode code point
        code = format(ord(kanji), '05x')
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
        svg_content = re.sub(r'<\?xml[^>]*\?>', '', svg_content)
        svg_content = re.sub(r'<!--.*?-->', '', svg_content, flags=re.DOTALL)

        # Remove problematic attributes and elements
        svg_content = re.sub(r'xmlns:kvg="[^"]*"', '', svg_content)
        svg_content = re.sub(r'kvg:[a-z]+="[^"]*"', '', svg_content)

        # CRITICAL: Remove inline fill and stroke attributes for dark mode support
        # This allows CSS to control the colors
        svg_content = re.sub(r'\s+fill="[^"]*"', '', svg_content)
        svg_content = re.sub(r'\s+stroke="[^"]*"', '', svg_content)

        # Keep only essential SVG content
        svg_match = re.search(r'(<svg[^>]*>.*</svg>)', svg_content, re.DOTALL)
        if svg_match:
            svg_content = svg_match.group(1)

        # Set viewBox and size - use class for theme support
        svg_content = re.sub(
            r'<svg([^>]*)>',
            '<svg viewBox="0 0 109 109" width="120" height="120" class="stroke-svg">',
            svg_content
        )

        return svg_content.strip()


class TTSGenerator:
    """Generate audio using Microsoft Edge TTS (better Japanese pronunciation)"""

    # Japanese voice options:
    # ja-JP-NanamiNeural (female, natural)
    # ja-JP-KeitaNeural (male, natural)
    VOICE = "ja-JP-NanamiNeural"

    @staticmethod
    def generate_audio(text: str, output_path: str, lang: str = 'ja') -> bool:
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
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Remove comment key
                data.pop('_comment', None)
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
        return ' '.join(result) if result else ""


# =============================================================================
# 48 BỘ THỦ (RADICALS)
# =============================================================================

class RadicalDB:
    """48 most common radicals database - loads from JSON"""

    RADICALS: Dict[str, Dict] = {}
    _loaded = False

    @classmethod
    def _load(cls):
        """Load data from JSON file"""
        if cls._loaded:
            return

        json_path = Path(__file__).parent / "data" / "radicals.json"
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.pop('_comment', None)
                cls.RADICALS = data
        cls._loaded = True

    @staticmethod
    def identify_radical(kanji: str) -> Dict:
        """Identify the radical of a kanji"""
        RadicalDB._load()

        if kanji in RadicalDB.RADICALS:
            return RadicalDB.RADICALS[kanji]

        for radical, info in RadicalDB.RADICALS.items():
            if radical in kanji:
                return {**info, 'radical': radical}
            for variant in info.get('variants', []):
                if variant in kanji:
                    return {**info, 'radical': radical}

        return {}


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
            with open(json_path, 'r', encoding='utf-8') as f:
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
                return {**cls.FREQ[char], 'kanji': char}
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
            with open(json_path, 'r', encoding='utf-8') as f:
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

    @staticmethod
    def generate(word: str, reading: str) -> str:
        """Generate furigana HTML. Returns <ruby>漢字<rt>かんじ</rt></ruby>"""
        # If word is all hiragana/katakana, no furigana needed
        has_kanji = any('\u4e00' <= c <= '\u9fff' for c in word)
        if not has_kanji:
            return word

        # Simple case: wrap entire word
        # For complex cases with mixed kanji/kana, we'd need morphological analysis
        return f'<ruby>{word}<rt>{reading}</rt></ruby>'

    @staticmethod
    def generate_per_char(word: str, reading: str) -> str:
        """Try to generate per-character furigana (best effort)"""
        # This is a simplified version - full implementation would need MeCab
        has_kanji = any('\u4e00' <= c <= '\u9fff' for c in word)
        if not has_kanji:
            return word

        # If single kanji, simple wrap
        if len(word) == 1:
            return f'<ruby>{word}<rt>{reading}</rt></ruby>'

        # For compound words, wrap entire word (safe fallback)
        return f'<ruby>{word}<rt>{reading}</rt></ruby>'


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
                print("Warning: pykakasi not installed. Run: pip install pykakasi --break-system-packages")
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
                orig = item['orig']
                hira = item['hira']

                # Check if has kanji
                has_kanji = any('\u4e00' <= c <= '\u9fff' for c in orig)

                if has_kanji and orig != hira:
                    html_parts.append(f'<ruby>{orig}<rt>{hira}</rt></ruby>')
                else:
                    html_parts.append(orig)

            return ''.join(html_parts)
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
        'う': {'masu': 'います', 'te': 'って', 'ta': 'った', 'nai': 'わない', 'potential': 'える'},
        'く': {'masu': 'きます', 'te': 'いて', 'ta': 'いた', 'nai': 'かない', 'potential': 'ける'},
        'ぐ': {'masu': 'ぎます', 'te': 'いで', 'ta': 'いだ', 'nai': 'がない', 'potential': 'げる'},
        'す': {'masu': 'します', 'te': 'して', 'ta': 'した', 'nai': 'さない', 'potential': 'せる'},
        'つ': {'masu': 'ちます', 'te': 'って', 'ta': 'った', 'nai': 'たない', 'potential': 'てる'},
        'ぬ': {'masu': 'にます', 'te': 'んで', 'ta': 'んだ', 'nai': 'なない', 'potential': 'ねる'},
        'ぶ': {'masu': 'びます', 'te': 'んで', 'ta': 'んだ', 'nai': 'ばない', 'potential': 'べる'},
        'む': {'masu': 'みます', 'te': 'んで', 'ta': 'んだ', 'nai': 'まない', 'potential': 'める'},
        'る': {'masu': 'ります', 'te': 'って', 'ta': 'った', 'nai': 'らない', 'potential': 'れる'},
    }

    # Irregular verbs
    IRREGULARS = {
        'する': {'masu': 'します', 'te': 'して', 'ta': 'した', 'nai': 'しない', 'potential': 'できる', 'type': 'suru'},
        '来る': {'masu': '来ます', 'te': '来て', 'ta': '来た', 'nai': '来ない', 'potential': '来られる', 'type': 'kuru'},
        'くる': {'masu': 'きます', 'te': 'きて', 'ta': 'きた', 'nai': 'こない', 'potential': 'こられる', 'type': 'kuru'},
        '行く': {'masu': '行きます', 'te': '行って', 'ta': '行った', 'nai': '行かない', 'potential': '行ける', 'type': 'iku'},
        'いく': {'masu': 'いきます', 'te': 'いって', 'ta': 'いった', 'nai': 'いかない', 'potential': 'いける', 'type': 'iku'},
        'ある': {'masu': 'あります', 'te': 'あって', 'ta': 'あった', 'nai': 'ない', 'potential': 'ありえる', 'type': 'aru'},
    }

    # Common ichidan (る) verbs that end in える/いる
    ICHIDAN_COMMON = {
        '食べる', '見る', '起きる', '寝る', '着る', '出る', '開ける', '閉める',
        '教える', '考える', '答える', '忘れる', '覚える', '始める', '終わる',
        'たべる', 'みる', 'おきる', 'ねる', 'きる', 'でる', 'あける', 'しめる',
    }

    @classmethod
    def detect_verb_type(cls, word: str, word_type: str = "") -> str:
        """Detect verb type: ichidan, godan, irregular, or not_verb"""
        # Check if it's marked as a verb (English, Japanese, or Vietnamese)
        verb_markers = ['Verb', '動詞', 'Động từ', 'verb']
        if word_type and not any(m in word_type for m in verb_markers):
            return 'not_verb'

        # Check irregulars first
        if word in cls.IRREGULARS:
            return cls.IRREGULARS[word].get('type', 'irregular')

        # Check if ends with する (suru compound)
        if word.endswith('する'):
            return 'suru'

        # Detect from word_type string
        ichidan_markers = ['Ichidan', 'ichidan', '一段']
        godan_markers = ['Godan', 'godan', '五段']

        if word_type:
            if any(m in word_type for m in ichidan_markers):
                return 'ichidan'
            if any(m in word_type for m in godan_markers):
                return 'godan'

        # Check common ichidan verbs
        if word in cls.ICHIDAN_COMMON:
            return 'ichidan'

        # Check ending
        if not word:
            return 'not_verb'

        last_char = word[-1]

        # Ichidan verbs end in る with え-row or い-row vowel before
        if last_char == 'る' and len(word) >= 2:
            prev_char = word[-2]
            # え-row: え, け, せ, て, ね, へ, め, れ, げ, ぜ, で, べ, ぺ
            e_row = 'えけせてねへめれげぜでべぺ'
            # い-row: い, き, し, ち, に, ひ, み, り, ぎ, じ, ぢ, び, ぴ
            i_row = 'いきしちにひみりぎじぢびぴ'
            if prev_char in e_row or prev_char in i_row:
                # Could be ichidan - but many are actually godan
                # Default to ichidan for common patterns
                return 'ichidan'

        # Godan verbs end in う-row
        if last_char in cls.GODAN_ENDINGS:
            return 'godan'

        return 'not_verb'

    @classmethod
    def conjugate(cls, word: str, reading: str = "", word_type: str = "") -> Dict[str, str]:
        """Conjugate a verb. Returns dict with masu, te, ta, nai, potential forms"""
        verb_type = cls.detect_verb_type(word, word_type)

        if verb_type == 'not_verb':
            return {}

        # Handle irregulars
        if word in cls.IRREGULARS:
            return {k: v for k, v in cls.IRREGULARS[word].items() if k != 'type'}

        # Handle する compounds
        if verb_type == 'suru' and word.endswith('する'):
            stem = word[:-2]
            return {
                'masu': f'{stem}します',
                'te': f'{stem}して',
                'ta': f'{stem}した',
                'nai': f'{stem}しない',
                'potential': f'{stem}できる',
            }

        if not word:
            return {}

        last_char = word[-1]
        stem = word[:-1]

        # Ichidan verbs - just drop る and add endings
        if verb_type == 'ichidan':
            return {
                'masu': f'{stem}ます',
                'te': f'{stem}て',
                'ta': f'{stem}た',
                'nai': f'{stem}ない',
                'potential': f'{stem}られる',
            }

        # Godan verbs
        if verb_type == 'godan' and last_char in cls.GODAN_ENDINGS:
            endings = cls.GODAN_ENDINGS[last_char]
            return {
                'masu': f'{stem}{endings["masu"]}',
                'te': f'{stem}{endings["te"]}',
                'ta': f'{stem}{endings["ta"]}',
                'nai': f'{stem}{endings["nai"]}',
                'potential': f'{stem}{endings["potential"]}',
            }

        return {}

    @classmethod
    def format_conjugations(cls, word: str, reading: str = "", word_type: str = "") -> str:
        """Format conjugations as HTML string"""
        conj = cls.conjugate(word, reading, word_type)
        if not conj:
            return ""

        parts = []
        labels = {'masu': 'ます形', 'te': 'て形', 'ta': 'た形', 'nai': 'ない形', 'potential': '可能形'}
        for key in ['masu', 'te', 'ta', 'nai', 'potential']:
            if key in conj:
                parts.append(f'{labels[key]}: {conj[key]}')

        return ' | '.join(parts)


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
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.pop('_comment', None)
                cls.SENTENCES = data
        cls._loaded = True

    @classmethod
    def get_examples(cls, word: str, limit: int = 2, offline: bool = False) -> List[str]:
        """Get example sentences for a word"""
        cls._load()
        cls.last_api_called = False

        if word in cls.SENTENCES:
            examples = cls.SENTENCES[word][:limit]
            # Format: "日本語 → Tiếng Việt"
            return [f"{jp} → {vi}" for jp, vi in examples]

        # Check cache - use stable hash
        word_hash = hashlib.md5(word.encode()).hexdigest()[:12]
        cache_file = cls._cache_dir / f"{word_hash}.json"
        if cache_file and cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    return cached[:limit]
            except:
                pass

        # Skip API if offline
        if offline:
            return []

        # Fetch from Tatoeba API
        cls.last_api_called = True
        examples = cls._fetch_tatoeba(word, limit)

        # Save to cache (including empty to avoid re-fetching)
        if cache_file:
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(examples, f, ensure_ascii=False)
            except:
                pass

        return examples

    @classmethod
    def _fetch_tatoeba(cls, word: str, limit: int = 2) -> List[str]:
        """Fetch examples from Tatoeba API"""
        try:
            url = f"https://tatoeba.org/en/api_v0/search?from=jpn&to=vie&query={urllib.parse.quote(word)}&limit={limit}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('results', [])[:limit]:
                    jp = item.get('text', '')
                    translations = item.get('translations', [[]])
                    if translations and translations[0]:
                        vi = translations[0][0].get('text', '')
                        if jp and vi:
                            results.append(f"{jp} → {vi}")
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
            with open(json_path, 'r', encoding='utf-8') as f:
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
            'han_viet': [],
            'pinyin': [],
            'kun': [],
            'on': [],
            'tu_ghep': [],
            'chi_tiet': []
        }

        for char in word:
            info = cls.DATABASE.get(char, {})
            if info:
                if info.get('han_viet'):
                    result['han_viet'].append(f"{char}({info['han_viet']})")
                if info.get('pinyin'):
                    result['pinyin'].append(info['pinyin'])
                if info.get('kun'):
                    result['kun'].append(info['kun'])
                if info.get('on'):
                    result['on'].append(info['on'])
                if info.get('tu_ghep'):
                    result['tu_ghep'].extend(info['tu_ghep'][:2])
                if info.get('chi_tiet'):
                    result['chi_tiet'].append(f"【{char}】{info['chi_tiet']}")

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
        css = '''
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
    font-size: 14px;
    color: #9b59b6;
    margin: 10px 0;
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
'''

        # Front template (Question) - pitch ở đây để học phát âm
        front_template = '''
<div class="word">{{Furigana}}</div>
{{#JLPTLevel}}<div class="jlpt-level jlpt-{{JLPTLevel}}">{{JLPTLevel}}</div>{{/JLPTLevel}}
{{#PitchDiagram}}<div class="pitch-diagram">{{PitchDiagram}}</div>{{/PitchDiagram}}
{{#Audio}}{{Audio}}{{/Audio}}
'''

        # Back template (Answer)
        back_template = '''
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
    {{#HanViet}}<div class="hanviet">漢越: {{HanViet}}</div>{{/HanViet}}
    {{#FrequencyInfo}}<div class="frequency-info">Tần suất: {{FrequencyInfo}}</div>{{/FrequencyInfo}}
    {{#Conjugations}}<div class="conjugations">🔄 {{Conjugations}}</div>{{/Conjugations}}
    {{#Synonyms}}<div class="synonyms">≈ Đồng nghĩa: {{Synonyms}}</div>{{/Synonyms}}
    {{#Antonyms}}<div class="antonyms">≠ Trái nghĩa: {{Antonyms}}</div>{{/Antonyms}}
    {{#KanjiChiTiet}}
    <div class="kanji-detail-separator"></div>
    <div class="kanji-detail-title">📚 Chiết tự Hán</div>
    {{#KanjiPinyin}}<div class="kanji-pinyin">🔊 Pinyin: {{KanjiPinyin}}</div>{{/KanjiPinyin}}
    {{#KanjiKun}}<div class="kanji-reading">訓: {{KanjiKun}}</div>{{/KanjiKun}}
    {{#KanjiOn}}<div class="kanji-reading">音: {{KanjiOn}}</div>{{/KanjiOn}}
    {{#KanjiTuGhep}}<div class="kanji-compound">📝 Từ ghép: {{KanjiTuGhep}}</div>{{/KanjiTuGhep}}
    <div class="kanji-etymology">{{KanjiChiTiet}}</div>
    {{/KanjiChiTiet}}
</div>

{{#StrokeOrder}}
<hr>
<div class="stroke-order">{{StrokeOrder}}</div>
{{/StrokeOrder}}

{{#RadicalInfo}}
<div class="radical">Bộ thủ: {{RadicalInfo}}</div>
{{/RadicalInfo}}

{{#Examples}}
<hr>
<div class="example">{{Examples}}</div>
{{/Examples}}

<div class="dictionary-link">
    <a href="{{TakobotoLink}}" target="_blank">📖 Takoboto</a>
</div>

<div class="tags">{{Chapter}} / {{SubCategory}}</div>
'''

        # Reverse card template (Vietnamese → Japanese)
        reverse_front = '''
<div class="meaning meaning-vi" style="font-size: 28px;">🇻🇳 {{MeaningVI}}</div>
{{#MeaningEN}}<div class="meaning meaning-en">🇬🇧 {{MeaningEN}}</div>{{/MeaningEN}}
{{#JLPTLevel}}<div class="jlpt-level jlpt-{{JLPTLevel}}">{{JLPTLevel}}</div>{{/JLPTLevel}}
'''

        reverse_back = '''
<div class="meaning meaning-vi" style="font-size: 28px;">🇻🇳 {{MeaningVI}}</div>
{{#MeaningEN}}<div class="meaning meaning-en">🇬🇧 {{MeaningEN}}</div>{{/MeaningEN}}

<hr>

<div class="word">{{Furigana}}</div>
{{#JLPTLevel}}<div class="jlpt-level jlpt-{{JLPTLevel}}">{{JLPTLevel}}</div>{{/JLPTLevel}}
{{#PitchDiagram}}<div class="pitch-diagram">{{PitchDiagram}}</div>{{/PitchDiagram}}
<div class="romaji">{{Romaji}}</div>

{{#Audio}}{{Audio}}{{/Audio}}

{{#WordType}}<div class="word-type">📗 {{WordType}}</div>{{/WordType}}
{{#HanViet}}<div class="hanviet">漢越: {{HanViet}}</div>{{/HanViet}}
{{#Conjugations}}<div class="conjugations">🔄 {{Conjugations}}</div>{{/Conjugations}}

<div class="dictionary-link">
    <a href="{{TakobotoLink}}" target="_blank">📖 Takoboto</a>
</div>

<div class="tags">{{Chapter}} / {{SubCategory}}</div>
'''

        return genanki.Model(
            self.MODEL_ID,
            'Japanese Vocabulary Enhanced',
            fields=[
                {'name': 'Word'},
                {'name': 'Reading'},
                {'name': 'Romaji'},
                {'name': 'MeaningVI'},
                {'name': 'MeaningEN'},
                {'name': 'HanViet'},
                {'name': 'PitchPattern'},
                {'name': 'PitchDiagram'},
                {'name': 'StrokeOrder'},
                {'name': 'Audio'},
                {'name': 'Examples'},
                {'name': 'RadicalInfo'},
                {'name': 'FrequencyInfo'},
                {'name': 'KanjiPinyin'},
                {'name': 'KanjiKun'},
                {'name': 'KanjiOn'},
                {'name': 'KanjiTuGhep'},
                {'name': 'KanjiChiTiet'},
                {'name': 'Chapter'},
                {'name': 'SubCategory'},
                {'name': 'TakobotoLink'},
                # New fields
                {'name': 'JLPTLevel'},
                {'name': 'WordType'},
                {'name': 'Furigana'},
                {'name': 'Conjugations'},
                {'name': 'Synonyms'},
                {'name': 'Antonyms'},
            ],
            templates=[
                {
                    'name': 'Recognition',
                    'qfmt': front_template,
                    'afmt': back_template,
                },
                {
                    'name': 'Production',
                    'qfmt': reverse_front,
                    'afmt': reverse_back,
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
            entry.chapter.replace(' ', '_'),
            entry.sub_category.replace(' ', '_') if entry.sub_category else '',
        ]
        if entry.jlpt_level:
            tags.append(entry.jlpt_level)  # Add JLPT level as tag for filtering

        # Create note
        note = genanki.Note(
            model=self.model,
            fields=[
                entry.word,
                entry.reading,
                entry.romaji,
                entry.meaning_vi,
                entry.meaning_en,
                entry.han_viet,
                entry.pitch_pattern,
                entry.pitch_svg,
                entry.stroke_order_svg,
                f'[sound:{Path(entry.audio_file).name}]' if entry.audio_file else '',
                entry.examples,
                entry.radical_info,
                entry.frequency_info,
                entry.kanji_pinyin,
                entry.kanji_kun,
                entry.kanji_on,
                entry.kanji_tu_ghep,
                entry.kanji_chi_tiet,
                entry.chapter,
                entry.sub_category,
                entry.takoboto_link,
                # New fields
                entry.jlpt_level,
                entry.word_type,
                entry.furigana,
                entry.conjugations,
                entry.synonyms,
                entry.antonyms,
            ],
            tags=tags
        )

        self.decks[chapter].add_note(note)

        # Track audio file
        if entry.audio_file and os.path.exists(entry.audio_file):
            self.media_files.append(entry.audio_file)

            # Track example audio files (inline in entry.examples)
            if entry.examples:
                import re
                examples_dir = Path(entry.audio_file).parent.parent / "examples"
                for match in re.findall(r'\[sound:([^\]]+)\]', entry.examples):
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
            'total_words': 0,
            'chapters': 0,
            'audio_generated': 0,
            'audio_cached': 0,
            'example_audio_generated': 0,
            'example_audio_cached': 0,
            'stroke_generated': 0,
            'stroke_cached': 0,
            'pitch_found': 0,
            'hanviet_found': 0,
            'chiettu_found': 0,
            'skipped_cached': 0,
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
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.processed = set(data.get('processed', []))
                    print(f"Loaded checkpoint: {len(self.processed)} entries already processed")
            except Exception as e:
                print(f"Warning: Could not load checkpoint: {e}")
                self.processed = set()

    def _save_checkpoint(self):
        """Save checkpoint to file"""
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'processed': list(self.processed),
                    'epub': self.epub_path,
                }, f, ensure_ascii=False, indent=2)
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

    def run(self,
            enrich_english: bool = True,
            generate_audio: bool = True,
            generate_pitch: bool = True,
            generate_stroke: bool = True,
            generate_example: bool = True,
            rate_limit_delay: float = 0.5,
            force_restart: bool = False,
            offline: bool = False,
            verbose: bool = False):
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
        self.stats['chapters'] = len(chapters)
        print(f"Found {len(chapters)} chapters")

        # Phase 2: Enrich and generate
        print("\n[Phase 2] Enriching vocabulary...")

        for chapter_name, entries in chapters.items():
            print(f"\n  Processing: {chapter_name} ({len(entries)} words)")

            for i, entry in enumerate(entries):
                self.stats['total_words'] += 1

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

    def _enrich_entry(self, entry: VocabEntry,
                      enrich_english: bool,
                      generate_audio: bool,
                      generate_pitch: bool,
                      generate_stroke: bool):
        """Enrich a single vocabulary entry"""

        self._last_api_called = False
        api_calls = []

        if self.verbose:
            print(f"      → {entry.word} ({entry.reading})", end="")

        # Kanji database - full info including chiết tự
        kanji_info = KanjiDB.get_word_info(entry.word)

        # Hán Việt from kanji_info
        if kanji_info['han_viet']:
            entry.han_viet = ' '.join(kanji_info['han_viet'])
            self.stats['hanviet_found'] += 1

        # Pinyin
        if kanji_info['pinyin']:
            entry.kanji_pinyin = ', '.join(kanji_info['pinyin'])

        # Kun/On readings
        if kanji_info['kun']:
            entry.kanji_kun = ' | '.join(kanji_info['kun'])
        if kanji_info['on']:
            entry.kanji_on = ' | '.join(kanji_info['on'])

        # Từ ghép (compound words)
        if kanji_info['tu_ghep']:
            tu_ghep_html = []
            for tg in kanji_info['tu_ghep'][:4]:
                if isinstance(tg, dict):
                    tu_ghep_html.append(f"{tg.get('viet', '')} {tg.get('han', '')}")
                else:
                    tu_ghep_html.append(str(tg))
            entry.kanji_tu_ghep = ' • '.join(tu_ghep_html)

        # Chi tiết chiết tự
        if kanji_info['chi_tiet']:
            entry.kanji_chi_tiet = '<br><br>'.join(kanji_info['chi_tiet'][:2])
            self.stats['chiettu_found'] += 1

        # Radical info
        for char in entry.word:
            radical_info = RadicalDB.identify_radical(char)
            if radical_info:
                entry.radical_info = f"{radical_info.get('radical', char)} ({radical_info.get('name_vn', '')} - {radical_info.get('name_en', '')})"
                break

        # Frequency info - handle compound words (each kanji)
        freq_parts = []
        for char in entry.word:
            if '\u4e00' <= char <= '\u9fff':  # Is kanji
                freq = KanjiFrequencyDB.get_frequency(char)
                if freq:
                    tier = freq['tier']
                    rank = freq['rank']
                    freq_parts.append(f'<span class="freq-{tier}">{char} [{tier} #{rank}]</span>')
        if freq_parts:
            entry.frequency_info = ' '.join(freq_parts)

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
        if entry.word_type and ('Động từ' in entry.word_type or 'Verb' in entry.word_type):
            entry.conjugations = VerbConjugator.format_conjugations(entry.word, entry.reading, entry.word_type)

        # === END NEW ENRICHMENTS ===

        # Example sentences - with furigana and inline audio
        if self.generate_example:
            examples = ExampleSentencesDB.get_examples(entry.word, limit=2, offline=self.offline)
            if ExampleSentencesDB.last_api_called:
                self._last_api_called = True
                api_calls.append('EX')
            if examples:
                import re
                examples_final = []
                example_audio_generated = False

                for i, ex in enumerate(examples):
                    if '→' in ex:
                        jp_part, vi_part = ex.split('→', 1)
                        jp_part = jp_part.strip()
                        vi_part = vi_part.strip()

                        # Add furigana
                        jp_with_ruby = SentenceFuriganaGenerator.generate(jp_part)

                        # Generate audio for this sentence (inline at end)
                        audio_tag = ""
                        if generate_audio and not self.offline:
                            ex_hash = hashlib.md5(f"{entry.word}_{i}_{jp_part}".encode()).hexdigest()[:10]
                            ex_audio_filename = f"ex_{ex_hash}.mp3"
                            ex_audio_path = self.examples_audio_dir / ex_audio_filename

                            if ex_audio_path.exists():
                                audio_tag = f" [sound:{ex_audio_filename}]"
                                self.stats['example_audio_cached'] += 1
                            else:
                                if TTSGenerator.generate_audio(jp_part, str(ex_audio_path)):
                                    audio_tag = f" [sound:{ex_audio_filename}]"
                                    self.stats['example_audio_generated'] += 1
                                    example_audio_generated = True

                        # Combine: Japanese (with ruby) → Vietnamese [audio]
                        examples_final.append(f"{jp_with_ruby} → {vi_part}{audio_tag}")
                    else:
                        examples_final.append(ex)

                entry.examples = "<br>".join(examples_final)

                if example_audio_generated:
                    self._last_api_called = True
                    api_calls.append('EX_AUDIO')

        # English meaning (API call) - skip in offline mode
        if enrich_english and not self.offline:
            try:
                entry.meaning_en = JishoAPI.get_english_meaning(entry.word)
                if JishoAPI.last_api_called:
                    self._last_api_called = True
                    api_calls.append('EN')
            except:
                pass

        # Pitch accent - offline mode uses local DB only
        if generate_pitch:
            pattern, morae = PitchAccentAPI.get_pitch_pattern(entry.word, entry.reading, offline=self.offline)
            if PitchAccentAPI.last_api_called:
                self._last_api_called = True
                api_calls.append('PITCH')
            entry.pitch_pattern = pattern
            if pattern != '?':
                self.stats['pitch_found'] += 1
            entry.pitch_svg = PitchDiagramGenerator.generate_svg(entry.reading, pattern, morae)

        # Stroke order - handle compound words (each kanji separately)
        if generate_stroke:
            stroke_svgs = []
            stroke_api_called = False
            for char in entry.word:
                # Skip non-kanji (hiragana, katakana, punctuation)
                if not ('\u4e00' <= char <= '\u9fff'):
                    continue

                stroke_cache_file = self.stroke_dir / f"{ord(char)}.svg"

                if stroke_cache_file.exists():
                    # Load from cache
                    svg = stroke_cache_file.read_text(encoding='utf-8')
                    stroke_svgs.append(svg)
                    self.stats['stroke_cached'] += 1
                elif not self.offline:
                    try:
                        self._last_api_called = True
                        stroke_api_called = True
                        svg = StrokeOrderAPI.get_stroke_order_svg(char)
                        if svg:
                            stroke_svgs.append(svg)
                            # Save to cache
                            stroke_cache_file.write_text(svg, encoding='utf-8')
                            self.stats['stroke_generated'] += 1
                    except:
                        pass

            if stroke_api_called:
                api_calls.append('STROKE')

            # Combine all stroke SVGs
            if stroke_svgs:
                entry.stroke_order_svg = ''.join(stroke_svgs)

        # Audio for word - check if already exists
        if generate_audio:
            audio_filename = f"{hashlib.md5(entry.word.encode()).hexdigest()[:8]}.mp3"
            audio_path = self.words_audio_dir / audio_filename

            if audio_path.exists():
                # Audio already exists, skip generation
                entry.audio_file = str(audio_path)
                self.stats['audio_cached'] += 1
            elif not self.offline:
                self._last_api_called = True
                api_calls.append('AUDIO')
                if TTSGenerator.generate_audio(entry.word, str(audio_path)):
                    entry.audio_file = str(audio_path)
                    self.stats['audio_generated'] += 1

        # Debug: show which APIs were called
        if self.verbose:
            if api_calls:
                print(f" [API: {','.join(api_calls)}]")
            else:
                # Show cached details
                cached_items = []
                if entry.audio_file:
                    cached_items.append('audio')
                if entry.meaning_en:
                    cached_items.append('en')
                if entry.pitch_pattern:
                    cached_items.append('pitch')
                if entry.examples:
                    cached_items.append('ex')
                print(f" [cached: {','.join(cached_items) if cached_items else 'all'}]")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate Anki deck from Japanese vocabulary EPUB')
    parser.add_argument('epub_path', help='Path to EPUB file')
    parser.add_argument('-o', '--output', default='./output', help='Output directory')
    parser.add_argument('--no-english', action='store_true', help='Skip English meanings (faster)')
    parser.add_argument('--no-audio', action='store_true', help='Skip audio generation')
    parser.add_argument('--no-pitch', action='store_true', help='Skip pitch diagrams')
    parser.add_argument('--no-stroke', action='store_true', help='Skip stroke order')
    parser.add_argument('--no-example', action='store_true', help='Skip example sentences')
    parser.add_argument('--delay', type=float, default=0.5, help='API rate limit delay (seconds)')
    parser.add_argument('--force-restart', action='store_true', help='Clear checkpoint and start fresh')
    parser.add_argument('--offline', action='store_true', help='No API calls, use local data only')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print detailed progress')

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