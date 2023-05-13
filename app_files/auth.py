
import validators
from http import HTTPStatus
from flask import request
from flask_restx import Namespace, Resource, fields, abort
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token

from app_files.models import User
from app_files.utils import TokenService, MailService


auth_namespace = Namespace('Auth', description='auth namespace')

user_register_input = auth_namespace.model(
    'RegisterUser', 
    {
        'username' : fields.String(required=True, description='An username for a user'),
        'email' : fields.String(required=True, description='An email for a user'),
        'firstname' : fields.String(required=True, description='An firstname for a user'),
        'lastname' : fields.String(required=True, description='An lastname for a user'),
        'password' : fields.String(required=True, description='A password for a user'),
    }
)

user_register_output = auth_namespace.model(
    'User',
    {
        'id' : fields.Integer(),
        'username' : fields.String(),
        'email' : fields.String(),
        'firstname' : fields.String(),
        'lastname' : fields.String(),
        'date_joined' : fields.DateTime(),
    }
)

user_login_output = auth_namespace.model(
    'User',
    {
        'id' : fields.Integer(),
        'username' : fields.String(),
        'email' : fields.String(),
        'firstname' : fields.String(),
        'lastname' : fields.String(),
        'date_joined' : fields.DateTime(),
        'access_token' : fields.String(),
        'refresh_token' : fields.String(),
        'token_type' : fields.String(),
    }
)


user_login_input = auth_namespace.model(
    'User',
    {
        'username_or_email' : fields.String(required=True, description="username or email"),
        'password' : fields.String(required=True, description="password"),
    }
)

password_reset_input = auth_namespace.model(
    'User',
    {'username_or_email' : fields.String(required=True, description="username or email")}
)


@auth_namespace.route('/register')
class Users(Resource):
 
    @auth_namespace.expect(user_register_input)
    @auth_namespace.marshal_with(user_register_output)
    def post(self):
        data: dict = request.get_json()
        username = data.get('username')
        email = data.get('email')
        firstname = data.get('firstname')
        lastname = data.get('lastname')
        password = data.get('password')

        if not username:
            abort(HTTPStatus.BAD_REQUEST, 'Username is required')

        if not validators.email(email):
            abort(HTTPStatus.BAD_REQUEST, 'Email is not valid')
        
        if not firstname:
            abort(HTTPStatus.BAD_REQUEST, 'Firstname is required')
        
        if not lastname:
            abort(HTTPStatus.BAD_REQUEST, 'Lastname is required')
        
        if len(password) < 6:
            abort(HTTPStatus.BAD_REQUEST, 'Password is too short')

        if User.query.filter_by(username=username).first():
            abort(HTTPStatus.CONFLICT, 'Username is already taken')
        
        if User.query.filter_by(email=email).first():
            abort(HTTPStatus.CONFLICT, 'Email is already taken')
        
        password_hash = generate_password_hash(password)
        new_user = User(username=username, firstname=firstname, lastname=lastname, email=email, password_hash=password_hash)
        new_user.save()

        return new_user, HTTPStatus.OK
    

@auth_namespace.route('/login')
class Users(Resource):

    @auth_namespace.expect(user_login_input)
    @auth_namespace.marshal_with(user_login_output)
    def post(self):
        data: dict = request.get_json()
        username_or_email = data.get('username_or_email')
        password = data.get('password')

        user = User.query.filter_by(email=username_or_email).first() or User.query.filter_by(username=username_or_email).first()

        if user and check_password_hash(user.password_hash, password):
            user.access_token = create_access_token(identity=user.id)
            user.refresh_token = create_refresh_token(identity=user.id)
            user.token_type = 'bearer'

            return user, HTTPStatus.OK
        
        abort(HTTPStatus.UNAUTHORIZED, 'Wrong credentials')
        
        

@auth_namespace.route('/password-reset-request')
class Users(Resource):

    @auth_namespace.expect(password_reset_input)
    def post(self):
        data: dict = request.get_json()
        username_or_email = data.get('username_or_email')

        user = User.query.filter_by(email=username_or_email).first() or User.query.filter_by(username=username_or_email).first()

        if not user:
            abort(HTTPStatus.NOT_FOUND, 'A user with that username or email not found!')
        
        user_id = str(user.id)
        user_email = user.email
        token = TokenService.create_password_reset_token(user_id=user_id)
        if token:
            is_mail_sent = MailService.send_reset_mail(email=user_email, token=token, uuid=user_id)
            if is_mail_sent:
                return 'An email has been sent with instructions to reset your password.', HTTPStatus.OK
    
   

@auth_namespace.route('/password-reset/<string:token>/<string:uuid>/confirm')
class Users(Resource):

    def post(self, token:str, uuid:str):
        data: dict = request.get_json()
        password_1 = data.get('password_1')
        password_2 = data.get('password_2')

        if password_1 and password_2:
            if password_1 == password_2:
                if TokenService.validate_password_reset_token(token=token, user_id=uuid):
                    user = User.query.get_or_404(uuid)
                    if user:
                        user.password_hash = generate_password_hash(password_2)
                        user.update()
                        return 'Password Reset Successfully', HTTPStatus.OK
                else:
                    return 'Unable to verify token', HTTPStatus.BAD_REQUEST
        return 'Passwords do not match', HTTPStatus.BAD_REQUEST
