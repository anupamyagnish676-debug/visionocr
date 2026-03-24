import os, uuid, tempfile, traceback
from flask import Blueprint, render_template, request, jsonify, current_app, send_file, Response
from flask_login import login_required, current_user
from PIL import Image
from fpdf import FPDF
from app.models.database import db, Result

extract_bp = Blueprint('extract', __name__)
ALLOWED = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp', 'gif'}

def allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

def safe_text(text):
    if not text:
        return ''
    return text.encode('latin-1', errors='replace').decode('latin-1')

@extract_bp.route('/extract')
@login_required
def upload_page():
    return render_template('upload.html')

@extract_bp.route('/api/analyze', methods=['POST'])
@login_required
def analyze():
    try:
        from utils.vision_engine import analyze_image

        if 'image' not in request.files:
            return jsonify({'error': 'No image uploaded'}), 400

        file         = request.files['image']
        translate_to = request.form.get('translate_to', '').strip()

        if not file.filename or not allowed(file.filename):
            return jsonify({'error': 'Unsupported file type. Use JPG, PNG, or WEBP.'}), 400

        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        fname    = f"{uuid.uuid4().hex}_{file.filename}"
        filepath = os.path.join(upload_dir, fname)
        file.save(filepath)

        api_key = current_app.config.get('GEMINI_API_KEY', '')
        pil_img = Image.open(filepath).convert('RGB')
        result  = analyze_image(pil_img, translate_to=translate_to, api_key=api_key)

        rec = Result(
            user_id      = current_user.id,
            filename     = fname,
            doc_type     = result['doc_type'][:80] if result['doc_type'] else 'Unknown',
            extracted    = result['extracted'],
            summary      = result['summary'],
            translation  = result['translation'],
            translate_to = result['translate_to'],
            word_count   = result['word_count'],
            char_count   = result['char_count'],
            tokens_used  = result['tokens_used'],
        )
        db.session.add(rec)
        db.session.commit()

        return jsonify({
            'id':           rec.id,
            'doc_type':     rec.doc_type,
            'extracted':    rec.extracted,
            'summary':      rec.summary,
            'translation':  rec.translation,
            'translate_to': rec.translate_to,
            'word_count':   rec.word_count,
            'char_count':   rec.char_count,
            'tokens_used':  rec.tokens_used,
        })

    except Exception as e:
        tb = traceback.format_exc()
        print(f'[ERROR] /api/analyze:\n{tb}')
        return jsonify({'error': str(e)}), 500


@extract_bp.route('/api/pdf/<int:result_id>')
@login_required
def download_pdf(result_id):
    rec = Result.query.get_or_404(result_id)
    if rec.user_id != current_user.id:
        return 'Forbidden', 403

    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Extracted Text', ln=True, align='C')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, safe_text(
        f'Type: {rec.doc_type}  |  Words: {rec.word_count}  |  Chars: {rec.char_count}'),
        ln=True, align='C')
    pdf.ln(4)
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(30, 30, 30)
    for line in (rec.extracted or '').split('\n'):
        pdf.multi_cell(0, 7, safe_text(line) if safe_text(line).strip() else ' ')

    if rec.summary:
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 10, 'Summary', ln=True)
        pdf.ln(2)
        pdf.set_font('Helvetica', '', 11)
        pdf.multi_cell(0, 7, safe_text(rec.summary))

    if rec.translation:
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 10, safe_text(f'Translation ({rec.translate_to})'), ln=True)
        pdf.ln(2)
        pdf.set_font('Helvetica', '', 11)
        for line in rec.translation.split('\n'):
            pdf.multi_cell(0, 7, safe_text(line) if safe_text(line).strip() else ' ')

    out = os.path.join(tempfile.gettempdir(), f'ocr_{result_id}.pdf')
    pdf.output(out)
    return send_file(out, as_attachment=True, download_name=f'document_{result_id}.pdf')


@extract_bp.route('/api/txt/<int:result_id>')
@login_required
def download_txt(result_id):
    rec = Result.query.get_or_404(result_id)
    if rec.user_id != current_user.id:
        return 'Forbidden', 403
    content  = f"DOCUMENT TYPE: {rec.doc_type}\n\n"
    content += f"EXTRACTED TEXT:\n{rec.extracted}\n\n"
    if rec.summary:
        content += f"SUMMARY:\n{rec.summary}\n\n"
    if rec.translation:
        content += f"TRANSLATION ({rec.translate_to}):\n{rec.translation}\n"
    return Response(content, mimetype='text/plain',
                    headers={'Content-Disposition': f'attachment; filename=document_{result_id}.txt'})
