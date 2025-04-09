from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
import os
import uuid

app = FastAPI()


@app.post("/generate-quote-image/")
async def generate_quote_image_api(
    quote: str = Form(...),
    author: str = Form(...),
    quote_font_size: int = Form(48),
    author_font_size: int = Form(40),
    quote_text_color: str = Form("white"),
    author_text_color: str = Form("white"),
    shadow_blur_radius: int = Form(5),
    background_image: UploadFile = Form(...),
    overlay_image: UploadFile = Form(...),
    quote_font_file: UploadFile = Form(...),
    author_font_file: UploadFile = Form(...),
):
    width, height = 512, 512
    margin = 20

    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    bg_path = f"{temp_dir}/{uuid.uuid4()}.png"
    overlay_path = f"{temp_dir}/{uuid.uuid4()}.png"
    quote_font_path = f"{temp_dir}/{uuid.uuid4()}.ttf"
    author_font_path = f"{temp_dir}/{uuid.uuid4()}.ttf"

    with open(bg_path, "wb") as f:
        f.write(await background_image.read())
    with open(overlay_path, "wb") as f:
        f.write(await overlay_image.read())
    with open(quote_font_path, "wb") as f:
        f.write(await quote_font_file.read())
    with open(author_font_path, "wb") as f:
        f.write(await author_font_file.read())

    background = Image.open(bg_path).resize((width, height)).convert("RGBA")
    overlay = Image.open(overlay_path).resize((width, height)).convert("RGBA")
    image = Image.alpha_composite(background, overlay)

    try:
        quote_font = ImageFont.truetype(quote_font_path, quote_font_size)
    except:
        quote_font = ImageFont.load_default()

    try:
        author_font = ImageFont.truetype(author_font_path, author_font_size)
    except:
        author_font = ImageFont.load_default()

    quote_text = f'"{quote.replace('\n', ' '*50)}"'
    author_text = f"- {author}"

    avg_char_width = sum(quote_font.getlength(c) for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") / 52
    max_chars_per_line = int((width - 2 * margin) / avg_char_width)
    wrapped_quote = textwrap.fill(quote_text, width=max_chars_per_line)

    draw = ImageDraw.Draw(image)
    quote_bbox = draw.multiline_textbbox((0, 0), wrapped_quote, font=quote_font)
    author_bbox = draw.textbbox((0, 0), author_text, font=author_font)

    quote_height = quote_bbox[3] - quote_bbox[1]
    author_height = author_bbox[3] - author_bbox[1]
    total_height = quote_height + author_height + 10
    group_y = (height - total_height) // 2

    quote_x = margin
    quote_y = group_y
    author_x = width - margin - (author_bbox[2] - author_bbox[0])
    author_y = height - margin - (author_bbox[3] - author_bbox[1])

    shadow_color = (0, 0, 0, 200)
    shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.multiline_text((quote_x, quote_y), wrapped_quote, fill=shadow_color, font=quote_font, align="left")
    shadow_draw.text((author_x, author_y), author_text, fill=shadow_color, font=author_font, align="right")
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur_radius))
    image = Image.alpha_composite(image, shadow_layer)

    draw = ImageDraw.Draw(image)
    draw.multiline_text((quote_x, quote_y), wrapped_quote, fill=quote_text_color, font=quote_font, align="left")
    draw.text((author_x, author_y), author_text, fill=author_text_color, font=author_font, align="right")

    output_path = f"{temp_dir}/quote_{uuid.uuid4()}.png"
    image.save(output_path)

    return FileResponse(output_path, media_type="image/png", filename="quote.png")
