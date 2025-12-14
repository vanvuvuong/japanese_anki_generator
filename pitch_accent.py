#!/usr/bin/env python3
"""
Pitch Accent Module
===================
Fetch and generate pitch accent diagrams similar to Takoboto/JapanDict
"""

import re
import urllib.parse
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import os
    os.system("pip install requests beautifulsoup4 --break-system-packages")
    import requests
    from bs4 import BeautifulSoup


@dataclass
class PitchData:
    """Pitch accent data for a word"""
    word: str
    reading: str
    morae: List[str]
    pattern: int  # 0 = heiban, 1+ = downstep position, -1 = unknown
    pattern_name: str  # 平板型, 頭高型, 中高型, 尾高型

    def __post_init__(self):
        if not self.morae:
            self.morae = split_morae(self.reading)
        self._set_pattern_name()

    def _set_pattern_name(self):
        n = len(self.morae)
        if self.pattern == 0:
            self.pattern_name = "平板型 (Heiban)"
        elif self.pattern == 1:
            self.pattern_name = "頭高型 (Atamadaka)"
        elif self.pattern == n:
            self.pattern_name = "尾高型 (Odaka)"
        elif 1 < self.pattern < n:
            self.pattern_name = "中高型 (Nakadaka)"
        else:
            self.pattern_name = "Unknown"


def split_morae(text: str) -> List[str]:
    """
    Split Japanese text into morae (timing units)

    Rules:
    - Small kana (ゃゅょ etc.) combine with previous
    - っ (geminate) is its own mora
    - ー (long vowel mark) is its own mora
    """
    if not text:
        return []

    # Small kana that combine with previous character
    small_kana = set('ゃゅょャュョァィゥェォぁぃぅぇぉ')

    morae = []
    i = 0

    while i < len(text):
        char = text[i]

        # Check if next char is small kana (combines with current)
        if i + 1 < len(text) and text[i + 1] in small_kana:
            morae.append(text[i:i + 2])
            i += 2
        else:
            morae.append(char)
            i += 1

    return morae


def get_pitch_heights(pattern: int, num_morae: int) -> List[bool]:
    """
    Get pitch heights for each mora

    Returns list of booleans: True = high, False = low

    Pitch patterns:
    - 0 (Heiban): Low-High-High-High... (no drop, continues high after word)
    - 1 (Atamadaka): High-Low-Low-Low...
    - n (Odaka): Low-High-High...-High-[drop after word]
    - 2~n-1 (Nakadaka): Low-High...-High-Low...
    """
    if num_morae == 0:
        return []

    heights = []

    if pattern == 0:
        # 平板型: First mora low, rest high
        heights = [False] + [True] * (num_morae - 1)
    elif pattern == 1:
        # 頭高型: First mora high, rest low
        heights = [True] + [False] * (num_morae - 1)
    elif pattern > 0:
        # 中高型 or 尾高型: Low, then high until pattern position, then low
        heights = [False]  # First mora always low
        for i in range(1, num_morae):
            if i < pattern:
                heights.append(True)
            else:
                heights.append(False)
    else:
        # Unknown - return all high
        heights = [True] * num_morae

    return heights


