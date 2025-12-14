#!/bin/bash
#
# Japanese Vocabulary Anki Deck Generator
# Run script
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Japanese Vocabulary Anki Deck Generator${NC}"
echo -e "${GREEN}========================================${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found${NC}"
    exit 1
fi

# Install requirements if needed
if [ ! -f ".deps_installed" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt --break-system-packages 2>/dev/null || \
    pip install -r requirements.txt
    touch .deps_installed
fi

# Default EPUB path
EPUB_PATH="${1:-/mnt/user-data/uploads/Sách_Từ_Vựng_Tiếng_Nhật_Phương_Thức_T_Z_Library.epub}"
OUTPUT_DIR="${2:-./output}"

# Check EPUB exists
if [ ! -f "$EPUB_PATH" ]; then
    echo -e "${RED}Error: EPUB file not found: $EPUB_PATH${NC}"
    echo "Usage: $0 <epub_path> [output_dir]"
    exit 1
fi

echo ""
echo -e "Input:  ${YELLOW}$EPUB_PATH${NC}"
echo -e "Output: ${YELLOW}$OUTPUT_DIR${NC}"
echo ""

# Run options
echo "Select mode:"
echo "  1) Full (with English, Audio, Pitch, Stroke) - SLOW"
echo "  2) Fast (Vietnamese only, no API calls) - FAST"
echo "  3) Medium (with Pitch, no Audio/English) - MEDIUM"
echo ""
read -p "Choice [1-3, default=2]: " choice

case ${choice:-2} in
    1)
        echo -e "${YELLOW}Running FULL mode...${NC}"
        python3 main.py "$EPUB_PATH" -o "$OUTPUT_DIR" --delay 0.5
        ;;
    2)
        echo -e "${YELLOW}Running FAST mode...${NC}"
        python3 main.py "$EPUB_PATH" -o "$OUTPUT_DIR" --no-english --no-audio
        ;;
    3)
        echo -e "${YELLOW}Running MEDIUM mode...${NC}"
        python3 main.py "$EPUB_PATH" -o "$OUTPUT_DIR" --no-english --no-audio --delay 0.2
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Done!${NC}"
echo -e "Anki deck: ${YELLOW}$OUTPUT_DIR/japanese_vocabulary.apkg${NC}"
echo ""
echo "Import into Anki: File -> Import -> Select the .apkg file"
