import os, requests, textwrap, random, datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import urllib3
urllib3.disable_warnings()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
FONT_PATH = "assets/Montserrat-Bold.ttf"
PEXELS_URL = "https://api.pexels.com/v1/search"

def fetch_quote():
    res = requests.get('https://dummyjson.com/quotes/random')
    data = res.json()
    return f'"{data["quote"]}"\n\n— {data["author"]}', data["quote"], data["author"]

def generate_image_description(text):
    keywords = {
        "dream": "stars night",
        "life": "people walking sunset",
        "freedom": "open road travel",
        "love": "romantic couple nature",
        "path": "forest path light",
    }
    for key, desc in keywords.items():
        if key in text.lower():
            return desc
    return "black abstract"

def fetch_pexels_image(query, save_path="/tmp/bg.jpg"):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 10, "page": random.randint(1, 2)}
    r = requests.get(PEXELS_URL, headers=headers, params=params)
    data = r.json()
    img_url = random.choice(data["photos"])["src"]["large2x"]
    img_data = requests.get(img_url).content
    with open(save_path, "wb") as f:
        f.write(img_data)
    return save_path

def overlay_quote(image_path, quote, output_path="output/quote.png"):
    font_path = FONT_PATH
    image = Image.open(image_path).convert("RGBA")
    image = image.resize((1080, 1350), Image.Resampling.LANCZOS)
    blurred = image.filter(ImageFilter.GaussianBlur(radius=5))
    draw = ImageDraw.Draw(blurred)
    width, height = blurred.size

    if "—" in quote:
        quote_text, author = quote.rsplit("—", 1)
        author = f"— {author.strip()}"
    else:
        quote_text = quote.strip()
        author = ""

    def fit_text(quote_text, max_width, max_height, initial_size=64, min_size=20, line_spacing=10):
        font_size = initial_size
        while font_size >= min_size:
            font = ImageFont.truetype(font_path, font_size)
            wrapped = textwrap.wrap(quote_text, width=38)
            refined = []
            for line in wrapped:
                temp_line = ""
                for word in line.split():
                    test_line = f"{temp_line} {word}".strip()
                    w = draw.textbbox((0, 0), test_line, font=font)[2]
                    if w > max_width * 0.9:
                        refined.append(temp_line)
                        temp_line = word
                    else:
                        temp_line = test_line
                if temp_line:
                    refined.append(temp_line)

            total_height = len(refined) * (font_size + line_spacing)
            if total_height <= max_height * 0.6:
                return font, refined
            font_size -= 4
        return ImageFont.truetype(font_path, min_size), textwrap.wrap(quote_text, width=38)

    font_quote, lines = fit_text(quote_text.strip('" \n'), width, height)
    font_author = ImageFont.truetype(font_path, max(20, font_quote.size // 2))

    line_height = font_quote.size + 10
    total_text_height = len(lines) * line_height + (font_author.size if author else 0)
    y = (height - total_text_height) // 2

    for line in lines:
        w = draw.textbbox((0, 0), line, font=font_quote)[2]
        draw.text(((width - w) / 2, y), line, font=font_quote, fill="white")
        y += line_height

    if author:
        w = draw.textbbox((0, 0), author, font=font_author)[2]
        draw.text(((width - w) / 2, y + 30), author, font=font_author, fill="white")

    dir_name = os.path.dirname(output_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    blurred.save(output_path)
    return output_path

def upload_to_drive(file_path, author):
    creds = service_account.Credentials.from_service_account_file(
        '/etc/secrets/service-account.json',
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    service = build('drive', 'v3', credentials=creds)

    today = datetime.date.today().isoformat()
    author_tag = author.lower().replace(" ", "-").replace(".", "")
    filename = f"{today}-{author_tag}-quote.png"

    file_metadata = {
        'name': filename,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype='image/png')
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

def generate_and_save_quote_image():
    quote, raw, author = fetch_quote()
    query = generate_image_description(raw)
    bg = fetch_pexels_image(query)
    final_path = overlay_quote(bg, quote)
    upload_to_drive(final_path, author)