class PitchSVGGenerator:
    """Generate pitch accent diagram as SVG"""

    # Style constants
    MORA_WIDTH = 35
    PADDING_X = 15
    PADDING_Y = 15
    HIGH_Y = 25
    LOW_Y = 55
    TEXT_Y = 80
    DOT_RADIUS = 5
    LINE_COLOR = "#e74c3c"
    DOT_COLOR = "#e74c3c"
    TEXT_COLOR = "#333"
    FONT_SIZE = 18

    @classmethod
    def generate(cls,
                 reading: str,
                 pattern: int,
                 morae: Optional[List[str]] = None,
                 show_particle: bool = True) -> str:
        """
        Generate SVG pitch diagram

        Args:
            reading: Hiragana reading
            pattern: Pitch pattern number
            morae: Pre-split morae (optional)
            show_particle: Whether to show particle pitch indicator

        Returns:
            SVG string
        """
        if not morae:
            morae = split_morae(reading)

        if not morae:
            return ""

        num_morae = len(morae)

        # Add particle indicator for heiban/odaka distinction
        extra_mora = 1 if show_particle else 0
        total_units = num_morae + extra_mora

        # Calculate dimensions
        width = cls.PADDING_X * 2 + cls.MORA_WIDTH * total_units
        height = cls.TEXT_Y + 15

        # Get pitch heights
        heights = get_pitch_heights(pattern, num_morae)

        # Add particle height (low after heiban continues high, others go low)
        if show_particle:
            if pattern == 0:
                # Heiban: particle is high (no drop)
                heights.append(True)
            else:
                # All others: particle is low
                heights.append(False)

        # Build SVG
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
            '<style>',
            f'  .pitch-line {{ stroke: {cls.LINE_COLOR}; stroke-width: 2.5; fill: none; stroke-linecap: round; stroke-linejoin: round; }}',
            f'  .pitch-dot {{ fill: {cls.DOT_COLOR}; }}',
            f'  .mora-text {{ font-family: "Noto Sans JP", "Yu Gothic", sans-serif; font-size: {cls.FONT_SIZE}px; text-anchor: middle; fill: {cls.TEXT_COLOR}; }}',
            f'  .particle-text {{ font-family: "Noto Sans JP", sans-serif; font-size: {cls.FONT_SIZE - 4}px; text-anchor: middle; fill: #999; }}',
            '</style>',
        ]

        # Calculate points
        points = []
        for i in range(len(heights)):
            x = cls.PADDING_X + i * cls.MORA_WIDTH + cls.MORA_WIDTH // 2
            y = cls.HIGH_Y if heights[i] else cls.LOW_Y
            points.append((x, y))

        # Draw connecting line
        if len(points) > 1:
            path_d = f"M {points[0][0]} {points[0][1]}"
            for x, y in points[1:]:
                path_d += f" L {x} {y}"
            svg_parts.append(f'<path class="pitch-line" d="{path_d}" />')

        # Draw dots and text for actual morae
        for i, mora in enumerate(morae):
            x = cls.PADDING_X + i * cls.MORA_WIDTH + cls.MORA_WIDTH // 2
            y = cls.HIGH_Y if heights[i] else cls.LOW_Y
            svg_parts.append(f'<circle class="pitch-dot" cx="{x}" cy="{y}" r="{cls.DOT_RADIUS}" />')
            svg_parts.append(f'<text class="mora-text" x="{x}" y="{cls.TEXT_Y}">{mora}</text>')

        # Draw particle indicator (if showing)
        if show_particle:
            i = num_morae
            x = cls.PADDING_X + i * cls.MORA_WIDTH + cls.MORA_WIDTH // 2
            y = cls.HIGH_Y if heights[i] else cls.LOW_Y
            # Hollow dot for particle
            svg_parts.append(f'<circle cx="{x}" cy="{y}" r="{cls.DOT_RADIUS}" fill="none" stroke="{cls.DOT_COLOR}" stroke-width="2" />')
            svg_parts.append(f'<text class="particle-text" x="{x}" y="{cls.TEXT_Y}">(が)</text>')

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)

    @classmethod
    def generate_comparison(cls,
                           word: str,
                           readings: List[Tuple[str, int]]) -> str:
        """
        Generate comparison diagram for words with multiple readings
        (like 行く: いく vs ゆく)

        Args:
            word: The kanji word
            readings: List of (reading, pattern) tuples

        Returns:
            SVG string with multiple pitch patterns
        """
        if not readings:
            return ""

        svgs = []
        for reading, pattern in readings:
            svg = cls.generate(reading, pattern)
            svgs.append(svg)

        # Could combine into single SVG if needed
        return '<div class="pitch-comparison">' + ''.join(svgs) + '</div>'


