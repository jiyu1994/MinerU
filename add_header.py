import fitz  # PyMuPDF

def apply_headers_and_footers(input_pdf_path, output_pdf_path):
    """
    Applies headers, footers, and separator lines to a PDF based on extracted JSON patterns.
    Uses Permille (1/1000) coordinate system logic.
    """
    try:
        doc = fitz.open(input_pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return

    # --- Configuration Constants (Derived from JSON Analysis) ---
    
    # Colors and Fonts
    TEXT_COLOR = (0.3, 0.3, 0.3)  # Dark Gray
    LINE_COLOR = (0, 0, 0)        # Black
    FONT_NAME = "helv"            # Helvetica/Arial
    FONT_SIZE = 9
    LINE_WIDTH = 0.5

    # Vertical Positions (Y) in Permille (0-1000)
    # Using averages from JSON to ensure consistency across pages
    HEADER_Y_PERMILLE = 93
    FOOTER_Y_PERMILLE = 960
    SEPARATOR_LINE_Y_PERMILLE = 115 # Slightly below header

    # Horizontal Positions (X) in Permille
    # Margins for the separator line
    LINE_START_X_PERMILLE = 50
    LINE_END_X_PERMILLE = 950
    
    # Text alignments
    LEFT_ALIGN_X_PERMILLE = 103
    RIGHT_ALIGN_X_PERMILLE = 706  # Approximate start for right-aligned block

    # Translations
    TXT_HEADER_EVEN = "2025 Revised Economic Outlook"
    TXT_HEADER_ODD = "Issue Analysis"
    TXT_FOOTER_PREFIX_EVEN = "May 2025 No. 834"
    TXT_FOOTER_SUFFIX_ODD = "| KDB Monthly Bulletin"

    print(f"Processing {len(doc)} pages...")

    for page_idx, page in enumerate(doc):
        # 1. Calculate Actual Dimensions based on Page Size
        width = page.rect.width
        height = page.rect.height

        # Helper to convert permille to pixels
        def p_to_px(permille_x, permille_y):
            return (permille_x / 1000.0 * width, permille_y / 1000.0 * height)

        # 2. Determine Page Number and Type (Odd/Even)
        # Logic: Printed Number = Index + 3
        printed_page_num = page_idx + 3
        is_even_index = (page_idx % 2 == 0)

        # 3. Define Text Content and Positions based on Page Type
        header_text = ""
        footer_text = ""
        text_align = 0 # 0 = Left (default for insert_text)
        
        # Coordinates for text insertion
        t_x, t_y = 0, 0
        f_x, f_y = 0, 0

        if is_even_index:
            # --- Even Page (Right Side) ---
            header_text = TXT_HEADER_EVEN
            footer_text = f"{TXT_FOOTER_PREFIX_EVEN}   {printed_page_num}"
            
            # Calculate coordinates
            t_x, t_y = p_to_px(RIGHT_ALIGN_X_PERMILLE, HEADER_Y_PERMILLE)
            f_x, f_y = p_to_px(RIGHT_ALIGN_X_PERMILLE, FOOTER_Y_PERMILLE)
            
            # Adjust X for right-side visual balance if needed, 
            # but JSON suggests starting text around 706. 
            
        else:
            # --- Odd Page (Left Side) ---
            header_text = TXT_HEADER_ODD
            footer_text = f"{printed_page_num}   {TXT_FOOTER_SUFFIX_ODD}"
            
            # Calculate coordinates
            t_x, t_y = p_to_px(LEFT_ALIGN_X_PERMILLE, HEADER_Y_PERMILLE)
            f_x, f_y = p_to_px(LEFT_ALIGN_X_PERMILLE, FOOTER_Y_PERMILLE)

        # 4. Draw Header
        page.insert_text(
            (t_x, t_y),
            header_text,
            fontname=FONT_NAME,
            fontsize=FONT_SIZE,
            color=TEXT_COLOR
        )

        # 5. Draw Footer
        page.insert_text(
            (f_x, f_y),
            footer_text,
            fontname=FONT_NAME,
            fontsize=FONT_SIZE,
            color=TEXT_COLOR
        )

        # 6. Draw Visual Separator Line (Under Header)
        # Calculate start and end points
        line_start = p_to_px(LINE_START_X_PERMILLE, SEPARATOR_LINE_Y_PERMILLE)
        line_end = p_to_px(LINE_END_X_PERMILLE, SEPARATOR_LINE_Y_PERMILLE)

        page.draw_line(
            line_start,
            line_end,
            color=LINE_COLOR,
            width=LINE_WIDTH
        )

    # Save output
    doc.save(output_pdf_path)
    print(f"Successfully saved: {output_pdf_path}")

# --- Execution ---
if __name__ == "__main__":
    # Ensure you have a file named 'translated.pdf' in the directory
    # or change this path to your actual file.
    input_file = "output/2025/auto/2025_translated_v2_2025-12-09_12-20-02.pdf" 
    output_file = "output/2025/auto/2025_final_paper_styled.pdf"
    
    # Create a dummy PDF for testing if input doesn't exist (Optional, for demo purposes)
    import os
    if not os.path.exists(input_file):
        print("Note: 'translated.pdf' not found. Creating a dummy blank PDF for demonstration.")
        dummy = fitz.open()
        for _ in range(30): dummy.new_page()
        dummy.save(input_file)
        dummy.close()

    apply_headers_and_footers(input_file, output_file)