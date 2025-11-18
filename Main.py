import telebot
from telebot import types
from flask import Flask, request
import os

# --- Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
OWNER_ID = int(os.environ.get("OWNER_ID", 6535364725)) 

# --- App Setup ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Bot Data Storage ---
admins = {OWNER_ID}
user_messages = {}
official_link = None 

# --------------------------- Helpers ---------------------------

def is_admin(uid):
    return uid in admins

def save_msg(uid, msg):
    user_messages.setdefault(uid, []).append(msg)

# --------------------------- Commands ---------------------------

@bot.message_handler(commands=['start'])
def start(msg):
    user_name = msg.from_user.first_name if msg.from_user.first_name else "There"
    bot.reply_to(msg, f"Welcome, {user_name}! Message me and I will forward it to the admin.")

@bot.message_handler(commands=['menu'])
def menu(msg):
    if not is_admin(msg.from_user.id):
        return
    
    link_status = official_link if official_link else "None set."

    txt = (
        "**Admin Menu**\n"
        "--- Chats ---\n"
        "`/mm <user_id> <text>` - Send text to a user\n"
        "`/mp <user_id>` (Reply to media) - Send media to a user\n"
        "`/show <user_id>` - Show chat history\n"
        "`/allm` - Show all chat histories\n\n"
        "--- Link Management (Owner Only) ---\n"
        f"**Current Link:** {link_status}\n"
        "`/setlink <URL>` - Set/Update the official link.\n\n"
        "--- Admin Management (Owner Only) ---\n"
        "`/admin <user_id>` - Add admin\n"
        "`/dadmin <user_id>` - Remove admin"
    )
    bot.reply_to(msg, txt, parse_mode='Markdown')

@bot.message_handler(commands=['setlink'])
def set_channel_link(msg):
    global official_link
    if msg.from_user.id != OWNER_ID:
        bot.reply_to(msg, "Error: Only the Owner can set the link.")
        return

    try:
        link = msg.text.split(" ", 1)[1].strip()
        if not link.startswith(('http://', 'https://')):
             link = 'https://' + link

        official_link = link
        bot.reply_to(msg, f"Official link updated successfully to: {official_link}")
    except IndexError:
        bot.reply_to(msg, "Format: /setlink <full_link_or_channel_invite>")
    except Exception as e:
        bot.reply_to(msg, f"An error occurred: {e}")

@bot.message_handler(commands=['admin'])
def add_admin(msg):
    if msg.from_user.id != OWNER_ID:
        return
    try:
        uid = int(msg.text.split()[1])
        admins.add(uid)
        bot.reply_to(msg, f"Added admin: {uid}")
    except:
        bot.reply_to(msg, "Format: /admin <user_id>")

@bot.message_handler(commands=['dadmin'])
def del_admin(msg):
    if msg.from_user.id != OWNER_ID:
        return
    try:
        uid = int(msg.text.split()[1])
        if uid == OWNER_ID:
            bot.reply_to(msg, "Cannot remove owner")
            return
        admins.discard(uid)
        bot.reply_to(msg, f"Removed admin: {uid}")
    except:
        bot.reply_to(msg, "Format: /dadmin <user_id>")

# ----------- Show messages (History) -----------

@bot.message_handler(commands=['show'])
def show_history(msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        uid = int(msg.text.split()[1])
        msgs = user_messages.get(uid, [])
        if not msgs:
            bot.reply_to(msg, "No messages for this user.")
            return
        
        history = "\n".join([f"-> {m}" for m in msgs[-5:]])
        bot.reply_to(msg, f"**History for User {uid} (Last 5):**\n{history}", parse_mode='Markdown')
    except:
        bot.reply_to(msg, "Format: /show <user_id>")

@bot.message_handler(commands=['allm'])
def all_messages(msg):
    if not is_admin(msg.from_user.id):
        return
    if not user_messages:
        bot.reply_to(msg, "No messages from any users yet.")
        return

    summary = "\n".join([f"- User ID: `{uid}` ({len(msgs)} msgs)" for uid, msgs in user_messages.items()])
    bot.reply_to(msg, f"**All Users with Messages:**\n{summary}", parse_mode='Markdown')

# --------------------------- Admin to User (Messaging) ---------------------------

@bot.message_handler(commands=['mm'])
def admin_send_text(msg):
    if not is_admin(msg.from_user.id):
        return
    try:
        parts = msg.text.split(" ", 2)
        uid = int(parts[1])
        text = parts[2]
        bot.send_message(uid, f"**Admin Reply:** {text}", parse_mode='Markdown')
        bot.reply_to(msg, "Text message sent successfully.")
    except Exception as e:
        bot.reply_to(msg, f"Failed to send: {e}\nFormat: /mm <user_id> <text>")

@bot.message_handler(commands=['mp'])
def admin_send_media(msg):
    if not is_admin(msg.from_user.id):
        return
    if not msg.reply_to_message:
        bot.reply_to(msg, "Please reply to a photo or video with /mp <user_id>")
        return
    try:
        uid = int(msg.text.split()[1])
        rep = msg.reply_to_message
        
        if rep.photo:
            bot.send_photo(uid, rep.photo[-1].file_id, caption="Admin Media")
        elif rep.video:
            bot.send_video(uid, rep.video.file_id, caption="Admin Media")
        else:
            bot.reply_to(msg, "The replied message is not a photo or video.")
            return
        
        bot.reply_to(msg, "Media sent successfully.")
    except Exception as e:
        bot.reply_to(msg, f"Failed to send: {e}\nFormat: reply /mp <user_id> to a media")

# --------------------------- User to Admin forward ---------------------------

@bot.message_handler(content_types=['text','photo','video','document','audio','voice'])
def all_user_msg(msg):
    uid = msg.from_user.id
    if is_admin(uid):
        return

    user_info = f"{msg.from_user.first_name} (ID: `{uid}`)"

    if msg.text:
        save_msg(uid, msg.text)
        forward_text = f"**New Message from User:** {user_info}\n\n{msg.text}"
        bot.send_message(OWNER_ID, forward_text, parse_mode='Markdown')
    else:
        media_type = 'media'
        if msg.photo: media_type = 'photo'
        elif msg.video: media_type = 'video'
        
        save_msg(uid, f"<{media_type}>")
        bot.forward_message(OWNER_ID, uid, msg.message_id)
        bot.send_message(OWNER_ID, f"**New {media_type.capitalize()} from User:** {user_info}", parse_mode='Markdown')
        
    bot.reply_to(msg, "Your message has been forwarded to the admin. We'll get back to you soon.")


# --------------------------- Webhook Setup for Render ---------------------------

# 1. Telegram Updates Handle Route
@app.route('/' + BOT_TOKEN, methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    return "Error: Wrong Content Type", 403

# 2. Webhook Setter Route
@app.route("/")
def set_webhook_route():
    WEBHOOK_BASE_URL = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not WEBHOOK_BASE_URL:
        return "Error: RENDER_EXTERNAL_HOSTNAME not set.", 500
        
    WEBHOOK_URL = f"https://{WEBHOOK_BASE_URL}/{BOT_TOKEN}"
    
    if not BOT_TOKEN:
        return "Error: BOT_TOKEN not set in environment variables.", 500

    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        return f"Webhook successfully set to: {WEBHOOK_URL}", 200
    except Exception as e:
        return f"Failed to set webhook: {e}", 500

# 3. Main App Run (For local testing or as a fallback)
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
