from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import requests
import json
import os
import uuid
from datetime import datetime

app = Flask(__name__)

GROQ_API_KEY = ""  # fallback

def get_groq_key():
    if os.path.exists("api_key.txt"):
        with open("api_key.txt") as f:
            k = f.read().strip()
            if k: return k
    return GROQ_API_KEY
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
CHATS_DIR = "chats"
PROMPT_FILE = "prompt.txt"
MODEL_FILE = "model.txt"
MEMORY_FILE = "memory.json"

DEFAULT_PROMPT = "Ты полезный ассистент. Сейчас 2026 год. Всегда отвечай только на том языке на котором пишет пользователь. Никаких переводов."
DEFAULT_MODEL = "llama-3.3-70b-versatile"

MODELS = [
    {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "desc": "Умный и быстрый"},
    {"id": "llama-3.1-8b-instant",    "name": "Llama 3.1 8B",  "desc": "Очень быстрый"},
    {"id": "mixtral-8x7b-32768",      "name": "Mixtral 8x7B",  "desc": "Длинный контекст"},
    {"id": "gemma2-9b-it",            "name": "Gemma 2 9B",    "desc": "От Google"},
]

os.makedirs(CHATS_DIR, exist_ok=True)

def load_prompt():
    if os.path.exists(PROMPT_FILE):
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return DEFAULT_PROMPT

def save_prompt(prompt):
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(prompt)

def load_model():
    if os.path.exists(MODEL_FILE):
        with open(MODEL_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return DEFAULT_MODEL

def save_model(model_id):
    with open(MODEL_FILE, "w", encoding="utf-8") as f:
        f.write(model_id)

def chat_path(chat_id):
    return os.path.join(CHATS_DIR, f"{chat_id}.json")

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_memory(facts):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)

def memory_to_text():
    facts = load_memory()
    if not facts:
        return ""
    lines = ["Вот что ты знаешь о пользователе:"]
    for f in facts:
        lines.append(f"- {f['fact']}")
    return "\n".join(lines)

