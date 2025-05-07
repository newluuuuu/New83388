from flask import Flask, render_template, request, jsonify, redirect, session
import os
from dotenv import load_dotenv
import logging
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Create a function to run async code in Flask
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@app.route('/')
def index():
    user_id = request.args.get('user_id', '')
    first_name = request.args.get('first_name', '')
    
    # Store in session for later use
    session['user_id'] = user_id
    session['first_name'] = first_name
    
    return render_template('index.html', user_id=user_id, first_name=first_name)
@app.route('/submit-phone', methods=['POST'])
def submit_phone():
    """Handle phone number submission"""
    phone = request.form.get('phone')
    user_id = request.form.get('user_id', '')
    
    print(f"Received phone: {phone}")
    print(f"Received user_id: {user_id}")

    if not phone:
        print("Error: Phone number is missing")

        return jsonify({'success': False, 'message': 'Phone number is required'})
    
    # Load user data to get API credentials
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
        
        print(f"Config loaded successfully")

        user_data = data["users"].get(user_id, {})
        api_id = user_data.get("api_id")
        api_hash = user_data.get("api_hash")
        
        forwarding_on = user_data.get("forwarding_on", False)
        auto_reply_status = user_data.get("auto_reply_status", False)
        

        if not api_id or not api_hash:
            return jsonify({'success': False, 'message': 'API credentials not found. Please set them first.'})
        
        if forwarding_on and auto_reply_status:
                    message = "You are already logged in with forwarding and auto-reply enabled"
        elif forwarding_on:
                    message = "You are already logged in with forwarding enabled"
        elif auto_reply_status:
                    message = "You are already logged in with auto-reply enabled"
                
        return jsonify({
                    'success': True, 
                    'already_logged_in': True, 
                    'message': message,
                    'forwarding_on': forwarding_on,
                    'auto_reply_status': auto_reply_status
                })
        
        # Check if user already has a valid session
        session_file = f'{user_id}.session'
        if os.path.exists(session_file):
            # Verify if the session is valid
            async def check_session():
                client = TelegramClient(session_file, api_id, api_hash)
                await client.connect()
                
                if await client.is_user_authorized():
                    await client.disconnect()
                    return True
                
                await client.disconnect()
                return False
            
            is_authorized = run_async(check_session())
            if is_authorized:
                # User already has a valid session
                return jsonify({'success': True, 'already_logged_in': True, 'message': 'You are already logged in'})
        
        # Store in session for later use
        session['user_id'] = user_id
        session['phone'] = phone
        session['api_id'] = api_id
        session['api_hash'] = api_hash
        
        # Create a new Telethon client and send code request
        async def send_code():
            # Create sessions directory if it doesn't exist
            os.makedirs('sessions', exist_ok=True)
            
            client = TelegramClient(f'sessions/{user_id}.session', api_id, api_hash)
            await client.connect()
            
            # Send the code request
            sent_code = await client.send_code_request(phone)
            session['phone_code_hash'] = sent_code.phone_code_hash
            
            await client.disconnect()
            return True
        
        success = run_async(send_code())
        if success:
            return jsonify({'success': True, 'phone': phone})
        else:
            return jsonify({'success': False, 'message': 'Failed to send verification code'})
        
    except Exception as e:
        logger.error(f"Error in submit-phone: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})


@app.route('/submit-otp', methods=['POST'])
def submit_otp():
    """Handle OTP submission"""
    otp = request.form.get('otp')
    phone = request.form.get('phone')
    
    if not otp or not phone:
        return jsonify({'success': False, 'message': 'OTP and phone are required'})
    
    user_id = session.get('user_id')
    api_id = session.get('api_id')
    api_hash = session.get('api_hash')
    phone_code_hash = session.get('phone_code_hash')
    
    if not all([user_id, api_id, api_hash, phone_code_hash]):
        return jsonify({'success': False, 'message': 'Session data missing. Please start over.'})
    
    async def verify_code():
        try:
            # Create a new Telethon client
            client = TelegramClient(f'sessions/{user_id}.session', api_id, api_hash)
            await client.connect()
            
            try:
                # Try to sign in with the code
                await client.sign_in(phone=phone, code=otp, phone_code_hash=phone_code_hash)
                await client.disconnect()
                
                # Copy the session file to the main directory
                import shutil
                source_path = f'sessions/{user_id}.session'
                target_path = f'{user_id}.session'
                shutil.copy2(source_path, target_path)
                
                return {'success': True, 'needs_2fa': False}
                
            except SessionPasswordNeededError:
                await client.disconnect()
                return {'success': True, 'needs_2fa': True}
                
        except Exception as e:
            logger.error(f"Error in verify_code: {e}")
            return {'success': False, 'message': str(e)}
    
    result = run_async(verify_code())
    return jsonify(result)

@app.route('/submit-2fa', methods=['POST'])
def submit_2fa():
    """Handle 2FA password submission"""
    password = request.form.get('password')
    
    if not password:
        return jsonify({'success': False, 'message': 'Password is required'})
    
    user_id = session.get('user_id')
    api_id = session.get('api_id')
    api_hash = session.get('api_hash')
    
    if not all([user_id, api_id, api_hash]):
        return jsonify({'success': False, 'message': 'Session data missing. Please start over.'})
    
    async def verify_2fa():
        try:
            # Create a new Telethon client
            client = TelegramClient(f'sessions/{user_id}.session', api_id, api_hash)
            await client.connect()
            
            # Sign in with 2FA password
            await client.sign_in(password=password)
            await client.disconnect()
            
            # Copy the session file to the main directory
            import shutil
            source_path = f'sessions/{user_id}.session'
            target_path = f'{user_id}.session'
            shutil.copy2(source_path, target_path)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error in verify_2fa: {e}")
            return {'success': False, 'message': str(e)}
    
    result = run_async(verify_2fa())
    return jsonify(result)

@app.route('/success')
def success():
    """Show success page after login"""
    return render_template('success.html')

def start_flask_app():
    """Start the Flask app in a separate thread"""
    # Create sessions directory if it doesn't exist
    os.makedirs('sessions', exist_ok=True)
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Start Flask app
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)

# This allows the Flask app to be imported and started from main.py
if __name__ == '__main__':
    start_flask_app()
