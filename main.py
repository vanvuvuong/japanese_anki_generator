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
    
    def generate_takoboto_link(self):
        """Generate Takoboto dictionary link"""
        encoded = urllib.parse.quote(self.word)
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
            meaning_vi = trans_span.get_text().strip() if trans_span else ""
            
            # Japanese word (Kanji or Kana)
            word_span = div.find('span', class_='top_word')
            word = word_span.get_text().strip() if word_span else ""
            
            # Romaji reading
            post_span = div.find('span', class_='top_post')
            romaji_raw = post_span.get_text().strip() if post_span else ""
            # Remove parentheses
            romaji = romaji_raw.strip('()')
            
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
    
    @staticmethod
    def lookup(word: str) -> Dict:
        """Look up a word in Jisho"""
        try:
            url = f"{JishoAPI.BASE_URL}?keyword={urllib.parse.quote(word)}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    return data['data'][0]
        except Exception as e:
            print(f"Jisho lookup error for {word}: {e}")
        return {}
    
    @staticmethod
    def get_english_meaning(word: str) -> str:
        """Get English meaning from Jisho"""
        data = JishoAPI.lookup(word)
        if data and 'senses' in data:
            meanings = []
            for sense in data['senses'][:2]:  # First 2 senses
                if 'english_definitions' in sense:
                    meanings.extend(sense['english_definitions'][:3])
            return "; ".join(meanings)
        return ""


class PitchAccentAPI:
    """Fetch pitch accent data"""
    
    # Common pitch patterns database (subset)
    # Format: word -> (pattern_number, mora_list)
    # Pattern 0 = 平板型 (heiban), 1+ = accent on that mora
    PITCH_DB = {
        # This would be populated from OJAD or similar database
        # Example entries:
        '犬': ('2', ['い', 'ぬ']),
        '猫': ('1', ['ね', 'こ']),
        '行く': ('0', ['い', 'く']),
        '食べる': ('2', ['た', 'べ', 'る']),
    }
    
    @staticmethod
    def get_pitch_pattern(word: str, reading: str) -> Tuple[str, List[str]]:
        """Get pitch pattern for a word"""
        if word in PitchAccentAPI.PITCH_DB:
            return PitchAccentAPI.PITCH_DB[word]
        
        # Default: return morae from reading with unknown pattern
        morae = PitchAccentAPI.split_morae(reading)
        return ('?', morae)
    
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
        """Add stroke numbers to SVG"""
        # Parse SVG and add numbers at stroke midpoints
        # This is a simplified version - full implementation would parse paths
        return svg_content


class TTSGenerator:
    """Generate audio using TTS"""
    
    @staticmethod
    def generate_audio(text: str, output_path: str, lang: str = 'ja') -> bool:
        """Generate TTS audio file using gTTS"""
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang=lang)
            tts.save(output_path)
            return True
        except ImportError:
            print("Installing gTTS...")
            os.system("pip install gTTS --break-system-packages")
            try:
                from gtts import gTTS
                tts = gTTS(text=text, lang=lang)
                tts.save(output_path)
                return True
            except Exception as e:
                print(f"TTS error: {e}")
                return False
        except Exception as e:
            print(f"TTS error for {text}: {e}")
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
.card {
    font-family: "Noto Sans JP", "Yu Gothic", "Hiragino Sans", sans-serif;
    font-size: 20px;
    text-align: center;
    color: #333;
    background-color: #fafafa;
    padding: 20px;
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
}

.meaning-en {
    color: #3498db;
}

.hanviet {
    font-size: 18px;
    color: #e74c3c;
    margin: 10px 0;
    font-style: italic;
}

.pitch-diagram {
    margin: 15px auto;
    display: block;
}

.stroke-order {
    margin: 15px auto;
    max-width: 200px;
}

