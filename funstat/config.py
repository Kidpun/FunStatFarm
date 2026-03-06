import os
import re

API_ID = None
API_HASH = None
SESSION_NAME = 'user.session'
RECOVERY_RETRY_HOURS = 1
SOURCE_BOT = 5506654256
CAPTCHA_BOT = 8799646329
TARGET_BOT = "@funstatfanstatkidbot"
LIMIT_CHECK_BOT = 8799646329
INTERVAL = 5

def load_from_env():
    global API_ID, API_HASH
    try:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key == 'API_ID' and value:
                                API_ID = int(value)
                            elif key == 'API_HASH' and value:
                                API_HASH = value
            return API_ID is not None and API_HASH is not None
    except Exception as e:
        print(f"Error loading .env: {e}")
    return False

def initialize_config():
    global API_ID, API_HASH
    
    if load_from_env():
        return True
    
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        api_id_match = re.search(r'^API_ID\s*=\s*(\d+)', content, re.MULTILINE)
        api_hash_match = re.search(r"^API_HASH\s*=\s*['\"]([^'\"]+)['\"]", content, re.MULTILINE)
        
        if api_id_match and api_hash_match:
            API_ID = int(api_id_match.group(1))
            API_HASH = api_hash_match.group(1)
            return True
    except Exception as e:
        print(f"Error reading config: {e}")
    
    return False

def save_credentials(api_id, api_hash):
    global API_ID, API_HASH
    
    try:
        API_ID = int(api_id)
        API_HASH = str(api_hash)
    except ValueError:
        return False
    
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(f"API_ID={API_ID}\n")
            f.write(f"API_HASH={API_HASH}\n")
        return True
    except Exception as e:
        print(f"Error saving to .env: {e}")
    
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        with open(config_path, 'w', encoding='utf-8') as f:
            for line in lines:
                if line.strip().startswith('API_ID ='):
                    f.write(f'API_ID = {API_ID}\n')
                elif line.strip().startswith('API_HASH ='):
                    f.write(f"API_HASH = '{API_HASH}'\n")
                else:
                    f.write(line)
        return True
    except Exception as e:
        print(f"Error saving to config.py: {e}")
        return False