def load_chat(chat_id):
    path = chat_path(chat_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            chat = json.load(f)
    else:
        chat = {"id": chat_id, "title": "Новый чат", "created": datetime.now().isoformat(),
                "messages": [{"role": "system", "content": load_prompt()}]}
    # Обновляем системный промпт с памятью
    mem = memory_to_text()
    base_prompt = load_prompt()
    full_prompt = base_prompt + ("\n\n" + mem if mem else "")
    if chat["messages"] and chat["messages"][0]["role"] == "system":
        chat["messages"][0]["content"] = full_prompt
    return chat

def save_chat(chat):
    with open(chat_path(chat["id"]), "w", encoding="utf-8") as f:
        json.dump(chat, f, ensure_ascii=False, indent=2)

def list_chats():
    chats = []
    for fname in sorted(os.listdir(CHATS_DIR), reverse=True):
        if fname.endswith(".json"):
            with open(os.path.join(CHATS_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
                chats.append({"id": data["id"], "title": data["title"], "created": data["created"]})
    return chats

def extract_text(file, filename):
    ext = filename.lower().split(".")[-1]
    if ext in ["txt", "md", "py", "js", "html", "css", "json", "csv"]:
        try:
            return file.read().decode("utf-8")
        except:
            return file.read().decode("latin-1")
    elif ext == "pdf":
        try:
            import fitz
            data = file.read()
            doc = fitz.open(stream=data, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            return f"Ошибка чтения PDF: {e}"
    return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/models", methods=["GET"])
def get_models():
    return jsonify({"models": MODELS, "current": load_model()})

@app.route("/models", methods=["POST"])
def set_model():
    model_id = request.json.get("model_id", "").strip()
    if not any(m["id"] == model_id for m in MODELS):
        return jsonify({"error": "Неизвестная модель"}), 400
    save_model(model_id)
    return jsonify({"status": "ok"})

@app.route("/chats", methods=["GET"])
def get_chats():
    return jsonify(list_chats())

@app.route("/chats", methods=["POST"])
def new_chat():
    chat_id = str(uuid.uuid4())[:8]
    chat = {"id": chat_id, "title": "Новый чат", "created": datetime.now().isoformat(),
            "messages": [{"role": "system", "content": load_prompt()}]}
    save_chat(chat)
    return jsonify({"id": chat_id})

@app.route("/chats/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    chat = load_chat(chat_id)
    return jsonify([m for m in chat["messages"] if m["role"] != "system"])

@app.route("/chats/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    path = chat_path(chat_id)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"status": "ok"})

@app.route("/chats/<chat_id>/rename", methods=["POST"])
def rename_chat(chat_id):
    chat = load_chat(chat_id)
    new_title = request.json.get("title", "").strip()
    if not new_title:
        return jsonify({"error": "Пустое название"}), 400
    chat["title"] = new_title
    save_chat(chat)
    return jsonify({"status": "ok"})

@app.route("/chats/<chat_id>/upload", methods=["POST"])
def upload_file(chat_id):
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Файл не найден"}), 400
    text = extract_text(file, file.filename)
    if text is None:
        return jsonify({"error": "Формат не поддерживается"}), 400
    return jsonify({"text": text[:12000], "filename": file.filename})

@app.route("/chats/<chat_id>/stream", methods=["POST"])
def stream_chat(chat_id):
    chat = load_chat(chat_id)
    user_msg = request.json.get("message")
    chat["messages"].append({"role": "user", "content": user_msg})
    if chat["title"] == "Новый чат":
        chat["title"] = user_msg[:30] + ("..." if len(user_msg) > 30 else "")
    model = load_model()

    def generate():
        full_reply = ""
        prompt_tokens = 0
        completion_tokens = 0
        try:
            resp = requests.post(GROQ_URL, headers={
                "Authorization": f"Bearer {get_groq_key()}",
                "Content-Type": "application/json"
            }, json={"model": model, "messages": chat["messages"], "stream": True,
                     "stream_options": {"include_usage": True}}, stream=True)

            for line in resp.iter_lines():
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"].get("content", "") if chunk.get("choices") else ""
                            if delta:
                                full_reply += delta
                                yield f"data: {json.dumps({'token': delta})}\n\n"
                            if chunk.get("usage"):
                                prompt_tokens = chunk["usage"].get("prompt_tokens", 0)
                                completion_tokens = chunk["usage"].get("completion_tokens", 0)
                        except:
                            pass

            chat["messages"].append({"role": "assistant", "content": full_reply})
            save_chat(chat)
            yield f"data: {json.dumps({'done': True, 'title': chat['title'], 'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/chats/<chat_id>/export")
def export_chat(chat_id):
    chat = load_chat(chat_id)
    msgs = [m for m in chat["messages"] if m["role"] != "system"]
    lines = [f"Чат: {chat['title']}", f"Дата: {chat['created']}", "=" * 40]
    for m in msgs:
        role = "Вы" if m["role"] == "user" else "Бот"
        lines.append(f"\n[{role}]\n{m['content']}")
    return Response("\n".join(lines), mimetype="text/plain",
                    headers={"Content-Disposition": f"attachment; filename={chat_id}.txt"})

@app.route("/prompt", methods=["GET"])
def get_prompt():
    return jsonify({"prompt": load_prompt()})

@app.route("/prompt", methods=["POST"])
def set_prompt():
    new_prompt = request.json.get("prompt", "").strip()
    if not new_prompt:
        return jsonify({"error": "Пустой промпт"}), 400
    save_prompt(new_prompt)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


# ====== ПАМЯТЬ ======
MEMORY_FILE = "memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_memory(facts):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)

def memory_to_text():
    facts = load_memory()
    if not facts:
        return ""
    lines = ["Вот что ты знаешь о пользователе:"]
    for f in facts:
        lines.append(f"- {f['fact']}")
    return "\n".join(lines)

@app.route("/memory", methods=["GET"])
def get_memory():
    return jsonify(load_memory())

@app.route("/memory", methods=["POST"])
def add_memory():
    fact = request.json.get("fact", "").strip()
    if not fact:
        return jsonify({"error": "Пустой факт"}), 400
    facts = load_memory()
    facts.append({"id": str(uuid.uuid4())[:8], "fact": fact, "created": datetime.now().isoformat()})
    save_memory(facts)
    return jsonify({"status": "ok"})

@app.route("/memory/<fact_id>", methods=["DELETE"])
def delete_memory(fact_id):
    facts = [f for f in load_memory() if f["id"] != fact_id]
    save_memory(facts)
    return jsonify({"status": "ok"})

@app.route("/memory/extract", methods=["POST"])
def extract_memory():
    """Автоматически извлекаем факты из сообщений через AI"""
    messages = request.json.get("messages", [])
    if not messages:
        return jsonify({"facts": []})

    prompt = """Из переписки ниже извлеки факты о пользователе (имя, профессия, интересы, предпочтения, цели и т.д.).
Верни ТОЛЬКО JSON массив строк, без лишнего текста. Пример: ["Зовут Алексей", "Работает программистом"]
Если фактов нет — верни пустой массив [].

Переписка:
""" + "\n".join([f"{m['role']}: {m['content']}" for m in messages[-10:] if m["role"] != "system"])

    try:
        resp = requests.post(GROQ_URL, headers={
            "Authorization": f"Bearer {get_groq_key()}",
            "Content-Type": "application/json"
        }, json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300
        })
        text = resp.json()["choices"][0]["message"]["content"].strip()
        text = text[text.find("["):text.rfind("]")+1]
        new_facts = json.loads(text)
        return jsonify({"facts": new_facts})
    except Exception as e:
        return jsonify({"facts": [], "error": str(e)})


# ====== ПАРОЛЬ ======
PIN_FILE = "pin.txt"

def load_pin():
    if os.path.exists(PIN_FILE):
        with open(PIN_FILE, "r") as f:
            return f.read().strip()
    return None

def save_pin(pin):
    with open(PIN_FILE, "w") as f:
        f.write(pin)

@app.route("/pin/check", methods=["POST"])
def pin_check():
    pin = request.json.get("pin", "")
    stored = load_pin()
    if not stored:
        return jsonify({"status": "no_pin"})
    return jsonify({"status": "ok" if pin == stored else "wrong"})

@app.route("/pin/set", methods=["POST"])
def pin_set():
    pin = request.json.get("pin", "").strip()
    if not pin:
        if os.path.exists(PIN_FILE):
            os.remove(PIN_FILE)
        return jsonify({"status": "removed"})
    if not pin.isdigit() or len(pin) < 4:
        return jsonify({"error": "Минимум 4 цифры"}), 400
    save_pin(pin)
    return jsonify({"status": "ok"})


# ====== ИЗБРАННОЕ ======
FAVORITES_FILE = "favorites.json"

def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_favorites(favs):
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)

@app.route("/favorites", methods=["GET"])
def get_favorites():
    return jsonify(load_favorites())

@app.route("/favorites", methods=["POST"])
def add_favorite():
    text = request.json.get("text", "").strip()
    chat_title = request.json.get("chat_title", "")
    if not text:
        return jsonify({"error": "Пусто"}), 400
    favs = load_favorites()
    fav_id = str(uuid.uuid4())[:8]
    favs.append({"id": fav_id, "text": text, "chat_title": chat_title, "created": datetime.now().isoformat()})
    save_favorites(favs)
    return jsonify({"status": "ok", "id": fav_id})

@app.route("/favorites/<fav_id>", methods=["DELETE"])
def delete_favorite(fav_id):
    favs = [f for f in load_favorites() if f["id"] != fav_id]
    save_favorites(favs)
    return jsonify({"status": "ok"})


# ====== СТАТИСТИКА ======
@app.route("/stats", methods=["GET"])
def get_stats():
    chats = []
    total_msgs = 0
    total_user = 0
    total_bot = 0
    total_chars = 0
    models_used = {}
    days = {}

    for fname in os.listdir(CHATS_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(CHATS_DIR, fname), "r", encoding="utf-8") as f:
            chat = json.load(f)
        msgs = [m for m in chat["messages"] if m["role"] != "system"]
        user_msgs = [m for m in msgs if m["role"] == "user"]
        bot_msgs = [m for m in msgs if m["role"] == "assistant"]
        total_msgs += len(msgs)
        total_user += len(user_msgs)
        total_bot += len(bot_msgs)
        for m in msgs:
            total_chars += len(m["content"])
        day = chat["created"][:10]
        days[day] = days.get(day, 0) + 1
        chats.append({
            "title": chat["title"],
            "msgs": len(msgs),
            "created": chat["created"][:10]
        })

    favs = load_favorites()
    mem = load_memory()

    return jsonify({
        "total_chats": len(chats),
        "total_msgs": total_msgs,
        "total_user": total_user,
        "total_bot": total_bot,
        "total_chars": total_chars,
        "total_favs": len(favs),
        "total_memory": len(mem),
        "avg_msgs": round(total_msgs / len(chats), 1) if chats else 0,
        "days": dict(sorted(days.items())[-14:]),
        "top_chats": sorted(chats, key=lambda x: x["msgs"], reverse=True)[:5]
    })


# ====== ШАБЛОНЫ ПРОМПТОВ ======
TEMPLATES_FILE = "templates_data.json"

def load_templates():
    if os.path.exists(TEMPLATES_FILE):
        with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [
        {"id": "t1", "name": "📝 Резюме", "text": "Сделай краткое резюме следующего текста: ", "color": "#6366f1"},
        {"id": "t2", "name": "🐛 Дебаг", "text": "Найди и исправь ошибки в коде: ", "color": "#10b981"},
        {"id": "t3", "name": "✍️ Улучши", "text": "Улучши стиль и грамматику текста: ", "color": "#f59e0b"},
        {"id": "t4", "name": "🌍 Перевод", "text": "Переведи на английский язык: ", "color": "#3b82f6"},
    ]

def save_templates(templates):
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)

@app.route("/templates", methods=["GET"])
def get_templates():
    return jsonify(load_templates())

@app.route("/templates", methods=["POST"])
def add_template():
    name = request.json.get("name", "").strip()
    text = request.json.get("text", "").strip()
    color = request.json.get("color", "#6366f1")
    if not name or not text:
        return jsonify({"error": "Заполни все поля"}), 400
    templates = load_templates()
    templates.append({"id": str(uuid.uuid4())[:8], "name": name, "text": text, "color": color})
    save_templates(templates)
    return jsonify({"status": "ok"})

@app.route("/templates/<tpl_id>", methods=["DELETE"])
def delete_template(tpl_id):
    templates = [t for t in load_templates() if t["id"] != tpl_id]
    save_templates(templates)
    return jsonify({"status": "ok"})

@app.route("/templates/<tpl_id>", methods=["PUT"])
def update_template(tpl_id):
    templates = load_templates()
    for t in templates:
        if t["id"] == tpl_id:
            t["name"] = request.json.get("name", t["name"]).strip()
            t["text"] = request.json.get("text", t["text"]).strip()
            t["color"] = request.json.get("color", t["color"])
            break
    save_templates(templates)
    return jsonify({"status": "ok"})


# ====== API КЛЮЧ ======
API_KEY_FILE = "api_key.txt"

def load_api_key():
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r") as f:
            return f.read().strip()
    return None

def save_api_key(key):
    with open(API_KEY_FILE, "w") as f:
        f.write(key)

@app.route("/apikey", methods=["GET"])
def get_apikey():
    key = load_api_key()
    return jsonify({"has_key": bool(key), "key_preview": key[:8] + "..." if key else None})

@app.route("/apikey", methods=["POST"])
def set_apikey():
    key = request.json.get("key", "").strip()
    if not key.startswith("gsk_") or len(key) < 20:
        return jsonify({"error": "Неверный формат ключа Groq"}), 400
    save_api_key(key)
    return jsonify({"status": "ok"})

import base64

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

@app.route("/chats/<chat_id>/image", methods=["POST"])
def send_image(chat_id):
    chat = load_chat(chat_id)
    file = request.files.get("image")
    text = request.form.get("message", "Что на этом изображении?")
    if not file:
        return jsonify({"error": "Изображение не найдено"}), 400
    img_data = base64.b64encode(file.read()).decode("utf-8")
    ext = file.filename.lower().split(".")[-1]
    mime = "image/jpeg" if ext in ["jpg","jpeg"] else f"image/{ext}"
    msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_data}"}}
        ]
    }
    chat["messages"].append(msg)
    if chat["title"] == "Новый чат":
        chat["title"] = text[:30]
    try:
        resp = requests.post(GROQ_URL, headers={
            "Authorization": f"Bearer {get_groq_key()}",
            "Content-Type": "application/json"
        }, json={"model": VISION_MODEL, "messages": chat["messages"], "max_tokens": 1024})
        reply = resp.json()["choices"][0]["message"]["content"]
        chat["messages"].append({"role": "assistant", "content": reply})
        save_chat(chat)
        return jsonify({"reply": reply, "title": chat["title"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/voice", methods=["POST"])
def voice_to_text():
    """Принимаем аудио, отправляем в Groq Whisper"""
    file = request.files.get("audio")
    if not file:
        return jsonify({"error": "Аудио не найдено"}), 400
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {get_groq_key()}"},
            files={"file": (file.filename, file.read(), file.content_type)},
            data={"model": "whisper-large-v3-turbo", "language": "ru"}
        )
        text = resp.json().get("text", "")
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/search", methods=["GET"])
def search_messages():
    q = request.args.get("q", "").strip().lower()
    if not q or len(q) < 2:
        return jsonify([])
    results = []
    for fname in os.listdir(CHATS_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(CHATS_DIR, fname), "r", encoding="utf-8") as f:
            chat = json.load(f)
        for msg in chat["messages"]:
            if msg["role"] == "system":
                continue
            if q in msg["content"].lower():
                idx = msg["content"].lower().find(q)
                snippet = msg["content"][max(0,idx-40):idx+80]
                results.append({
                    "chat_id": chat["id"],
                    "chat_title": chat["title"],
                    "role": msg["role"],
                    "snippet": snippet
                })
    return jsonify(results[:30])

# ====== ПЛАГИНЫ / АГЕНТ ======
import re as _re

def plugin_calc(expr):
    try:
        result = eval(_re.sub(r'[^0-9+\-*/().,\s]','',expr))
        return f"🧮 Результат: **{result}**"
    except:
        return "❌ Ошибка вычисления"

def plugin_weather(city):
    city = city.strip()
    try:
        r = requests.get(f"https://wttr.in/{requests.utils.quote(city)}?format=j1", timeout=8)
        data = r.json()
        cur = data["current_condition"][0]
        temp = cur["temp_C"]
        feels = cur["FeelsLikeC"]
        desc = cur["lang_ru"][0]["value"] if cur.get("lang_ru") else cur["weatherDesc"][0]["value"]
        return f"🌤 Погода в {city}:\n🌡 Температура: {temp}°C\n🤔 Ощущается: {feels}°C\n☁️ {desc}"
        return f"🌤 {r.text.strip()}"
    except:
        return "❌ Не удалось получить погоду"

def plugin_currency(text):
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        rates = r.json()["rates"]
        result = []
        pairs = [("USD","RUB"),("EUR","RUB"),("USD","EUR"),("BTC","USD")]
        for a,b in pairs:
            if a in rates and b in rates:
                rate = rates[b]/rates[a]
                result.append(f"**{a}→{b}**: {rate:.2f}")
        return "💱 Курсы валют:\n" + "\n".join(result)
    except:
        return "❌ Не удалось получить курсы"

def plugin_wiki(query):
    try:
        r = requests.get(
            "https://ru.wikipedia.org/api/rest_v1/page/summary/" + requests.utils.quote(query),
            timeout=5
        )
        data = r.json()
        title = data.get("title","")
        extract = data.get("extract","")[:500]
        return f"📖 **{title}**\n{extract}..."
    except:
        return "❌ Не нашёл в Wikipedia"

def plugin_time():
    from datetime import datetime
    now = datetime.now()
    return f"🕐 Сейчас: **{now.strftime('%d.%m.%Y %H:%M')}**"

def check_plugins(message):
    msg = message.lower().strip()
    if msg.startswith("/погода "):
        return plugin_weather(message[8:].strip())
    if msg.startswith("/курс") or msg.startswith("/валюта"):
        return plugin_currency(msg)
    if msg.startswith("/считай ") or msg.startswith("/calc "):
        expr = message.split(" ",1)[1]
        return plugin_calc(expr)
    if msg.startswith("/wiki ") or msg.startswith("/вики "):
        return plugin_wiki(message.split(" ",1)[1])
    if msg.startswith("/поиск ") or msg.startswith("/search "):
        return None  # обрабатывается отдельно
    if msg in ["/время", "/time"]:
        return plugin_time()
    return None

@app.route("/plugin", methods=["POST"])
def run_plugin():
    message = request.json.get("message","").strip()
    result = check_plugins(message)
    if result:
        return jsonify({"result": result})
    return jsonify({"result": None})

# ====== ВЕБ-ПОИСК ======
@app.route("/websearch", methods=["POST"])
def web_search():
    query = request.json.get("query", "").strip()
    if not query:
        return jsonify({"error": "Пустой запрос"}), 400
    try:
        # DuckDuckGo instant answer API
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=8
        )
        data = r.json()
        results = []
        
        # Abstract (основной ответ)
        if data.get("Abstract"):
            results.append(f"📖 **{data.get('Heading','')}**\n{data['Abstract']}")
        
        # Related topics
        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"• {topic['Text'][:200]}")
        
        # Answer (прямой ответ)
        if data.get("Answer"):
            results.insert(0, f"✅ **{data['Answer']}**")
        
        if not results:
            # Fallback - поиск через DDG HTML
            r2 = requests.get(
                f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8
            )
            import re
            snippets = re.findall(r'class="result__snippet">(.*?)</a>', r2.text)
            titles = re.findall(r'class="result__title".*?>(.*?)</a>', r2.text)
            for i, (t, s) in enumerate(zip(titles[:3], snippets[:3])):
                clean_t = re.sub(r'<.*?>', '', t).strip()
                clean_s = re.sub(r'<.*?>', '', s).strip()
                if clean_t and clean_s:
                    results.append(f"**{clean_t}**\n{clean_s}")
        
        if results:
            text = "\n\n".join(results[:5])
            return jsonify({"result": f"🌐 Результаты поиска по запросу «{query}»:\n\n{text}"})
        return jsonify({"result": "❌ Ничего не найдено"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ====== TTS (озвучка) ======
@app.route("/tts", methods=["POST"])
def text_to_speech():
    text = request.json.get("text", "").strip()[:1000]
    if not text:
        return jsonify({"error": "Пустой текст"}), 400
    try:
        # Groq TTS
        resp = requests.post(
            "https://api.groq.com/openai/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {get_groq_key()}",
                "Content-Type": "application/json"
            },
            json={"model": "playai-tts", "input": text, "voice": "Fritz-PlayAI", "response_format": "mp3"},
            timeout=30
        )
        if resp.status_code == 200:
            import base64
            audio_b64 = base64.b64encode(resp.content).decode("utf-8")
            return jsonify({"audio": audio_b64})
        return jsonify({"error": "TTS недоступен"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ====== УВЕДОМЛЕНИЯ ======
REMINDERS_FILE = "reminders.json"

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_reminders(r):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)

@app.route("/reminders", methods=["GET"])
def get_reminders():
    return jsonify(load_reminders())

@app.route("/reminders", methods=["POST"])
def add_reminder():
    text = request.json.get("text", "").strip()
    time_str = request.json.get("time", "").strip()
    if not text:
        return jsonify({"error": "Пустое напоминание"}), 400
    reminders = load_reminders()
    reminders.append({
        "id": str(uuid.uuid4())[:8],
        "text": text,
        "time": time_str,
        "created": datetime.now().isoformat(),
        "done": False
    })
    save_reminders(reminders)
    return jsonify({"status": "ok"})

@app.route("/reminders/<rid>", methods=["DELETE"])
def delete_reminder(rid):
    reminders = [r for r in load_reminders() if r["id"] != rid]
    save_reminders(reminders)
    return jsonify({"status": "ok"})

@app.route("/reminders/<rid>/done", methods=["POST"])
def done_reminder(rid):
    reminders = load_reminders()
    for r in reminders:
        if r["id"] == rid:
            r["done"] = True
    save_reminders(reminders)
    return jsonify({"status": "ok"})
