import os
from PIL import Image
from surya.foundation import FoundationPredictor
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor

DEVICE = "cpu" 

def load_image(path: str) -> Image.Image:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    img = Image.open(path)
    img = img.convert("RGB")
    return img

def upscale(img: Image.Image, scale: float = 2.0) -> Image.Image:
    if scale is None or scale <= 1.0:
        return img
    w, h = img.size
    return img.resize((int(w * scale), int(h * scale)), resample=Image.BICUBIC)


def sort_key_textline(text_line) -> float:
    """Sort lines top-to-bottom using min y from polygon."""
    try:
        return min(pt[1] for pt in text_line.polygon)
    except Exception:
        return 0.0

def run_surya_ocr(image_path: str, scale: float = 2.0):
    # 1) Load
    img = load_image(image_path)

    # 2) Upscale
    img = upscale(img, scale=scale)

    # 3) Preview input 
    try:
        img.show(title="Surya OCR Input")
    except Exception:
        pass  

    # 4) Initialize predictors once per run
    foundation = FoundationPredictor(device=DEVICE)
    det = DetectionPredictor(device=DEVICE)
    rec = RecognitionPredictor(foundation)

    print("Processing OCR...")
    # Surya expects a list of PIL images
    results = rec([img], det_predictor=det)

    # results is list[OCRResult]
    if not results:
        return []

    ocr_result = results[0]

    # Extract lines
    text_lines = list(getattr(ocr_result, "text_lines", []) or [])
    if not text_lines:
        return []

    # Sort for nicer reading
    text_lines = sorted(text_lines, key=sort_key_textline)

    extracted = []
    for tl in text_lines:
        txt = (getattr(tl, "text", "") or "").strip()
        if not txt:
            continue
        conf = getattr(tl, "confidence", None)
        poly = getattr(tl, "polygon", None)
        extracted.append((txt, conf, poly))

    return extracted


if __name__ == "__main__":
    target_path = r"C:\Users\Nader\Desktop\Testing ocr (previous failures)\6483.png"
    try:
        out = run_surya_ocr(target_path, scale=2.0)

        print("\n--- EXTRACTED TEXT (Surya) ---")
        if not out:
            print("(No text detected)")
        else:
            for i, (txt, conf, poly) in enumerate(out, 1):
                conf_str = f"{conf:.3f}" if isinstance(conf, (int, float)) else "N/A"
                print(f"{i:02d}. [{conf_str}] {txt}")

    except Exception as e:
        print("ERROR:", e)