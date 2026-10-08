import os
import json
import re
import time
import threading
import subprocess
import http.server
import socketserver
import telebot
from telebot import types

telebot.apihelper.CONNECT_TIMEOUT = 120
telebot.apihelper.READ_TIMEOUT = 300

# Environment variables with fallbacks
BOT_TOKEN = os.getenv("BOT_TOKEN", "8854251593:AAGMFK8-6GCfXaNaTeVBnm2JnDDwFm2Ix0U")
PASSWORD = os.getenv("PASSWORD", "2162340")
STATIC_WEBAPP_URL = os.getenv("WEBAPP_URL", "https://fazliddinyangiboev1985-web.github.io/TelegramBot-1C/")
PORT = int(os.getenv("PORT", 8085))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.path.join(BASE_DIR, "authenticated_users.json")
CLOUD_FILES_FILE = os.path.join(BASE_DIR, "cloud_files.json")
WEB_APP_DIR = os.path.join(BASE_DIR, "web_app")

WEBAPP_URL = STATIC_WEBAPP_URL

def start_http_server():
    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            if os.path.exists(WEB_APP_DIR):
                super().__init__(*args, directory=WEB_APP_DIR, **kwargs)
            else:
                super().__init__(*args, **kwargs)
        def log_message(self, format, *args):
            pass

    try:
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("0.0.0.0", PORT), CustomHandler) as httpd:
            print(f"Web server active on 0.0.0.0:{PORT}")
            httpd.serve_forever()
    except Exception as e:
        print(f"HTTP Server skipped: {e}")

def start_cloudflare_tunnel():
    global WEBAPP_URL
    if os.getenv("RENDER") or STATIC_WEBAPP_URL:
        return

    try:
        cmd = ["npx", "cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"]
        proc = subprocess.Popen(
            cmd, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding="utf-8", 
            errors="ignore"
        )
        for line in iter(proc.stdout.readline, ""):
            m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if m:
                WEBAPP_URL = m.group(0)
                break
    except Exception as e:
        print(f"Cloudflare Tunnel skipped: {e}")

# Start web server thread for Render port health check
threading.Thread(target=start_http_server, daemon=True).start()

if not os.getenv("RENDER"):
    try:
        threading.Thread(target=start_cloudflare_tunnel, daemon=True).start()
    except Exception:
        pass

def load_auth_users():
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_auth_users(users):
    try:
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(list(users), f)
    except Exception as e:
        print(f"Auth сақлашда хатолик: {e}")

