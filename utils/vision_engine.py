"""
utils/vision_engine.py
Uses Google Gemini Vision API.
Get FREE key at: https://aistudio.google.com/app/apikey
"""
import base64, os, io
from PIL import Image


def _pil_to_base64(pil_img: Image.Image, max_size: int = 1568) -> str:
    w, h = pil_img.size
    if max(w, h) > max_size:
        scale   = max_size / max(w, h)
        pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    if pil_img.mode in ('RGBA', 'P'):
        pil_img = pil_img.convert('RGB')
    buf = io.BytesIO()
    pil_img.save(buf, format='JPEG', quality=90)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def _build_prompt(translate_to: str) -> str:
    translation_block = ''
    if translate_to.strip():
        translation_block = f"""
4. TRANSLATION
Translate the full extracted text into {translate_to}.
Label this section exactly as: TRANSLATION:
"""
    return f"""You are an expert OCR and document analysis assistant.
Analyze this handwritten or typed document image carefully and provide:

1. DOCUMENT TYPE
Identify what kind of document this is (e.g. personal letter, school essay, diary entry,
shopping list, meeting notes, academic notes, story, poem, etc.)
Label this section exactly as: DOCUMENT TYPE:

2. EXTRACTED TEXT
Transcribe ALL text visible in the image exactly as written, preserving:
- Original line breaks and paragraph structure
- Punctuation and capitalization as written
- Any crossed out words (mark as ~~word~~)
Label this section exactly as: EXTRACTED TEXT:

3. SUMMARY
Write a concise 2-3 sentence summary of what the document is about.
Label this section exactly as: SUMMARY:
{translation_block}
Be thorough. If handwriting is unclear, make your best interpretation and add [unclear] next to uncertain words."""


def _parse_response(raw: str, translate_to: str) -> dict:
    def extract_section(text, label, next_labels):
        marker = label + ':'
        idx    = text.find(marker)
        if idx == -1:
            return ''
        start = idx + len(marker)
        end   = len(text)
        for nl in next_labels:
            ni = text.find(nl + ':', start)
            if ni != -1 and ni < end:
                end = ni
        return text[start:end].strip()

    doc_type    = extract_section(raw, 'DOCUMENT TYPE',  ['EXTRACTED TEXT', 'SUMMARY', 'TRANSLATION'])
    extracted   = extract_section(raw, 'EXTRACTED TEXT', ['SUMMARY', 'TRANSLATION'])
    summary     = extract_section(raw, 'SUMMARY',        ['TRANSLATION'])
    translation = extract_section(raw, 'TRANSLATION',    []) if translate_to.strip() else ''

    if not extracted:
        extracted = raw

    return {
        'doc_type':    doc_type.strip(),
        'extracted':   extracted.strip(),
        'summary':     summary.strip(),
        'translation': translation.strip(),
        'translate_to': translate_to.strip(),
        'word_count':  len(extracted.split()),
        'char_count':  len(extracted),
    }


def analyze_image(pil_img: Image.Image, translate_to: str = '', api_key: str = '') -> dict:
    try:
        import google.generativeai as genai
        from google.api_core.exceptions import ResourceExhausted
    except ImportError:
        raise ImportError("Run: pip install google-generativeai")

    key = api_key or os.getenv('GEMINI_API_KEY', '')
    if not key or key == 'PASTE_YOUR_GEMINI_KEY_HERE':
        raise ValueError(
            "Gemini API key not set.\n"
            "Open app/__init__.py and paste your key on line 13."
        )

    genai.configure(api_key=key)

    candidates = [
        'gemini-2.5-flash',
        'gemini-flash-latest',
        'gemini-2.0-flash',
        'gemini-2.5-pro',
        'gemini-2.5-flash-lite',
        'gemini-pro-latest'
    ]

    prompt   = _build_prompt(translate_to)
    b64      = _pil_to_base64(pil_img)
    img_part = {'mime_type': 'image/jpeg', 'data': b64}
    
    response = None
    used_model = None
    
    for candidate in candidates:
        try:
            model = genai.GenerativeModel(candidate)
            response = model.generate_content(
                [prompt, img_part],
                generation_config=genai.GenerationConfig(max_output_tokens=4096, temperature=0.1)
            )
            used_model = candidate
            print(f'[Gemini] Successfully used: {candidate}')
            break
        except ResourceExhausted:
            print(f'[Gemini] Model {candidate} has 0 limit or quota exceeded. Trying next...')
            continue
        except Exception as e:
            if 'does not exist' in str(e).lower() or 'not found' in str(e).lower() or 'not supported' in str(e).lower():
                print(f'[Gemini] Model {candidate} unavailable. Trying next...')
                continue
            raise e

    if not response:
        raise ValueError("All candidate Google Gemini models exceeded quota limits or are unavailable on your free-tier account. Please upgrade your API plan or wait.")

    raw    = response.text
    tokens = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0

    result = _parse_response(raw, translate_to)
    result['tokens_used'] = tokens
    result['model'] = used_model
    return result
