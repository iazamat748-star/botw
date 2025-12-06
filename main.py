import telebot
import google.generativeai as genai
from PIL import Image
import io
import requests
import os
import re
import random
import urllib.parse
from fastapi import FastAPI, Request

# ===========================
#        CONFIG (БАПТАУЛАР)
# ===========================

# ҚАУІПСІЗДІК: Кілттерді кодқа ашық жазбаймыз.
# Оларды Render-дің "Environment Variables" бөлімінен оқиды.
TELEGRAM_TOKEN = os.getenv('8556730396:AAGZtPA6mkMsvU_zKbp076kyB4NkhS_AH0s')
GOOGLE_API_KEY = os.getenv('AIzaSyCYvSYz9kkC6erbfMp2K1V5dxMfJlwBdbk')

# Егер кілттер табылмаса, бот жұмыс істемейді
if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
    print("⚠️ ҚАТЕ: API кілттері табылмады! Environment Variables тексеріңіз.")

# Gemini баптау
if GOOGLE_API_KEY:
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
- Код сұраса: Толық, жұмыс істейтін код жаз.
- Тіл: Қазақша.
"""

# Модельді жүктеу
model = genai.GenerativeModel(
    model_name='gemini-2.0-flash', # Жылдам әрі тегін нұсқа
    safety_settings=safety_settings,
    system_instruction=system_instruction
)

# Ботты инициализациялау (threaded=False Webhook үшін маңызды)
if TELEGRAM_TOKEN:
    bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
else:
    bot = None

chat_sessions = {}

# ===========================
#   FLUX IMAGE GENERATION
# ===========================
def generate_image_flux(prompt):
    """Flux моделі арқылы сурет салу"""
    clean_prompt = urllib.parse.quote(prompt.strip())
    seed = random.randint(1, 999999)
    # Pollinations.ai API қолдану
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
    """Мәтін ішінен кодты тауып, файлға сақтау"""
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

            # Файлды уақытша жазу
            with open(filename, "w", encoding="utf-8") as f:
                f.write(code.strip())
            saved_files.append(filename)

    return saved_files

# ===========================
#      LONG MESSAGE SPLIT
# ===========================
def send_long_message(chat_id, text):
    """4096 символдан ұзын мәтінді бөліп жіберу"""
    for i in range(0, len(text), 4000):
        chunk = text[i:i+4000]
        try:
            bot.send_message(chat_id, chunk, parse_mode='Markdown')
        except:
            # Markdown қате кетсе, жай мәтін қылып жіберу
            bot.send_message(chat_id, chunk)

# ===========================
#        BOT HANDLER
# ===========================
# Тек бот бар болса ғана handler қосамыз
if bot:
    @bot.message_handler(content_types=['text', 'photo'])
    def handle_all(message):
        chat_id = message.chat.id
        
        try:
            # RESET COMMAND
            if message.text and message.text.lower() in ['/reset', 'тазалау']:
                chat_sessions.pop(chat_id, None)
                bot.send_message(chat_id, "♻️ Жүйе жаңартылды! Жаңа тақырып бастаңыз.")
                return

            # IMAGE GENERATION (Сурет салу)
            if message.text and message.text.lower().startswith('сурет '):
                raw_prompt = message.text[6:]
                bot.send_message(chat_id, "🎨 Сурет салынып жатыр... (Flux)")
                bot.send_chat_action(chat_id, 'upload_photo')

                # Промптты ағылшыншаға аудару (дәлірек болу үшін)
                instruction = f"Translate to English for Flux prompt ONLY, keep details: '{raw_prompt}'"
                prompt_resp = model.generate_content(instruction)
                english_prompt = prompt_resp.text.strip()

                image_data = generate_image_flux(english_prompt)
                
                if image_data:
                    bot.send_photo(chat_id, image_data, caption=f"Prompt: {english_prompt}")
                else:
                    bot.send_message(chat_id, "⚠️ Сервер жауап бермеді, кейінірек көріңіз.")
                return

            # GEMINI CHAT SESSIONS
            if chat_id not in chat_sessions:
                chat_sessions[chat_id] = model.start_chat(history=[])
            session = chat_sessions[chat_id]

            bot.send_chat_action(chat_id, 'typing')

            # PHOTO ANALYSIS (Суретті талдау)
            if message.content_type == 'photo':
                file_info = bot.get_file(message.photo[-1].file_id)
                img_data = bot.download_file(file_info.file_path)
                image = Image.open(io.BytesIO(img_data))
                caption = message.caption if message.caption else "Суретте не бар екенін толық талдап бер."

                response = session.send_message([caption, image])
                send_long_message(chat_id, response.text)
                return

            # TEXT MESSAGES (Мәтін)
            if message.content_type == 'text':
                response = session.send_message(message.text)
                send_long_message(chat_id, response.text)

                # CODE FILE HANDLING (Код файлын жасау)
                if "```" in response.text:
                    files = save_code_file(response.text)
                    for filename in files:
                        with open(filename, 'rb') as f:
                            bot.send_document(chat_id, f, caption="📂 Сіз сұраған код файлы")
                        
                        # МАҢЫЗДЫ: Сервер қоқысқа толмау үшін файлды өшіреміз
                        os.remove(filename)
                return

        except Exception as e:
            # Қате болса сессияны тазалау
            chat_sessions.pop(chat_id, None)
            bot.send_message(chat_id, f"❌ Қате орын алды: {e}\nЖад тазаланды.")

# ===========================
#      FASTAPI SERVER
# ===========================
app = FastAPI()

@app.get("/")
def home():
    return {"status": "Bot is running on Render!"}

@app.post("/")
async def telegram_webhook(request: Request):
    """Telegram-нан келетін жаңа хабарламаларды қабылдау"""
    if not bot:
        return {"error": "Bot token not configured"}

    try:
        json_data = await request.json()
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return {"ok": True}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"error": str(e)}

# Render бұл файлды uvicorn арқылы автоматты түрде іске қосады.
# Төмендегі код тек локалды тестілеу үшін қажет:
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)