def load_cloud_files():
    if os.path.exists(CLOUD_FILES_FILE):
        try:
            with open(CLOUD_FILES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cloud_files(data):
    try:
        with open(CLOUD_FILES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Cloud сақлашда хатолик: {e}")

authenticated_users = load_auth_users()
cloud_files = load_cloud_files()

bot = telebot.TeleBot(BOT_TOKEN)

def get_auth_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    url = WEBAPP_URL if WEBAPP_URL else "https://fazliddinyangiboev1985-web.github.io/TelegramBot-1C/"
    btn = types.KeyboardButton(
        text="🔐 Паролни киритиш (Форма)", 
        web_app=types.WebAppInfo(url=url)
    )
    markup.add(btn)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    authenticated_users.discard(user_id)
    save_auth_users(authenticated_users)
    
    markup = get_auth_keyboard()
    bot.send_message(
        message.chat.id, 
        "🔒 **Ботга кириш учун пастдаги «🔐 Паролни киритиш (Форма)» тугмасини босинг:**", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    user_id = message.from_user.id
    pwd_entered = message.web_app_data.data.strip() if message.web_app_data and message.web_app_data.data else ""
    
    if pwd_entered == PASSWORD:
        authenticated_users.add(user_id)
        save_auth_users(authenticated_users)
        
        bot.send_message(
            message.chat.id, 
            "✅ **Пароль тўғри! Хуш келибсиз.**", 
            reply_markup=types.ReplyKeyboardRemove(), 
            parse_mode="Markdown"
        )
        show_program_list_keyboard(message.chat.id)
    else:
        markup = get_auth_keyboard()
        bot.send_message(
            message.chat.id, 
            "❌ **Нотўғри пароль!**\n\nҚайтадан «🔐 Паролни киритиш (Форма)» тугмасини босинг:", 
            reply_markup=markup,
            parse_mode="Markdown"
        )

def get_clean_title(filename):
    clean_name = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ")
    return clean_name.strip()

def show_program_list_keyboard(chat_id):
    if not cloud_files:
        bot.send_message(
            chat_id, 
            "⚠️ **Бот хотирасида ҳали ҳеч қандай файл йўқ.**\n\nФайл қўшиш учун шу ботга файлларни юборинг.",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        return

    sorted_items = sorted(
        cloud_files.items(),
        key=lambda item: item[1].get("title", get_clean_title(item[0])).lower()
    )

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for idx, (file_key, data) in enumerate(sorted_items, 1):
        clean_title = data.get("title", get_clean_title(file_key))
        btn_text = f"{idx}.  {clean_title}"
        markup.add(types.KeyboardButton(btn_text))
        
    bot.send_message(
        chat_id, 
        "📂 **Дастурлар рўйхати:**", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['document', 'audio', 'video'])
def handle_incoming_file_to_cloud(message):
    user_id = message.from_user.id
    if user_id not in authenticated_users:
        send_welcome(message)
        return

    doc = message.document
    if doc:
        filename = doc.file_name if doc.file_name else "file"
        file_id = doc.file_id
        clean_title = get_clean_title(filename)
        
        cloud_files[filename] = {
            "file_id": file_id,
            "title": clean_title,
            "filename": filename
        }
        save_cloud_files(cloud_files)
        
        bot.reply_to(
            message, 
            f"✅ **`{clean_title}` файли сақланди!**", 
            parse_mode="Markdown"
        )
        show_program_list_keyboard(message.chat.id)

@bot.message_handler(commands=['del', 'delete'])
def handle_delete_command(message):
    user_id = message.from_user.id
    if user_id not in authenticated_users:
        send_welcome(message)
        return
    
    sorted_items = sorted(
        cloud_files.items(),
        key=lambda item: item[1].get("title", get_clean_title(item[0])).lower()
    )
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, (file_key, data) in enumerate(sorted_items, 1):
        raw_title = data.get("title", file_key)
        btn = types.InlineKeyboardButton(text=f"🗑 {idx}. {raw_title}", callback_data=f"del_file:{file_key}")
        markup.add(btn)
        
    bot.send_message(message.chat.id, "🗑 **Ўчирмоқчи бўлган файлингизни танланг:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_file:"))
def handle_delete_file_callback(call):
    file_key = call.data[9:]
    if file_key in cloud_files:
        del cloud_files[file_key]
        save_cloud_files(cloud_files)
        bot.answer_callback_query(call.id, "✅ Файл ўчирилди!")
        bot.edit_message_text("✅ **Файл бот менюсидан ўчирилди.**", call.message.chat.id, call.message.message_id)
        show_program_list_keyboard(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "⚠️ Файл топилмади!")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    
    # Авторизациядан ўтмаган бўлса
    if user_id not in authenticated_users:
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass

        if text == PASSWORD:
            authenticated_users.add(user_id)
            save_auth_users(authenticated_users)
            bot.send_message(
                message.chat.id, 
                "✅ **Пароль тўғри! Хуш келибсиз.**", 
                reply_markup=types.ReplyKeyboardRemove(), 
                parse_mode="Markdown"
            )
            show_program_list_keyboard(message.chat.id)
        else:
            markup = get_auth_keyboard()
            bot.send_message(
                message.chat.id, 
                "🔒 **Илтимос, пастдаги «🔐 Паролни киритиш (Форма)» тугмасини босинг:**", 
                reply_markup=markup, 
                parse_mode="Markdown"
            )
        return

    # Дастурлар тугмасини текшириш
    sorted_items = sorted(
        cloud_files.items(),
        key=lambda item: item[1].get("title", get_clean_title(item[0])).lower()
    )
    
    for idx, (file_key, data) in enumerate(sorted_items, 1):
        clean_title = data.get("title", get_clean_title(file_key))
        btn_text = f"{idx}.  {clean_title}"
        
        if text == btn_text or text == clean_title or text == f"{idx}. {clean_title}" or text.endswith(clean_title):
            file_id = data.get("file_id")
            if file_id:
                try:
                    bot.send_document(message.chat.id, file_id)
                except Exception as e:
                    bot.send_message(message.chat.id, f"❌ Хатолик: {e}")
                return

    show_program_list_keyboard(message.chat.id)

if __name__ == "__main__":
    print("==================================================")
    print(" 1C Programs Telegram Bot (24/7 Cloud Ready)")
    print(f" Password: {PASSWORD}")
    print("==================================================")
    bot.infinity_polling(skip_pending=True)
