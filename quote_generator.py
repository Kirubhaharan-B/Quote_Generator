import os, requests, textwrap, random, datetime, pickle
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
    return "minimal abstract background"

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

def get_avg_brightness(img, box=None):
    crop = img.crop(box) if box else img
    greyscale = crop.convert("L")
    histogram = greyscale.histogram()
    pixels = sum(histogram)
    brightness = sum(i * v for i, v in enumerate(histogram)) / pixels if pixels else 0
    return brightness

def overlay_quote(img_path, quote, out_path="output.png"):
    img = Image.open(img_path).convert("RGBA").resize((1080, 1350))
    blurred = img.filter(ImageFilter.GaussianBlur(radius=5))
    draw = ImageDraw.Draw(blurred)
    width, height = blurred.size

    quote_text, author = quote.rsplit("—", 1)
    author = f"— {author.strip()}"
    quote_text = quote_text.strip('" \n')

    font_size = 64
    while font_size > 20:
        font = ImageFont.truetype(FONT_PATH, font_size)
        lines = textwrap.wrap(quote_text, width=38)
        total_height = len(lines) * (font_size + 10)
        if total_height < height * 0.6:
            break
        font_size -= 4

    y = (height - total_height) // 2
    font_color = "white" if get_avg_brightness(blurred) < 130 else "black"
    for line in lines:
        w = draw.textbbox((0, 0), line, font=font)[2]
        draw.text(((width - w) / 2, y), line, font=font, fill=font_color)
        y += font_size + 10

    author_font = ImageFont.truetype(FONT_PATH, font_size // 2)
    w = draw.textbbox((0, 0), author, font=author_font)[2]
    draw.text(((width - w) / 2, y + 20), author, font=author_font, fill=font_color)

    blurred.save(out_path)
    return out_path

def upload_to_drive(file_path, author):
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
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
