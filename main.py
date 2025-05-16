import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap, random, os, datetime
import urllib3
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

urllib3.disable_warnings()

PEXELS_API_KEY = "VZS0oPqUPO04YfW0dy3qmqMvak10sZncJA6MkqjUEldShxYgn9izLA5D"
PEXELS_URL = "https://api.pexels.com/v1/search"
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def fetch_quote():
    res = requests.get('https://dummyjson.com/quotes/random')
    data = res.json()
    return f'"{data["quote"]}"\n\n— {data["author"]}', data["quote"], data["author"]

def generate_image_description(quote_text):
    keywords = {
        "shoe": "mismatched shoes street",
        "path": "forest path light",
        "life": "people walking sunset",
        "freedom": "open road travel",
        "dream": "starry sky night",
        "love": "romantic couple nature",
        "individual": "person alone mountain",
    }
    for key, desc in keywords.items():
        if key in quote_text.lower():
            return desc
    return "minimal abstract background"

def fetch_pexels_image(query, save_path="/tmp/background.jpg"):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 10, "page": random.randint(1, 2)}
    response = requests.get(PEXELS_URL, headers=headers, params=params)
    data = response.json()
    photos = data.get("photos", [])
    if not photos:
        params["query"] = "nature"
        response = requests.get(PEXELS_URL, headers=headers, params=params)
        data = response.json()
        photos = data.get("photos", [])
        if not photos:
            raise Exception("No images found")
    img_url = random.choice(photos)["src"]["large2x"]
    img_data = requests.get(img_url).content
    with open(save_path, "wb") as f:
        f.write(img_data)
    return save_path

def get_average_brightness(image, box=None):
    # Calculate average brightness in the given box or whole image
    if box:
        crop = image.crop(box)
    else:
        crop = image
    greyscale = crop.convert("L")  # convert to greyscale
    histogram = greyscale.histogram()
    pixels = sum(histogram)
    brightness = scale = 0
    for i in range(256):
        brightness += histogram[i] * i
    avg = brightness / pixels if pixels else 0
    return avg

def overlay_quote(image_path, quote, output_path="output/quote_output.png"):
    font_path = "assets/Montserrat-Bold.ttf"
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

    # Fit text function for font size and wrapping
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

    # Calculate brightness under text area to decide text color
    text_area_height = len(lines) * (font_quote.size + 10) + (font_author.size if author else 0)
    y_text_start = (height - text_area_height) // 2
    # We sample a box in the center for brightness
    sample_box = (0, y_text_start, width, y_text_start + text_area_height)
    brightness = get_average_brightness(blurred, sample_box)

    # Use black or white font color based on brightness
    font_color = "white" if brightness < 130 else "black"

    # Vertical centering and drawing
    line_height = font_quote.size + 10
    y = y_text_start
    for line in lines:
        w = draw.textbbox((0, 0), line, font=font_quote)[2]
        draw.text(((width - w) / 2, y), line, font=font_quote, fill=font_color)
        y += line_height

    if author:
        w = draw.textbbox((0, 0), author, font=font_author)[2]
        draw.text(((width - w) / 2, y + 30), author, font=font_author, fill=font_color)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    blurred.save(output_path)
    return output_path

def upload_to_drive(file_path, author, folder_name='Quotes'):
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)

    # Check if folder exists
    folder_id = None
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces='drive', fields="files(id, name)").execute()
    folders = results.get('files', [])
    if folders:
        folder_id = folders[0]['id']
    else:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        file = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = file.get('id')

    # Format file name
    today = datetime.date.today().isoformat()
    author_tag = author.lower().replace(" ", "-").replace(".", "").strip()
    filename = f"{today}-{author_tag}-quote.png"

    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='image/png')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

    print(f"✅ Uploaded to Google Drive as {filename}")

def generate_and_save_quote_image():
    quote, raw_text, author = fetch_quote()
    query = generate_image_description(raw_text)
    img_path = fetch_pexels_image(query)
    final_path = overlay_quote(img_path, quote)
    upload_to_drive(final_path, author)

def main():
    generate_and_save_quote_image()

if __name__ == "__main__":
    main()