class TakobotoScraper:
    """Scrape pitch accent data from Takoboto"""

    BASE_URL = "https://takoboto.jp/"

    @classmethod
    def lookup(cls, word: str) -> Optional[PitchData]:
        """
        Look up pitch accent from Takoboto

        Note: This is for educational purposes.
        Consider using their API if available or caching results.
        """
        try:
            url = f"{cls.BASE_URL}?q={urllib.parse.quote(word)}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; educational scraper)'
            }
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                return None

            return cls._parse_response(word, response.text)

        except Exception as e:
            print(f"Takoboto lookup error for {word}: {e}")
            return None

    @classmethod
    def _parse_response(cls, word: str, html: str) -> Optional[PitchData]:
        """Parse Takoboto HTML response for pitch data"""
        soup = BeautifulSoup(html, 'html.parser')

        # Look for pitch accent indicators
        # Takoboto uses specific CSS classes for pitch visualization
        # This is a simplified parser - actual implementation would need
        # to analyze the specific HTML structure

        # Find reading
        reading_elem = soup.find('span', class_='kana')
        reading = reading_elem.get_text() if reading_elem else ""

        # Find pitch pattern (would need to analyze their specific markup)
        # For now, return unknown

        if reading:
            return PitchData(
                word=word,
                reading=reading,
                morae=split_morae(reading),
                pattern=-1  # Unknown - would need actual parsing
            )

        return None


class JapanDictScraper:
    """Scrape pitch accent from JapanDict"""

    BASE_URL = "https://www.japandict.com/"

    @classmethod
    def lookup(cls, word: str) -> Optional[PitchData]:
        """Look up pitch accent from JapanDict"""
        try:
            url = f"{cls.BASE_URL}?s={urllib.parse.quote(word)}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; educational scraper)'
            }
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                return None

            return cls._parse_response(word, response.text)

        except Exception as e:
            print(f"JapanDict lookup error for {word}: {e}")
            return None

    @classmethod
    def _parse_response(cls, word: str, html: str) -> Optional[PitchData]:
        """Parse JapanDict HTML response"""
        # Similar to Takoboto parser
        soup = BeautifulSoup(html, 'html.parser')

        # JapanDict has pitch diagrams with specific visual indicators
        # Would need to parse their specific HTML structure

        return None


