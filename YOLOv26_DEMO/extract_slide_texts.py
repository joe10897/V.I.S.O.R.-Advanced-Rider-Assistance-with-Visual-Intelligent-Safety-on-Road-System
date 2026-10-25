import re

def extract_texts():
    html_path = r"C:\Users\USER\Desktop\motorcycle_assist\YOLOv26_DEMO\presentation.html"
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all slide-frames
    slides = re.findall(r'<section class="slide-frame[^"]*" id="slide-(\d+)">(.*?)</section>', content, re.DOTALL)
    
    # We want to inspect the slide bodies of slide 2 to 15
    for slide_id, slide_body in slides:
        slide_num = int(slide_id)
        if 2 <= slide_num <= 15:
            print(f"\n================ SLIDE {slide_num} ================")
            # Find all tag contents like <p>, <li>, <h3>, <th>, <td>
            tags = re.findall(r'(<(p|li|h3|h4|td|th)[^>]*>.*?</\2>)', slide_body, re.DOTALL)
            for tag_html, tag_name in tags:
                # Strip excessive whitespace
                cleaned = " ".join(tag_html.split())
                print(f"  {cleaned}")

if __name__ == "__main__":
    extract_texts()
