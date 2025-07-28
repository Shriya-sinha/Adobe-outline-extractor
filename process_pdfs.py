import json
import os
from io import BytesIO
from typing import Dict, List, Optional
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar
from pathlib import Path
import re

# Configuration
FONT_THRESHOLDS = {
    "H1": 16,  # Largest headings
    "H2": 14,  # Major sections
    "H3": 12,  # Subsections
    "H4": 10   # Sub-subsections
}
MAX_PAGES = 50
Y_THRESHOLD = 8
MIN_TEXT_LENGTH = 4
EXCLUDED_HEADINGS = {"figure", "table", "appendix"}
TITLE_MIN_FONT_SIZE = 9  # Minimum font size for title

def average_fontsize(element: LTTextContainer) -> float:
    """Calculate average font size of characters in a text container."""
    sizes = [char.size for line in element for char in line if isinstance(char, LTChar)]
    return sum(sizes) / len(sizes) if sizes else 0.0

def is_heading(text: str, avg_size: float) -> bool:
    """Determine if text qualifies as a heading, excluding short or invalid entries."""
    text = text.strip().lower()
    return (len(text) >= MIN_TEXT_LENGTH and
            avg_size >= FONT_THRESHOLDS["H3"] and
            not re.match(r'^[\d\s\-–.():]+$', text) and
            text not in EXCLUDED_HEADINGS)

def is_potential_title(text: str, avg_size: float) -> bool:
    """Determine if text qualifies as a potential title."""
    text = text.strip()
    return (len(text) >= MIN_TEXT_LENGTH and
            avg_size >= TITLE_MIN_FONT_SIZE and
            not re.match(r'^[\d\s\-–.():]+$', text))

def group_boxes_by_y(boxes: List[Dict], y_thresh: float = Y_THRESHOLD) -> List[List[Dict]]:
    """Group text boxes by y-coordinate proximity to handle multi-line headings."""
    if not boxes:
        return []

    boxes = sorted(boxes, key=lambda b: b['y0'], reverse=True)
    groups, current_group, last_y = [], [boxes[0]], boxes[0]['y0']

    for box in boxes[1:]:
        if abs(box['y0'] - last_y) <= y_thresh:
            current_group.append(box)
        else:
            groups.append(current_group)
            current_group = [box]
        last_y = box['y0']

    if current_group:
        groups.append(current_group)
    return groups

def get_heading_level(avg_size: float) -> Optional[str]:
    """Assign heading level based on font size."""
    return next((level for level, size in FONT_THRESHOLDS.items() if avg_size >= size), None)

def outline_to_markdown(outline: List[Dict]) -> str:
    """Convert outline to markdown format for additional output."""
    return "\n".join(f"{'  ' * (int(item['level'][1]) - 1)}- {item['text']} (Page {item['page']})"
                    for item in outline)

def extract_pdfminer_outline(file_bytes: bytes, file_name: str, max_pages: int = MAX_PAGES) -> Dict:
    """Extract outline from PDF, producing JSON structure."""
    try:
        pages = extract_pages(BytesIO(file_bytes))
        outline: List[Dict] = []
        title_candidate, largest_size = None, 0.0
        is_first_text = True

        for page_num, layout in enumerate(list(pages)[:max_pages]):
            boxes = [
                {"text": element.get_text().strip(), "size": average_fontsize(element), "y0": element.y0}
                for element in layout
                if isinstance(element, LTTextContainer) and average_fontsize(element) > TITLE_MIN_FONT_SIZE
            ]

            for group in group_boxes_by_y(boxes):
                if not group:
                    continue

                merged_text = "\n".join(box['text'] for box in group)
                avg_size = sum(box['size'] for box in group) / len(group)

                if page_num == 0 and is_first_text and is_potential_title(merged_text, avg_size):
                    if avg_size > largest_size:
                        title_candidate, largest_size = merged_text, avg_size
                    is_first_text = False
                    continue

                if is_heading(merged_text, avg_size):
                    level = get_heading_level(avg_size)
                    if level:
                        outline.append({
                            "level": level,
                            "text": merged_text,
                            "page": page_num + 1,
                            "y0": min(box['y0'] for box in group)
                        })

        outline.sort(key=lambda x: (x['page'], -x['y0']))
        for item in outline:
            item.pop('y0', None)

        title = title_candidate or file_name.replace("_", " ").replace(".pdf", "").title()
        return {"title": title, "outline": outline}

    except Exception as e:
        print(f"Error processing {file_name}: {str(e)}")
        return {"title": file_name, "outline": []}

def process_pdfs():
    """Process all PDFs in input directory and save outputs to output directory."""
    try:
        # Get input and output directories
        input_dir = Path("/app/input")
        output_dir = Path("/app/output")
        
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get all PDF files
        pdf_files = list(input_dir.glob("*.pdf"))
        
        if not pdf_files:
            print("No PDF files found in input directory")
            return

        for pdf_file in pdf_files:
            
            # Read PDF file bytes
            with open(pdf_file, "rb") as f:
                file_bytes = f.read()
            
            # Extract outline
            result = extract_pdfminer_outline(file_bytes, pdf_file.name)
            
            # Save JSON output
            json_filename = output_dir / f"{pdf_file.stem}_outline.json"
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"Processed {pdf_file.name} -> {json_filename.name}")

    except Exception as e:
        print(f"Error processing files: {str(e)}")

if __name__ == "__main__":
    print("Starting processing PDFs")
    process_pdfs()
    print("Completed processing PDFs")