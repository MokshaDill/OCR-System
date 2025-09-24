from PIL import Image
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\Moksha_FirstChoice\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Path to your image
image_path = r"C:/Users/Moksha_FirstChoice/Desktop/OneDrive - Dialog Axiata PLC/Pictures/Screenshots/1.png"

# Open image using PIL
img = Image.open(image_path)

# Extract text with pytesseract
text = pytesseract.image_to_string(img)

print(text)



