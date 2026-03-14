from flask import Blueprint, redirect, url_for, render_template, request, flash, jsonify
from flask_security import current_user, login_required, hash_password
from flask_security.utils import verify_password, login_user
from datetime import date
from mp.models import db, User

bp = Blueprint('auth', __name__, url_prefix='/auth')

#모달 로그인 엔드포인트 (JSON 응답)
@bp.route("/login_modal", methods=["POST"])
def login_modal():
    email = request.form.get("email")
    password = request.form.get("password")
    remember = request.form.get("remember") == "on"
    
    # 사용자 조회
    user = User.query.filter_by(email=email).first()
    
    # 사용자 존재 여부 및 비밀번호 확인
    if user and verify_password(password, user.password):
        # 로그인 처리
        login_user(user, remember=remember)
        
        # 권한에 따라 리다이렉트 URL 결정
        if user.has_role('admin'):
            redirect_url = url_for('auth.admin_dashboard')
        else:
            redirect_url = url_for('auth.user_profile')
        
        return jsonify({
            'success': True,
            'redirect_url': redirect_url
        })
    else:
        return jsonify({
            'success': False,
            'message': '이메일 또는 비밀번호가 올바르지 않습니다.'
        }), 401


# 회원가입
@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # 폼 데이터 가져오기
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")
        birth_str = request.form.get("birth")  # YYYY-MM-DD 형식
        mobile1 = request.form.get("mobile1")
        mobile2 = request.form.get("mobile2")
        mobile3 = request.form.get("mobile3")
        mobile = f"{mobile1}{mobile2}{mobile3}"

        # birth를 datetime.date 객체로 변환
        birth = date.fromisoformat(birth_str)

        # 1 비밀번호 확인
        if password != password_confirm:
            flash("비밀번호가 일치하지 않습니다.")
            return render_template("auth/register.html")

        # 2 이메일 중복 체크
        if User.query.filter_by(email=email).first():
            flash("이미 존재하는 이메일입니다.")
            return render_template("auth/register.html")

        # 3 모바일 중복 체크
        if User.query.filter_by(mobile=mobile).first():
            flash("이미 등록된 휴대폰 번호입니다.")
            return render_template("auth/register.html")

        # User 생성
        new_user = User(
            name=name,
            email=email,
            password=hash_password(password),
            birth=birth,
            mobile=mobile,
            active=True
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("index.index"))  # 가입 후 로그인 페이지로 이동

    # GET 요청일 경우 템플릿 렌더링
    return render_template("auth/register.html")


# 🔐 로그인 후 이동할 기본 페이지
@bp.route('/user')
@login_required
def user_profile():
    return render_template("auth/user_profile.html", user=current_user)


# 🔐 관리자 전용 페이지
@bp.route('/admin')
def admin_dashboard():
    if not current_user.is_authenticated or not current_user.has_role('admin'):
        return redirect(url_for('index.index'))
    return render_template("auth/admin_dashboard.html", user=current_user)


# 로그인 후 권한에 따라 자동 분기
@bp.route('/redirect')
@login_required
def redirect_by_role():
    if current_user.has_role('admin'):
        return redirect(url_for('auth.admin_dashboard'))
    return redirect(url_for('auth.user_profile'))
