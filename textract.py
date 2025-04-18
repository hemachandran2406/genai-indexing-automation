from PIL import Image, ImageDraw
import boto3
import io
import base64
import os
import fitz  # PyMuPDF
from dotenv import load_dotenv

load_dotenv()

# Replace these with your actual credentials and region
access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
region_name = os.getenv("AWS_REGION", "")

def process_document(file_path):
    client = boto3.client("textract", aws_access_key_id=access_key_id,
                          aws_secret_access_key=secret_access_key,
                          region_name=region_name)

    if file_path.lower().endswith('.pdf'):
        with fitz.open(file_path) as pdf_document:
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                pix = page.get_pixmap()
                image_bytes = pix.tobytes("png")
                response = client.analyze_document(
                    Document={'Bytes': image_bytes},
                    FeatureTypes=["TABLES", "FORMS"]
                )
                yield response
    else:
        with open(file_path, 'rb') as image_file:
            image_bytes = image_file.read()
            response = client.detect_document_text(Document={"Bytes": image_bytes})
            yield response

def extract_raw_text(response):
    raw_text = ""
    for item in response["Blocks"]:
        if item["BlockType"] == "LINE":
            raw_text += item["Text"] + " "
    return raw_text

def visualize_blocks(image_bytes, blocks):
    image = Image.open(io.BytesIO(image_bytes))
    draw = ImageDraw.Draw(image)

    for block in blocks:
        if block["BlockType"] != "PAGE":
            bbox = block["Geometry"]["BoundingBox"]
            x, y, w, h = bbox["Left"], bbox["Top"], bbox["Width"], bbox["Height"]
            x *= image.width
            y *= image.height
            w *= image.width
            h *= image.height
            draw.rectangle([x, y, x + w, y + h], outline="red", width=2)

    return image

def image_to_base64(image):
    with io.BytesIO() as buffer:
        image.save(buffer, format="JPEG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    
def image_to_data_url(image):
    base64_image = image_to_base64(image)
    data_url = f"data:image/jpeg;base64,{base64_image}"   

    return data_url

# ...existing code...

def main(file_path):
    responses = process_document(file_path)
    for response in responses:
        raw_text = extract_raw_text(response)
        print(raw_text)

if __name__ == "__main__":
    file_path = "/Users/Hemachandran/Documents/Personal Projects/GenAI-OCR/docs/M.33623BL.pdf"
    main(file_path)