.example {
    font-size: 16px;
    color: #555;
    text-align: left;
    margin: 10px 20px;
    padding: 10px;
    background: #ecf0f1;
    border-radius: 5px;
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
        
        # Front template (Question)
        front_template = '''
<div class="word">{{Word}}</div>
{{#Reading}}<div class="reading">{{Reading}}</div>{{/Reading}}
{{#Audio}}{{Audio}}{{/Audio}}
'''
        
        # Back template (Answer)
        back_template = '''
<div class="word">{{Word}}</div>
<div class="reading">{{Reading}}</div>
<div class="romaji">{{Romaji}}</div>

{{#Audio}}{{Audio}}{{/Audio}}

<hr>

<div class="meaning meaning-vi">🇻🇳 {{MeaningVI}}</div>
{{#MeaningEN}}<div class="meaning meaning-en">🇬🇧 {{MeaningEN}}</div>{{/MeaningEN}}
{{#HanViet}}<div class="hanviet">漢越: {{HanViet}}</div>{{/HanViet}}

{{#PitchDiagram}}
<hr>
<div class="pitch-diagram">{{PitchDiagram}}</div>
{{/PitchDiagram}}

{{#StrokeOrder}}
<hr>
<div class="stroke-order">{{StrokeOrder}}</div>
{{/StrokeOrder}}

{{#RadicalInfo}}
<div class="radical">Bộ thủ: {{RadicalInfo}}</div>
{{/RadicalInfo}}

{{#KanjiOrigin}}
<div class="origin">{{KanjiOrigin}}</div>
{{/KanjiOrigin}}

{{#Examples}}
<hr>
<div class="example">{{Examples}}</div>
{{/Examples}}

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
                {'name': 'KanjiOrigin'},
                {'name': 'Chapter'},
                {'name': 'SubCategory'},
                {'name': 'TakobotoLink'},
            ],
            templates=[
                {
                    'name': 'Recognition',
                    'qfmt': front_template,
                    'afmt': back_template,
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
                f'[sound:{entry.audio_file}]' if entry.audio_file else '',
                '<br>'.join(entry.example_sentences),
                entry.radical_info,
                entry.kanji_origin,
                entry.chapter,
                entry.sub_category,
                entry.takoboto_link,
            ],
            tags=[
                entry.chapter.replace(' ', '_'),
                entry.sub_category.replace(' ', '_') if entry.sub_category else '',
            ]
        )
        
        self.decks[chapter].add_note(note)
        
        # Track audio file
        if entry.audio_file and os.path.exists(entry.audio_file):
            self.media_files.append(entry.audio_file)
    
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
        self.audio_dir = self.output_dir / "audio"
        self.audio_dir.mkdir(exist_ok=True)
        
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
            'pitch_found': 0,
            'hanviet_found': 0,
            'skipped_cached': 0,
        }
    
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
    
    def _get_entry_key(self, entry: VocabEntry) -> str:
        """Generate unique key for an entry"""
        return f"{entry.chapter}::{entry.word}::{entry.meaning_vi}"
    
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
            rate_limit_delay: float = 0.5,
            force_restart: bool = False):
        """Run the full pipeline"""
        
        if force_restart:
            self.clear_checkpoint()
        
        print("=" * 60)
        print("JAPANESE VOCABULARY ANKI DECK GENERATOR")
        print("=" * 60)
        
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
                entry_key = self._get_entry_key(entry)
                
                # Skip if already processed
                if entry_key in self.processed:
                    self.stats['skipped_cached'] += 1
                    # Still add to deck (without re-enriching)
                    self.deck_generator.add_entry(entry, chapter_name)
                    continue
                
                self.stats['total_words'] += 1
                
                # Progress indicator
                if (i + 1) % 20 == 0:
                    print(f"    {i + 1}/{len(entries)} processed...")
                
                # Enrich entry
                self._enrich_entry(
                    entry,
                    enrich_english=enrich_english,
                    generate_audio=generate_audio,
                    generate_pitch=generate_pitch,
                    generate_stroke=generate_stroke,
                )
                
                # Add to deck
                self.deck_generator.add_entry(entry, chapter_name)
                
                # Mark as processed & save checkpoint
                self.processed.add(entry_key)
                
                # Save checkpoint every 10 entries
                if len(self.processed) % 10 == 0:
                    self._save_checkpoint()
                
                # Rate limiting for API calls
                if enrich_english or generate_audio:
                    time.sleep(rate_limit_delay)
        
        # Final checkpoint save
        self._save_checkpoint()
        
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
        print(f"Skipped (cached): {self.stats['skipped_cached']}")
        print(f"Audio files generated: {self.stats['audio_generated']}")
        print(f"Pitch patterns found: {self.stats['pitch_found']}")
        print(f"Hán Việt found: {self.stats['hanviet_found']}")
        print(f"\nOutput: {output_path}")
        print(f"Checkpoint: {self.checkpoint_file}")
        
        return str(output_path)
    
    def _enrich_entry(self, entry: VocabEntry,
                      enrich_english: bool,
                      generate_audio: bool,
                      generate_pitch: bool,
                      generate_stroke: bool):
        """Enrich a single vocabulary entry"""
        
        # Hán Việt
        entry.han_viet = HanVietDB.get_hanviet(entry.word)
        if entry.han_viet:
            self.stats['hanviet_found'] += 1
        
        # Radical info
        for char in entry.word:
            radical_info = RadicalDB.identify_radical(char)
            if radical_info:
                entry.radical_info = f"{radical_info.get('radical', char)} ({radical_info.get('name_vn', '')} - {radical_info.get('name_en', '')})"
                break
        
        # English meaning (API call)
        if enrich_english:
            try:
                entry.meaning_en = JishoAPI.get_english_meaning(entry.word)
            except:
                pass
        
        # Pitch accent
        if generate_pitch:
            pattern, morae = PitchAccentAPI.get_pitch_pattern(entry.word, entry.reading)
            entry.pitch_pattern = pattern
            if pattern != '?':
                self.stats['pitch_found'] += 1
            entry.pitch_svg = PitchDiagramGenerator.generate_svg(entry.reading, pattern, morae)
        
        # Stroke order (only for single kanji)
        if generate_stroke and len(entry.word) == 1:
            try:
                entry.stroke_order_svg = StrokeOrderAPI.get_stroke_order_svg(entry.word)
            except:
                pass
        
        # Audio
        if generate_audio:
            audio_filename = f"{hashlib.md5(entry.word.encode()).hexdigest()[:8]}.mp3"
            audio_path = self.audio_dir / audio_filename
            if TTSGenerator.generate_audio(entry.word, str(audio_path)):
                entry.audio_file = str(audio_path)
                self.stats['audio_generated'] += 1


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
    parser.add_argument('--delay', type=float, default=0.5, help='API rate limit delay (seconds)')
    parser.add_argument('--force-restart', action='store_true', help='Clear checkpoint and start fresh')
    
    args = parser.parse_args()
    
    pipeline = JapaneseVocabPipeline(args.epub_path, args.output)
    pipeline.run(
        enrich_english=not args.no_english,
        generate_audio=not args.no_audio,
        generate_pitch=not args.no_pitch,
        generate_stroke=not args.no_stroke,
        rate_limit_delay=args.delay,
        force_restart=args.force_restart,
    )


if __name__ == "__main__":
    main()