class OfflinePitchDB:
    """
    Offline pitch accent database
    Built from OJAD (Online Japanese Accent Dictionary) data
    """

    # This would be populated from OJAD dump or similar source
    # Format: word -> (reading, pattern)
    DATABASE: Dict[str, List[Tuple[str, int]]] = {
        # Common verbs
        '行く': [('いく', 0), ('ゆく', 0)],
        '来る': [('くる', 1)],
        '食べる': [('たべる', 2)],
        '飲む': [('のむ', 1)],
        '見る': [('みる', 1)],
        '聞く': [('きく', 0)],
        '話す': [('はなす', 2)],
        '読む': [('よむ', 1)],
        '書く': [('かく', 1)],
        '買う': [('かう', 0)],
        '売る': [('うる', 0)],
        '作る': [('つくる', 2)],
        '使う': [('つかう', 0)],
        '思う': [('おもう', 2)],
        '考える': [('かんがえる', 4)],
        '分かる': [('わかる', 2)],
        '知る': [('しる', 0)],
        '覚える': [('おぼえる', 3)],
        '忘れる': [('わすれる', 0)],
        '始める': [('はじめる', 0)],
        '終わる': [('おわる', 0)],
        '開ける': [('あける', 0)],
        '閉める': [('しめる', 2)],
        '入る': [('はいる', 1)],
        '出る': [('でる', 1)],
        '帰る': [('かえる', 1)],
        '待つ': [('まつ', 1)],
        '持つ': [('もつ', 1)],
        '走る': [('はしる', 2)],
        '歩く': [('あるく', 2)],
        '泳ぐ': [('およぐ', 2)],
        '飛ぶ': [('とぶ', 0)],
        '遊ぶ': [('あそぶ', 0)],
        '働く': [('はたらく', 0)],
        '休む': [('やすむ', 2)],
        '寝る': [('ねる', 0)],
        '起きる': [('おきる', 2)],
        '住む': [('すむ', 1)],
        '着る': [('きる', 0)],
        '脱ぐ': [('ぬぐ', 1)],
        '洗う': [('あらう', 0)],

        # Common nouns
        '犬': [('いぬ', 2)],
        '猫': [('ねこ', 1)],
        '鳥': [('とり', 0)],
        '魚': [('さかな', 0)],
        '牛': [('うし', 0)],
        '馬': [('うま', 2)],
        '豚': [('ぶた', 0)],
        '羊': [('ひつじ', 0)],
        '熊': [('くま', 2)],
        '虎': [('とら', 0)],
        '象': [('ぞう', 1)],
        '猿': [('さる', 1)],
        '蛇': [('へび', 1)],
        '亀': [('かめ', 1)],
        '蝶': [('ちょう', 1)],
        '蜂': [('はち', 1)],
        '蚊': [('か', 0)],
        '蟻': [('あり', 0)],

        # Food
        '水': [('みず', 0)],
        '米': [('こめ', 2)],
        '肉': [('にく', 2)],
        '魚': [('さかな', 0)],
        '野菜': [('やさい', 0)],
        '果物': [('くだもの', 2)],
        '卵': [('たまご', 2)],
        '牛乳': [('ぎゅうにゅう', 0)],
        '茶': [('ちゃ', 0)],
        '酒': [('さけ', 0)],
        '塩': [('しお', 2)],
        '砂糖': [('さとう', 2)],
        '醤油': [('しょうゆ', 0)],

        # Body
        '頭': [('あたま', 3)],
        '顔': [('かお', 0)],
        '目': [('め', 1)],
        '耳': [('みみ', 2)],
        '鼻': [('はな', 0)],
        '口': [('くち', 0)],
        '手': [('て', 1)],
        '足': [('あし', 2)],
        '体': [('からだ', 0)],
        '心': [('こころ', 2)],

        # Nature
        '山': [('やま', 2)],
        '川': [('かわ', 2)],
        '海': [('うみ', 1)],
        '空': [('そら', 1)],
        '雲': [('くも', 1)],
        '雨': [('あめ', 1)],
        '雪': [('ゆき', 2)],
        '風': [('かぜ', 0)],
        '花': [('はな', 2)],
        '木': [('き', 1)],
        '森': [('もり', 0)],
        '石': [('いし', 2)],
        '土': [('つち', 2)],
        '火': [('ひ', 1)],

        # Time
        '今日': [('きょう', 1)],
        '明日': [('あした', 3), ('あす', 1)],
        '昨日': [('きのう', 2)],
        '朝': [('あさ', 1)],
        '昼': [('ひる', 2)],
        '夜': [('よる', 1)],
        '今': [('いま', 1)],
        '後': [('あと', 1)],
        '前': [('まえ', 1)],

        # Adjectives (i-adjectives)
        '大きい': [('おおきい', 3)],
        '小さい': [('ちいさい', 3)],
        '高い': [('たかい', 2)],
        '安い': [('やすい', 2)],
        '新しい': [('あたらしい', 4)],
        '古い': [('ふるい', 2)],
        '良い': [('いい', 1), ('よい', 1)],
        '悪い': [('わるい', 2)],
        '長い': [('ながい', 2)],
        '短い': [('みじかい', 3)],
        '広い': [('ひろい', 2)],
        '狭い': [('せまい', 2)],
        '暑い': [('あつい', 2)],
        '寒い': [('さむい', 2)],
        '熱い': [('あつい', 2)],
        '冷たい': [('つめたい', 3)],
        '甘い': [('あまい', 0)],
        '辛い': [('からい', 2)],
        '美味しい': [('おいしい', 0)],
        '不味い': [('まずい', 2)],
    }

    @classmethod
    def lookup(cls, word: str) -> Optional[List[Tuple[str, int]]]:
        """Look up pitch data from offline database"""
        return cls.DATABASE.get(word)

    @classmethod
    def get_pitch_data(cls, word: str, reading: str = "") -> Optional[PitchData]:
        """Get PitchData object for a word"""
        data = cls.lookup(word)
        if not data:
            return None

        # If reading specified, find matching entry
        if reading:
            for r, p in data:
                if r == reading:
                    return PitchData(word=word, reading=r, morae=split_morae(r), pattern=p)

        # Return first reading
        r, p = data[0]
        return PitchData(word=word, reading=r, morae=split_morae(r), pattern=p)


