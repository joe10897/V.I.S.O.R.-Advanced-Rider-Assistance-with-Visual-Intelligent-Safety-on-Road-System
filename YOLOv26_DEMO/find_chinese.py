import re

def find_chinese():
    html_path = r"C:\Users\USER\Desktop\motorcycle_assist\YOLOv26_DEMO\presentation.html"
    
    with open(html_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    print("Lines containing Chinese characters:")
    count = 0
    # Match Chinese characters
    pattern = re.compile(r'[\u4e00-\u9fff]')
    
    for idx, line in enumerate(lines, 1):
        if pattern.search(line):
            # Check if it is inside the speakerNotesData block (which is allowed to contain Chinese bilingual notes)
            # We want to translate the slide contents themselves, but speaker notes are bilingual.
            # If the user wants to reduce Chinese, we can translate the slides themselves, but wait: 
            # should the speaker notes also be translated to English or kept bilingual?
            # "減少用中文，因為發表會用全英文" (Reduce use of Chinese, since the presentation will be fully in English).
            # It's better to keep speaker notes bilingual so they have both English and Chinese for reference,
            # but translate all slides and UI elements completely to English!
            # Let's see if the Chinese characters are on the slide content or in the JS speaker notes.
            is_js_notes = "en:" in line or "zh:" in line or "speakerNotesData" in line or (idx > 1800 and "zh" in line)
            
            if not is_js_notes:
                print(f"Line {idx}: {line.strip()}")
                count += 1
                if count > 30:
                    print("... (truncated)")
                    break
                    
    print(f"Total lines with Chinese (excluding notes): {count}")

if __name__ == "__main__":
    find_chinese()
