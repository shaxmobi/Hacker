import telebot
import os
import zipfile
from pathlib import Path
import subprocess
import threading
from collections import defaultdict
import time

# ===== SOZLAMALAR =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "8383556025:AAE8Dw_9cbxbmsyLrXG5pdtP6VeGIPYjGxI")
ADMIN_ID = os.getenv("ADMIN_ID", "7992769498")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CWD_FILE = os.path.join(BASE_DIR, f".cwd_{ADMIN_ID}.txt")

# ===== CWD BOSHQARUV =====
def get_cwd():
    if not os.path.exists(CWD_FILE):
        with open(CWD_FILE, "w") as f:
            f.write(BASE_DIR)
    with open(CWD_FILE, "r") as f:
        return f.read().strip()

def set_cwd(path):
    with open(CWD_FILE, "w") as f:
        f.write(path)

def full_path(p=""):
    return os.path.join(get_cwd(), p) if p else get_cwd()

# ===== ADMIN TEKSHIRUV =====
def is_admin(message):
    return str(message.chat.id) == ADMIN_ID

# ===== BUYRUQLAR =====
@bot.message_handler(commands=["start"])
def start(msg):
    if is_admin(msg):
        bot.reply_to(msg, "✅ Bot ishga tushdi!\n/help - yordam")
    else:
        bot.reply_to(msg, "⛔️ Siz admin emassiz")

@bot.message_handler(commands=["pwd"])
def pwd(message):
    if not is_admin(message): return
    bot.reply_to(message, f"📍 Joriy papka:\n<code>{get_cwd()}</code>")

@bot.message_handler(commands=["cd"])
def cd(message):
    if not is_admin(message): return
    arg = message.text.replace("/cd", "").strip()

    if arg in ["", "~"]:
        set_cwd(BASE_DIR)
    elif arg == "..":
        set_cwd(str(Path(get_cwd()).parent))
    elif arg == "/":
        set_cwd("/")
    else:
        new = os.path.realpath(os.path.join(get_cwd(), arg))
        if os.path.isdir(new):
            set_cwd(new)
        else:
            bot.reply_to(message, "❌ Papka topilmadi")
            return

    bot.reply_to(message, f"📂 O'tildi:\n<code>{get_cwd()}</code>")

@bot.message_handler(commands=["ls"])
def ls(message):
    if not is_admin(message): return
    try:
        files = os.listdir(get_cwd())
        if not files:
            bot.reply_to(message, "📂 Papka bo'sh")
            return
        
        # Fayl va papkalarni ajratish
        dirs = [f"📁 {f}/" for f in files if os.path.isdir(full_path(f))]
        fls = [f"📄 {f}" for f in files if os.path.isfile(full_path(f))]
        
        result = "\n".join(dirs + fls)
        bot.reply_to(message, f"📂 <b>{get_cwd()}</b>\n\n{result}"[:4000])
    except Exception as e:
        bot.reply_to(message, f"❌ Xato: {e}")

@bot.message_handler(commands=["cat"])
def cat(message):
    if not is_admin(message): return
    file = message.text.replace("/cat", "").strip()
    if not file:
        bot.reply_to(message, "❌ Fayl nomini kiriting\n/cat filename")
        return
    
    path = full_path(file)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if len(content) > 4000:
                    bot.reply_to(message, f"📄 <code>{content[:4000]}</code>\n\n⚠️ Fayl katta, faqat birinchi 4000 belgi")
                else:
                    bot.reply_to(message, f"📄 <code>{content}</code>")
        except Exception as e:
            bot.reply_to(message, f"❌ O'qib bo'lmadi: {e}")
    else:
        bot.reply_to(message, "❌ Fayl topilmadi")

@bot.message_handler(commands=["edit"])
def edit(message):
    if not is_admin(message): return
    if "|" not in message.text:
        bot.reply_to(message, "❌ Format: <code>/edit fayl|matn</code>")
        return
    
    try:
        _, content = message.text.split(" ", 1)
        file, text = content.split("|", 1)
        with open(full_path(file.strip()), "w", encoding="utf-8") as f:
            f.write(text.strip())
        bot.reply_to(message, "✅ Saqlandi")
    except Exception as e:
        bot.reply_to(message, f"❌ Xato: {e}")

@bot.message_handler(commands=["del"])
def delete(message):
    if not is_admin(message): return
    file = message.text.replace("/del", "").strip()
    if not file:
        bot.reply_to(message, "❌ Nom kiriting: /del filename")
        return
    
    p = full_path(file)
    try:
        if os.path.isdir(p):
            import shutil
            shutil.rmtree(p)
            bot.reply_to(message, "✅ Papka o'chirildi")
        elif os.path.isfile(p):
            os.remove(p)
            bot.reply_to(message, "✅ Fayl o'chirildi")
        else:
            bot.reply_to(message, "❌ Topilmadi")
    except Exception as e:
        bot.reply_to(message, f"❌ Xato: {e}")