class PitchAccentService:
    """
    Combined service for pitch accent lookup
    Tries multiple sources in order
    """

    @classmethod
    def lookup(cls, word: str, reading: str = "") -> Optional[PitchData]:
        """
        Look up pitch accent, trying sources in order:
        1. Offline database (fastest)
        2. Takoboto (online)
        3. JapanDict (online)
        """
        # Try offline first
        data = OfflinePitchDB.get_pitch_data(word, reading)
        if data and data.pattern >= 0:
            return data

        # Try online sources (uncomment when needed)
        # data = TakobotoScraper.lookup(word)
        # if data and data.pattern >= 0:
        #     return data

        # data = JapanDictScraper.lookup(word)
        # if data and data.pattern >= 0:
        #     return data

        # Return unknown pattern
        if reading:
            morae = split_morae(reading)
            return PitchData(word=word, reading=reading, morae=morae, pattern=-1)

        return None

    @classmethod
    def generate_svg(cls, word: str, reading: str = "") -> str:
        """Generate SVG diagram for a word"""
        data = cls.lookup(word, reading)
        if not data:
            return ""

        return PitchSVGGenerator.generate(
            reading=data.reading,
            pattern=data.pattern,
            morae=data.morae
        )


# =============================================================================
# DEMO / TEST
# =============================================================================

def demo():
    """Demonstrate pitch accent generation"""

    test_words = [
        ('行く', 'いく'),
        ('食べる', 'たべる'),
        ('犬', 'いぬ'),
        ('猫', 'ねこ'),
        ('水', 'みず'),
        ('山', 'やま'),
        ('大きい', 'おおきい'),
    ]

    print("=" * 60)
    print("PITCH ACCENT DEMO")
    print("=" * 60)

    for word, reading in test_words:
        data = PitchAccentService.lookup(word, reading)
        if data:
            print(f"\n{word} ({reading})")
            print(f"  Pattern: {data.pattern} - {data.pattern_name}")
            print(f"  Morae: {data.morae}")

            # Generate SVG
            svg = PitchSVGGenerator.generate(reading, data.pattern, data.morae)
            print(f"  SVG generated: {len(svg)} chars")

    # Generate sample HTML for visual testing
    html_parts = ['<!DOCTYPE html><html><head>',
                  '<meta charset="UTF-8">',
                  '<title>Pitch Accent Demo</title>',
                  '<style>body { font-family: sans-serif; padding: 20px; }',
                  '.word { margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 8px; }',
                  '.word h3 { margin: 0 0 10px 0; }',
                  '</style>',
                  '</head><body>',
                  '<h1>Pitch Accent Diagrams</h1>']

    for word, reading in test_words:
        data = PitchAccentService.lookup(word, reading)
        if data:
            svg = PitchSVGGenerator.generate(reading, data.pattern, data.morae)
            html_parts.append(f'''
            <div class="word">
                <h3>{word} ({reading}) - {data.pattern_name}</h3>
                {svg}
            </div>
            ''')

    html_parts.append('</body></html>')

    # Save demo HTML
    with open('/home/claude/japanese_anki/pitch_demo.html', 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))

    print(f"\n\nDemo HTML saved to: /home/claude/japanese_anki/pitch_demo.html")


if __name__ == "__main__":
    demo()
