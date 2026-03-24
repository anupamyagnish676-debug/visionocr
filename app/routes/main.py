from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models.database import Result

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def home():
    recent      = Result.query.filter_by(user_id=current_user.id)\
                              .order_by(Result.created_at.desc()).limit(5).all()
    total       = Result.query.filter_by(user_id=current_user.id).count()
    total_words = sum(r.word_count or 0 for r in
                      Result.query.filter_by(user_id=current_user.id).all())
    return render_template('home.html', recent=recent,
                           total=total, total_words=total_words)


history_bp = Blueprint('history', __name__)

@history_bp.route('/history')
@login_required
def history():
    page   = request.args.get('page', 1, type=int)
    doc_f  = request.args.get('doc_type', '')
    query  = Result.query.filter_by(user_id=current_user.id)
    if doc_f:
        query = query.filter(Result.doc_type.ilike(f'%{doc_f}%'))
    results = query.order_by(Result.created_at.desc()).paginate(page=page, per_page=10)
    return render_template('history.html', results=results, doc_filter=doc_f)

@history_bp.route('/result/<int:result_id>')
@login_required
def view_result(result_id):
    r = Result.query.get_or_404(result_id)
    if r.user_id != current_user.id:
        return 'Forbidden', 403
    return render_template('result.html', r=r)