@bot.message_handler(commands=["mkdir"])
def mkdir(message):
    if not is_admin(message): return
    folder = message.text.replace("/mkdir", "").strip()
    if not folder:
        bot.reply_to(message, "❌ Nom kiriting: /mkdir foldername")
        return
    
    try:
        os.makedirs(full_path(folder), exist_ok=True)
        bot.reply_to(message, "✅ Papka yaratildi")
    except Exception as e:
        bot.reply_to(message, f"❌ Xato: {e}")

# ===== JARAYON BOSHQARUVI =====
user_processes = defaultdict(dict)

@bot.message_handler(commands=["run"])
def run_command(message):
    if not is_admin(message): 
        return
    
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Fayl nomini kiriting\n<code>/run test.py</code>")
        return
    
    filename = args[1].strip()
    path = full_path(filename)
    
    if not os.path.isfile(path):
        bot.reply_to(message, "❌ Fayl topilmadi")
        return
    
    # Oldingi jarayonni to'xtatish
    if user_id in user_processes:
        proc_info = user_processes[user_id]
        if 'process' in proc_info and proc_info['process'].poll() is None:
            try:
                proc_info['process'].terminate()
                time.sleep(0.3)
                if proc_info['process'].poll() is None:
                    proc_info['process'].kill()
            except:
                pass
            del user_processes[user_id]
    
    # Yangi jarayonni boshlash
    try:
        process = subprocess.Popen(
            ["python3", path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # stderr ni stdout bilan birlashtirish
            text=True,
            bufsize=0,  # Buffer o'chirish
            cwd=get_cwd()
        )
        
        user_processes[user_id] = {
            'process': process,
            'filename': filename,
            'chat_id': message.chat.id,
            'waiting_input': False
        }
        
        msg = bot.reply_to(
            message, 
            f"🚀 <code>{filename}</code> ishga tushdi\n\n"
            f"📥 Input kerak bo'lsa matn yuboring\n"
            f"⏹️ To'xtatish: /stop"
        )
        
        user_processes[user_id]['status_msg_id'] = msg.message_id
        
        # Output o'qish thread
        thread = threading.Thread(target=read_process_output, args=(user_id, process))
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        bot.reply_to(message, f"❌ Xato: <code>{str(e)}</code>")

def read_process_output(user_id, process):
    """Real-time output o'qish"""
    if user_id not in user_processes:
        return
    
    chat_id = user_processes[user_id]['chat_id']
    buffer = ""
    
    try:
        while True:
            char = process.stdout.read(1)
            
            if not char:
                if process.poll() is not None:
                    break
                continue
            
            buffer += char
            
            # Yangi qator yoki 200 belgidan oshsa yuborish
            if char == '\n' or len(buffer) >= 200:
                if buffer.strip():
                    try:
                        # Input kutilayotganini aniqlash
                        if any(keyword in buffer.lower() for keyword in ['input', 'enter', 'kiriting', ':']):
                            user_processes[user_id]['waiting_input'] = True
                        
                        bot.send_message(chat_id, f"<code>{buffer}</code>")
                    except Exception as e:
                        print(f"Send error: {e}")
                buffer = ""
        
        # Qolgan bufferni yuborish
        if buffer.strip():
            try:
                bot.send_message(chat_id, f"<code>{buffer}</code>")
            except:
                pass
                
    except Exception as e:
        print(f"Read error: {e}")
    finally:
        # Jarayon tugagach
        if user_id in user_processes:
            proc_info = user_processes[user_id]
            try:
                bot.send_message(
                    chat_id,
                    f"✅ <code>{proc_info['filename']}</code> tugadi"
                )
            except:
                pass
            del user_processes[user_id]

@bot.message_handler(func=lambda msg: not msg.text.startswith('/'))
def handle_user_input(message):
    """Foydalanuvchi input'ini jarayonga yuborish"""
    user_id = message.from_user.id
    
    if user_id not in user_processes:
        return
    
    proc_info = user_processes[user_id]
    process = proc_info['process']
    
    if process.poll() is None:
        try:
            process.stdin.write(message.text + "\n")
            process.stdin.flush()
            
            user_processes[user_id]['waiting_input'] = False
            
            # Echo qilish
            bot.send_message(message.chat.id, f"➡️ <code>{message.text}</code>")
                
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Input yuborishda xato: <code>{str(e)}</code>")
            if user_id in user_processes:
                del user_processes[user_id]
    else:
        bot.send_message(message.chat.id, "ℹ️ Jarayon allaqachon tugagan")
        if user_id in user_processes:
            del user_processes[user_id]

@bot.message_handler(commands=["stop"])
def stop_process(message):
    if not is_admin(message): 
        return
    
    user_id = message.from_user.id
    
    if user_id in user_processes:
        proc_info = user_processes[user_id]
        process = proc_info['process']
        filename = proc_info['filename']
        
        if process.poll() is None:
            try:
                process.terminate()
                time.sleep(0.5)
                if process.poll() is None:
                    process.kill()
                
                bot.reply_to(message, f"⏹️ <code>{filename}</code> to'xtatildi")
            except Exception as e:
                bot.reply_to(message, f"❌ Xato: <code>{str(e)}</code>")
        else:
            bot.reply_to(message, f"ℹ️ <code>{filename}</code> allaqachon tugagan")
        
        if user_id in user_processes:
            del user_processes[user_id]
    else:
        bot.reply_to(message, "ℹ️ Faol jarayon yo'q")

@bot.message_handler(commands=["status"])
def process_status(message):
    if not is_admin(message): 
        return
    
    user_id = message.from_user.id
    
    if user_id in user_processes:
        proc_info = user_processes[user_id]
        process = proc_info['process']
        filename = proc_info['filename']
        
        if process.poll() is None:
            status = "🟢 Ishlamoqda"
            if proc_info.get('waiting_input'):
                status += " (input kutmoqda)"
            bot.reply_to(message, f"{status}\n<code>{filename}</code>")
        else:
            bot.reply_to(message, f"🔴 Tugagan: <code>{filename}</code>")
    else:
        bot.reply_to(message, "ℹ️ Faol jarayon yo'q")

@bot.message_handler(commands=["backup"])
def backup(message):
    if not is_admin(message):
        return

    args = message.text.split(maxsplit=1)
    base = get_cwd()

    # /backup all
    if len(args) == 2 and args[1] == "all":
        zipname = f"backup_{Path(base).name}.zip"
        zip_path = f"/tmp/{zipname}"

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(base):
                    for file in files:
                        fp = os.path.join(root, file)
                        if fp == zip_path:
                            continue
                        arc = os.path.relpath(fp, base)
                        zipf.write(fp, arc)

            send_backup(zip_path, message)
        except Exception as e:
            bot.reply_to(message, f"❌ Xato:\n<code>{e}</code>")

    # /backup fayl_nomi
    elif len(args) == 2:
        target = full_path(args[1])

        if not os.path.exists(target):
            bot.reply_to(message, "❌ Fayl yoki papka topilmadi")
            return

        zipname = f"{Path(target).name}.zip"
        zip_path = f"/tmp/{zipname}"

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                if os.path.isfile(target):
                    zipf.write(target, os.path.basename(target))
                else:
                    for root, dirs, files in os.walk(target):
                        for file in files:
                            fp = os.path.join(root, file)
                            arc = os.path.relpath(fp, os.path.dirname(target))
                            zipf.write(fp, arc)

            send_backup(zip_path, message)
        except Exception as e:
            bot.reply_to(message, f"❌ Xato:\n<code>{e}</code>")

    # /backup (bo'laklab)
    else:
        try:
            for item in os.listdir(base):
                path = os.path.join(base, item)
                zip_path = f"/tmp/{item}.zip"

                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    if os.path.isfile(path):
                        zipf.write(path, item)
                    else:
                        for root, dirs, files in os.walk(path):
                            for file in files:
                                fp = os.path.join(root, file)
                                arc = os.path.relpath(fp, base)
                                zipf.write(fp, arc)

                send_backup(zip_path, message)

        except Exception as e:
            bot.reply_to(message, f"❌ Xato:\n<code>{e}</code>")
            
def send_backup(zip_path, message):
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)

    if size_mb > 49:
        bot.reply_to(
            message,
            f"❌ Backup katta: {size_mb:.2f} MB\nLimit ~50MB"
        )
    else:
        with open(zip_path, "rb") as f:
            bot.send_document(
                message.chat.id,
                f,
                caption=f"📦 Backup ({size_mb:.2f} MB)"
            )

    os.remove(zip_path)
    
@bot.message_handler(commands=["help"])
def help_cmd(message):
    if not is_admin(message):
        return

    text = """
🛠 <b>BOT BUYRUQLARI</b>

📂 <b>Fayl tizimi</b>
/pwd — joriy papka
/ls — fayllar ro'yxati
/cd papka — papkaga o'tish
/mkdir nom — papka yaratish
/del nom — o'chirish

📄 <b>Fayl</b>
/cat fayl — ko'rish
/edit fayl|matn — tahrirlash

⚙️ <b>Ishga tushirish</b>
/run fayl.py — Python script (interaktiv)
/stop — to'xtatish
/status — holat

📦 <b>Backup</b>
/backup — bo'laklab
/backup all — hammasi
/backup nom — aniq fayl
"""
    bot.reply_to(message, text)

print("✅ Bot ishga tushdi...")
bot.infinity_polling()