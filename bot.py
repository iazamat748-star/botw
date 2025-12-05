import telebot
import google.generativeai as genai
from PIL import Image
import io
import requests
import os
import webbrowser
import re
import random
import urllib.parse

from fastapi import FastAPI, Request

# ===========================
#        CONFIG
# ===========================

TELEGRAM_TOKEN = '8556730396:AAGZtPA6mkMsvU_zKbp076kyB4NkhS_AH0s'
GOOGLE_API_KEY = 'AIzaSyCYvSYz9kkC6erbfMp2K1V5dxMfJlwBdbk'

genai.configure(api_key=GOOGLE_API_KEY)

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

system_instruction = """
Сен - QNeuro11, Қазақстанның озық жасанды интеллект жүйесісің.
3 сала бойынша сарапшысың:

1. 🎓 EDUCATION AI (Білім): Мұғалімдерге жоспар, Студенттерге көмек, IT код жазу.
2. 🏙 SMART CITY AI (Қала): Кептеліс, жол сапасы, экология суреттерін талдау.
3. 🏥 HEALTH AI (Денсаулық): Симптомдар мен Рентген/МРТ суреттерін талдау (Ескертумен).

ЕРЕЖЕЛЕР:
- Код сұраса: Толық, жұмыс істейтін код жаз (```python, ```html).
- Тіл: Қазақша.
"""

model = genai.GenerativeModel(
    model_name='gemini-2.5-pro',
    safety_settings=safety_settings,
    system_instruction=system_instruction
)

bot = telebot.TeleBot(TELEGRAM_TOKEN)
chat_sessions = {}

# ===========================
#   FLUX IMAGE GENERATION
# ===========================

def generate_image_flux(prompt):
    clean_prompt = urllib.parse.quote(prompt.strip())
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&model=flux&nologo=true&seed={seed}"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        print(f"Сурет қатесі: {e}")
    return None

# ===========================
#     CODE FILE SAVER
# ===========================

def save_code_file(text):
    pattern = r"```(\w+)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    saved_files = []

    extensions = {
        'html': '.html', 'python': '.py', 'py': '.py',
        'js': '.js', 'cpp': '.cpp', 'java': '.java', 'sql': '.sql'
    }

    if matches:
        for lang, code in matches:
            ext = extensions.get(lang.lower(), '.txt')
            rand_id = random.randint(100, 999)
            filename = f"Project_AI_{rand_id}{ext}"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(code.strip())
            saved_files.append(filename)

    return saved_files

# ===========================
#      LONG MESSAGE SPLIT
# ===========================

def send_long_message(chat_id, text):
    for i in range(0, len(text), 4000):
        try:
            bot.send_message(chat_id, text[i:i+4000], parse_mode='Markdown')
        except:
            bot.send_message(chat_id, text[i:i+4000])

# ===========================
#         FASTAPI SERVER
# ===========================

app = FastAPI()

@app.post("/")
async def telegram_webhook(request: Request):
    json_data = await request.json()
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return {"ok": True}

# ===========================
#        BOT HANDLER
# ===========================

@bot.message_handler(content_types=['text', 'photo'])
def handle_all(message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'typing')

    try:
        # Reset
        if message.text and message.text.lower() in ['/reset', 'тазалау']:
            chat_sessions.pop(chat_id, None)
            bot.send_message(chat_id, "♻️ Жүйе жаңартылды!")
            return

        # IMAGE GENERATION
        if message.text and message.text.lower().startswith('сурет '):
            raw_prompt = message.text[6:]
            bot.send_message(chat_id, "🎨 Сурет салынып жатыр...")
            bot.send_chat_action(chat_id, 'upload_photo')

            instruction = f"Translate to English for Flux prompt ONLY: '{raw_prompt}'"
            prompt_resp = model.generate_content(instruction)

            image_data = generate_image_flux(prompt_resp.text.strip())
            if image_data:
                bot.send_photo(chat_id, image_data)
            else:
                bot.send_message(chat_id, "Сервер жауап бермеді.")
            return

        # Create chat session
        if chat_id not in chat_sessions:
            chat_sessions[chat_id] = model.start_chat(history=[])
        session = chat_sessions[chat_id]

        # PHOTO
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)
            img_data = bot.download_file(file_info.file_path)
            image = Image.open(io.BytesIO(img_data))
            caption = message.caption if message.caption else "Суреттерді талда."

            response = session.send_message([caption, image])
            send_long_message(chat_id, response.text)
            return

        # TEXT
        if message.content_type == 'text':
            response = session.send_message(message.text)
            send_long_message(chat_id, response.text)

            # CODE FILES
            if "```" in response.text:
                files = save_code_file(response.text)
                for filename in files:
                    with open(filename, 'rb') as f:
                        bot.send_document(chat_id, f, caption="Міне, дайын код!")

                    if ".html" in filename:
                        try:
                            webbrowser.open('file://' + os.path.realpath(filename))
                        except:
                            pass
        return

    except Exception as e:
        chat_sessions.pop(chat_id, None)
        bot.send_message(chat_id, f"Қате: {e}")

# ===========================
#       LOCAL RUN MODE
# ===========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080)

