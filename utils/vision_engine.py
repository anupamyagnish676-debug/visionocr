"""
utils/vision_engine.py
Supports TWO VLM backends:
  1. Gemini API  — cloud, free tier, best accuracy (needs API key)
  2. Ollama      — local, fully offline, no API key needed

To use Ollama:
  1. Download from https://ollama.com and install
  2. Run: ollama pull llava
  3. Set VLM_BACKEND = "ollama" in app/__init__.py
"""
import base64
import os
import io
from PIL import Image


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────
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


def _pil_to_base64(pil_img: Image.Image, max_size: int = 1568) -> str:
    w, h = pil_img.size
    if max(w, h) > max_size:
        scale   = max_size / max(w, h)
        pil_img = pil_img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
    if pil_img.mode in ('RGBA', 'P'):
        pil_img = pil_img.convert('RGB')
    buf = io.BytesIO()
    pil_img.save(buf, format='JPEG', quality=90)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def _pil_to_path(pil_img: Image.Image) -> str:
    """Save PIL image to temp file and return path (for Ollama)."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    pil_img.convert('RGB').save(tmp.name, format='JPEG', quality=90)
    return tmp.name


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


# ─────────────────────────────────────────────
# Backend 1: Gemini API (cloud)
# ─────────────────────────────────────────────
def _analyze_gemini(pil_img: Image.Image, translate_to: str, api_key: str) -> dict:
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("Run: pip install google-generativeai")

    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in app/__init__.py")

    genai.configure(api_key=api_key)

    # Auto-detect working model from available list
    model_name = 'gemini-2.0-flash'
    try:
        available = [
            m.name.replace('models/', '')
            for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
        print(f'[Gemini] Available models: {available}')
        # Try in order of preference
        for candidate in [
            'gemini-2.0-flash',
            'gemini-2.0-flash-lite',
            'gemini-1.5-flash',
            'gemini-1.5-flash-001',
            'gemini-1.5-flash-002',
            'gemini-1.5-pro',
            'gemini-1.0-pro-vision',
        ]:
            if candidate in available:
                model_name = candidate
                break
        else:
            # Use first available vision model as last resort
            vision = [m for m in available if 'flash' in m or 'pro' in m or 'vision' in m]
            if vision:
                model_name = vision[0]
        print(f'[Gemini] Using model: {model_name}')
    except Exception as e:
        print(f'[Gemini] Could not list models: {e}')

    model    = genai.GenerativeModel(model_name)
    prompt   = _build_prompt(translate_to)
    b64      = _pil_to_base64(pil_img)
    img_part = {'mime_type': 'image/jpeg', 'data': b64}

    response = model.generate_content(
        [prompt, img_part],
        generation_config=genai.GenerationConfig(max_output_tokens=4096, temperature=0.1),
    )

    raw    = response.text
    tokens = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
    result = _parse_response(raw, translate_to)
    result['tokens_used'] = tokens
    result['backend']     = f'Gemini ({model_name})'
    return result


# ─────────────────────────────────────────────
# Backend 2: Ollama (local, offline)
# ─────────────────────────────────────────────
def _analyze_ollama(pil_img: Image.Image, translate_to: str, model: str = 'llava') -> dict:
    """
    Runs VLM locally using Ollama.
    Requirements:
      1. Install Ollama from https://ollama.com
      2. Run: ollama pull llava   (or llava:13b for better accuracy)
      3. Ollama must be running (it starts automatically after install)
    """
    try:
        import ollama as ol
    except ImportError:
        raise ImportError(
            "ollama Python package not installed.\n"
            "Run: pip install ollama\n"
            "Also install Ollama app from: https://ollama.com"
        )

    img_path = _pil_to_path(pil_img)
    prompt   = _build_prompt(translate_to)

    print(f'[Ollama] Running {model} locally...')

    try:
        response = ol.chat(
            model=model,
            messages=[{
                'role':    'user',
                'content': prompt,
                'images':  [img_path],
            }]
        )
        raw = response['message']['content']
    except Exception as e:
        raise RuntimeError(
            f"Ollama error: {e}\n"
            f"Make sure Ollama is running and model '{model}' is installed.\n"
            f"Run: ollama pull {model}"
        )
    finally:
        # Clean up temp file
        try:
            os.unlink(img_path)
        except Exception:
            pass

    result = _parse_response(raw, translate_to)
    result['tokens_used'] = 0   # Ollama does not report token count
    result['backend']     = f'Ollama ({model})'
    return result


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────
def analyze_image(
    pil_img: Image.Image,
    translate_to: str = '',
    api_key: str = '',
    backend: str = 'gemini',        # 'gemini' or 'ollama'
    ollama_model: str = 'llava',    # ollama model name
) -> dict:
    """
    Analyze a handwritten image using the selected VLM backend.

    backend='gemini'  → Uses Google Gemini API (needs API key, cloud)
    backend='ollama'  → Uses Ollama locally (needs Ollama installed, offline)
    """
    backend = backend.lower().strip()

    if backend == 'ollama':
        return _analyze_ollama(pil_img, translate_to, model=ollama_model)
    else:
        return _analyze_gemini(pil_img, translate_to, api_key=api_key)
