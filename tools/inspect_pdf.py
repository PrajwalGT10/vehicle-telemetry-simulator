from pypdf import PdfReader
import os

pdf_path = "configs/IMEI Details.pdf"

if not os.path.exists(pdf_path):
    print(f"File not found: {pdf_path}")
    exit(1)

reader = PdfReader(pdf_path)
print(f"Number of Pages: {len(reader.pages)}")

# Dump first page content
page = reader.pages[0]
text = page.extract_text(extraction_mode="layout")
print("--- Page 1 Content (Layout Mode) ---")
print(text)
print("----------------------")
