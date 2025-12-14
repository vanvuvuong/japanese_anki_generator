#!/usr/bin/env python3
"""
Stroke Order Module
===================
Generate stroke order diagrams using KanjiVG data
"""

import os
import re
import urllib.request
from typing import Optional, Dict, List
from pathlib import Path

try:
    import requests
except ImportError:
    os.system("pip install requests --break-system-packages")
    import requests


class KanjiVGFetcher:
    """Fetch stroke order SVG from KanjiVG repository"""
    
    # GitHub raw content URL
    KANJIVG_RAW = "https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{}.svg"
    
    # Cache directory
    CACHE_DIR = Path("./cache/kanjivg")
    
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        if use_cache:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def get_svg(self, kanji: str) -> Optional[str]:
        """
        Get stroke order SVG for a single kanji character
        
        Args:
            kanji: Single kanji character
            
        Returns:
            SVG string or None if not found
        """
        if len(kanji) != 1:
            return None
        
        # Get unicode code point (5 hex digits, zero-padded)
        code = format(ord(kanji), '05x')
        
        # Check cache first
        if self.use_cache:
            cache_path = self.CACHE_DIR / f"{code}.svg"
            if cache_path.exists():
                return cache_path.read_text(encoding='utf-8')
        
        # Fetch from GitHub
        try:
            url = self.KANJIVG_RAW.format(code)
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                svg = response.text
                
                # Cache it
                if self.use_cache:
                    cache_path.write_text(svg, encoding='utf-8')
                
                return svg
                
        except Exception as e:
            print(f"Error fetching stroke order for {kanji}: {e}")
        
        return None


class StrokeOrderProcessor:
    """Process KanjiVG SVG to add stroke numbers and styling"""
    
    @staticmethod
    def process(svg_content: str, 
                add_numbers: bool = True,
                colorize: bool = True,
                width: int = 150,
                height: int = 150) -> str:
        """
        Process KanjiVG SVG for display
        
        Args:
            svg_content: Original KanjiVG SVG
            add_numbers: Add stroke numbers
            colorize: Add color gradient to strokes
            width: Output width
            height: Output height
            
        Returns:
            Processed SVG string
        """
        if not svg_content:
            return ""
        
        # Parse viewBox from original
        viewbox_match = re.search(r'viewBox="([^"]+)"', svg_content)
        viewbox = viewbox_match.group(1) if viewbox_match else "0 0 109 109"
        
        # Extract path elements
        paths = re.findall(r'<path[^>]+d="([^"]+)"[^>]*/>', svg_content)
        
        if not paths:
            # Try alternate format
            paths = re.findall(r'd="([^"]+)"', svg_content)
        
        if not paths:
            return svg_content  # Return original if can't parse
        
        # Build new SVG
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="{width}" height="{height}">',
            '<style>',
            '  .stroke { fill: none; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }',
            '  .stroke-num { font-family: sans-serif; font-size: 10px; fill: #e74c3c; font-weight: bold; }',
            '</style>',
        ]
        
        # Color gradient for strokes (dark to light)
        num_strokes = len(paths)
        
        for i, path_d in enumerate(paths):
            # Calculate color (gradient from dark gray to light gray)
            if colorize:
                gray_value = int(50 + (150 * i / max(num_strokes - 1, 1)))
                color = f"rgb({gray_value},{gray_value},{gray_value})"
            else:
                color = "#333"
            
            svg_parts.append(f'<path class="stroke" d="{path_d}" stroke="{color}" />')
            
            # Add stroke number
            if add_numbers:
                # Try to get starting point of path
                start_match = re.match(r'M\s*([\d.]+)[,\s]+([\d.]+)', path_d)
                if start_match:
                    x = float(start_match.group(1))
                    y = float(start_match.group(2))
                    svg_parts.append(f'<text class="stroke-num" x="{x-5}" y="{y-5}">{i+1}</text>')
        
        svg_parts.append('</svg>')
        
        return '\n'.join(svg_parts)


