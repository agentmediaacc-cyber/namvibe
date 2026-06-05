from flask import Blueprint, request, session
from services.api_auth_service import api_response, api_error
from services.auth_service import login_chain_user, register_chain_user, get_current_user

auth_api_bp = Blueprint('auth_api', __name__, url_prefix='/auth')

@auth_api_bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return api_error("Email and password required", code="invalid_input")
        
    res, error = login_chain_user(email, password)
    if error:
        return api_error(error, code="auth_failed")
        
    return api_response(data={
        "user": {
            "id": res.user.id,
            "email": res.user.email
        },
        "session": {
            "access_token": res.session.access_token,
            "refresh_token": res.session.refresh_token
        }
    })

@auth_api_bp.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    email = data.get('email')
    password = data.get('password')
    username = data.get('username')
    full_name = data.get('full_name', username)
    
    if not email or not password or not username:
        return api_error("Email, password and username required", code="invalid_input")
        
    res, error = register_chain_user(email, password, username, full_name)
    if error:
        return api_error(error, code="registration_failed")
        
    return api_response(data={"message": "Verification email sent"})
