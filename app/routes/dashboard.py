from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.database import Result
from collections import Counter
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    all_results  = Result.query.filter_by(user_id=current_user.id).all()
    total_docs   = len(all_results)
    total_words  = sum(r.word_count  or 0 for r in all_results)
    total_tokens = sum(r.tokens_used or 0 for r in all_results)
    translated   = sum(1 for r in all_results if r.translation)

    doc_types        = Counter(r.doc_type for r in all_results if r.doc_type)
    doc_types_labels = list(doc_types.keys())[:6]
    doc_types_values = [doc_types[k] for k in doc_types_labels]

    languages   = Counter(r.translate_to for r in all_results if r.translate_to)
    lang_labels = list(languages.keys())[:5]
    lang_values = [languages[k] for k in lang_labels]

    today        = datetime.utcnow().date()
    daily_labels = []
    daily_values = []
    for i in range(6, -1, -1):
        day   = today - timedelta(days=i)
        count = sum(1 for r in all_results
                    if r.created_at and r.created_at.date() == day)
        daily_labels.append(day.strftime('%d %b'))
        daily_values.append(count)

    recent = sorted(all_results, key=lambda r: r.created_at, reverse=True)[:5]

    return render_template('dashboard.html',
        total_docs=total_docs, total_words=total_words,
        total_tokens=total_tokens, translated=translated,
        doc_types_labels=doc_types_labels, doc_types_values=doc_types_values,
        lang_labels=lang_labels, lang_values=lang_values,
        daily_labels=daily_labels, daily_values=daily_values,
        recent=recent,
    )