class StrokeOrderGenerator:
    """Main class to generate stroke order diagrams"""
    
    def __init__(self, use_cache: bool = True):
        self.fetcher = KanjiVGFetcher(use_cache=use_cache)
    
    def generate(self, kanji: str, 
                 width: int = 150,
                 height: int = 150,
                 add_numbers: bool = True,
                 colorize: bool = True) -> str:
        """
        Generate stroke order diagram for a kanji
        
        Args:
            kanji: Single kanji character
            width: SVG width
            height: SVG height
            add_numbers: Show stroke numbers
            colorize: Color gradient for strokes
            
        Returns:
            SVG string
        """
        svg = self.fetcher.get_svg(kanji)
        if not svg:
            return ""
        
        return StrokeOrderProcessor.process(
            svg,
            add_numbers=add_numbers,
            colorize=colorize,
            width=width,
            height=height
        )
    
    def generate_animated(self, kanji: str, 
                          width: int = 200,
                          height: int = 200,
                          stroke_duration: float = 0.5) -> str:
        """
        Generate animated stroke order diagram
        
        Uses CSS animations to draw strokes one by one
        """
        svg = self.fetcher.get_svg(kanji)
        if not svg:
            return ""
        
        # Extract paths
        paths = re.findall(r'd="([^"]+)"', svg)
        if not paths:
            return ""
        
        viewbox_match = re.search(r'viewBox="([^"]+)"', svg)
        viewbox = viewbox_match.group(1) if viewbox_match else "0 0 109 109"
        
        num_strokes = len(paths)
        total_duration = stroke_duration * num_strokes
        
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="{width}" height="{height}">',
            '<style>',
            '  .stroke { fill: none; stroke: #333; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }',
            '  @keyframes draw { from { stroke-dashoffset: 500; } to { stroke-dashoffset: 0; } }',
        ]
        
        for i in range(num_strokes):
            delay = i * stroke_duration
            svg_parts.append(
                f'  .stroke-{i} {{ stroke-dasharray: 500; animation: draw {stroke_duration}s linear {delay}s forwards; }}'
            )
        
        svg_parts.append('</style>')
        
        for i, path_d in enumerate(paths):
            svg_parts.append(f'<path class="stroke stroke-{i}" d="{path_d}" />')
        
        svg_parts.append('</svg>')
        
        return '\n'.join(svg_parts)
    
    def generate_step_by_step(self, kanji: str,
                               width: int = 100,
                               height: int = 100) -> List[str]:
        """
        Generate series of SVGs showing progressive strokes
        
        Returns list of SVGs, each showing one more stroke
        """
        svg = self.fetcher.get_svg(kanji)
        if not svg:
            return []
        
        paths = re.findall(r'd="([^"]+)"', svg)
        if not paths:
            return []
        
        viewbox_match = re.search(r'viewBox="([^"]+)"', svg)
        viewbox = viewbox_match.group(1) if viewbox_match else "0 0 109 109"
        
        result = []
        
        for step in range(1, len(paths) + 1):
            svg_parts = [
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="{width}" height="{height}">',
                '<style>',
                '  .stroke { fill: none; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }',
                '  .old { stroke: #ccc; }',
                '  .new { stroke: #e74c3c; }',
                '</style>',
            ]
            
            for i in range(step):
                css_class = "new" if i == step - 1 else "old"
                svg_parts.append(f'<path class="stroke {css_class}" d="{paths[i]}" />')
            
            svg_parts.append('</svg>')
            result.append('\n'.join(svg_parts))
        
        return result


# =============================================================================
# SIMPLE NUMBERED DIAGRAM (without KanjiVG)
# =============================================================================

class SimpleStrokeDiagram:
    """
    Generate simple stroke diagrams using Unicode stroke data
    For use when KanjiVG is not available
    """
    
    # Basic stroke data for common kanji
    # Format: kanji -> stroke count
    STROKE_COUNTS = {
        '一': 1, '二': 2, '三': 3, '四': 5, '五': 4,
        '六': 4, '七': 2, '八': 2, '九': 2, '十': 2,
        '日': 4, '月': 4, '火': 4, '水': 4, '木': 4,
        '金': 8, '土': 3, '山': 3, '川': 3, '田': 5,
        '人': 2, '口': 3, '目': 5, '耳': 6, '手': 4,
        '足': 7, '大': 3, '小': 3, '中': 4, '上': 3,
        '下': 3, '左': 5, '右': 5, '男': 7, '女': 3,
        '子': 3, '犬': 4, '猫': 11, '鳥': 11, '魚': 11,
        '花': 7, '草': 9, '虫': 6, '貝': 7, '石': 5,
        '糸': 6, '車': 7, '門': 8, '雨': 8, '雲': 12,
        '電': 13, '気': 6, '空': 8, '海': 9, '森': 12,
    }
    
    @classmethod
    def generate_info_box(cls, kanji: str) -> str:
        """Generate simple info box showing stroke count"""
        stroke_count = cls.STROKE_COUNTS.get(kanji, '?')
        
        return f'''
<div style="border: 1px solid #ddd; padding: 10px; border-radius: 5px; display: inline-block;">
    <div style="font-size: 48px; text-align: center;">{kanji}</div>
    <div style="text-align: center; color: #666;">Số nét: {stroke_count}</div>
</div>
'''


# =============================================================================
# DEMO
# =============================================================================

def demo():
    """Demonstrate stroke order generation"""
    
    test_kanji = ['日', '月', '火', '水', '木', '山', '川', '人']
    
    print("=" * 60)
    print("STROKE ORDER DEMO")
    print("=" * 60)
    
    generator = StrokeOrderGenerator(use_cache=True)
    
    html_parts = ['<!DOCTYPE html><html><head>',
                  '<meta charset="UTF-8">',
                  '<title>Stroke Order Demo</title>',
                  '<style>',
                  'body { font-family: sans-serif; padding: 20px; }',
                  '.kanji-box { display: inline-block; margin: 20px; padding: 15px; background: #f5f5f5; border-radius: 8px; text-align: center; }',
                  '.kanji-box h3 { margin: 0 0 10px 0; font-size: 36px; }',
                  '</style>',
                  '</head><body>',
                  '<h1>Stroke Order Diagrams</h1>']
    
    for kanji in test_kanji:
        print(f"\nProcessing: {kanji}")
        
        svg = generator.generate(kanji, width=150, height=150)
        
        if svg:
            print(f"  Generated SVG: {len(svg)} chars")
            html_parts.append(f'''
            <div class="kanji-box">
                <h3>{kanji}</h3>
                {svg}
            </div>
            ''')
        else:
            print(f"  Failed to generate")
            # Use simple fallback
            html_parts.append(SimpleStrokeDiagram.generate_info_box(kanji))
    
    html_parts.append('</body></html>')
    
    # Save demo HTML
    output_path = '/home/claude/japanese_anki/stroke_demo.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))
    
    print(f"\n\nDemo HTML saved to: {output_path}")


if __name__ == "__main__":
    demo()
