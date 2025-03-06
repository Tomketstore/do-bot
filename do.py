import requests
import json
import datetime
import time
import random
import string
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Konfigurasi
BOT_TOKEN = "isi bot token"
DO_TOKEN = "token digital ocean"
ADMIN_ID = 1708391805 

HEADERS = {"Authorization": f"Bearer {DO_TOKEN}", "Content-Type": "application/json"}

# Fungsi membatasi akses hanya untuk admin
def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

# Fungsi mendapatkan daftar region
def get_regions():
    url = "https://api.digitalocean.com/v2/regions"
    response = requests.get(url, headers=HEADERS).json()
    return [r["slug"] for r in response["regions"]]

# Fungsi mendapatkan daftar OS (Lengkap)
def get_images():
    url = "https://api.digitalocean.com/v2/images?type=distribution"
    response = requests.get(url, headers=HEADERS).json()
    return {i["slug"]: f"{i['distribution']} {i['name']}" for i in response["images"]}

# Fungsi mendapatkan daftar spesifikasi
def get_sizes():
    url = "https://api.digitalocean.com/v2/sizes"
    response = requests.get(url, headers=HEADERS).json()
    return [s["slug"] for s in response["sizes"]]

# Generate Password Root
def generate_password(length=12):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Handler untuk /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    await update.message.reply_text("Welcome to DigitalOcean VPS Bot!\n\nGunakan Command\n/create\n/cek_droplet\n/hapus_droplet\n/rebuild_droplet")

# Mulai proses buat droplet
async def create_vps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    keyboard = [[InlineKeyboardButton(r, callback_data=f"region:{r}")] for r in get_regions()]
    await update.message.reply_text("Pilih Region:", reply_markup=InlineKeyboardMarkup(keyboard))

# Pilih OS (Lengkap)
async def select_os(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update):
        return
    
    context.user_data["region"] = query.data.split(":")[1]
    keyboard = [[InlineKeyboardButton(name, callback_data=f"os:{slug}")] for slug, name in get_images().items()]
    await query.message.edit_text("Pilih OS:", reply_markup=InlineKeyboardMarkup(keyboard))

# Pilih spesifikasi
async def select_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update):
        return
    
    context.user_data["os"] = query.data.split(":")[1]
    keyboard = [[InlineKeyboardButton(s, callback_data=f"size:{s}")] for s in get_sizes()]
    await query.message.edit_text("Pilih Spesifikasi:", reply_markup=InlineKeyboardMarkup(keyboard))

# Konfirmasi & Buat Droplet dengan Password Root
async def create_droplet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update):
        return
    
    context.user_data["size"] = query.data.split(":")[1]
    password = generate_password()

    user_data = f"""#cloud-config
chpasswd:
  list: |
    root:{password}
  expire: False
"""

    data = {
        "name": "droplet-vps",
        "region": context.user_data["region"],
        "size": context.user_data["size"],
        "image": context.user_data["os"],
        "user_data": user_data
    }

    response = requests.post("https://api.digitalocean.com/v2/droplets", headers=HEADERS, json=data).json()

    if "droplet" in response:
        droplet = response["droplet"]
        droplet_id = droplet["id"]
        created_at = droplet["created_at"]
        
        await query.message.edit_text(f"Droplet dibuat! ID: {droplet_id}\nMenunggu 60 detik untuk mendapatkan detail VPS...")

        time.sleep(60)
        
        droplet_info = requests.get(f"https://api.digitalocean.com/v2/droplets/{droplet_id}", headers=HEADERS).json()
        if "droplet" in droplet_info:
            networks = droplet_info["droplet"].get("networks", {}).get("v4", [])
            if networks:
                ip_address = networks[0]["ip_address"]
                date_created = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"VPS berhasil dibuat:\n\nIP: {ip_address}\nUsername: root\nPassword: {password}\nTanggal Dibuat: {date_created}")
            else:
                await context.bot.send_message(chat_id=ADMIN_ID, text="Gagal mendapatkan IP VPS.")
    else:
        await query.message.edit_text("Gagal membuat droplet!")

# Cek status droplet
async def check_droplet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    response = requests.get("https://api.digitalocean.com/v2/droplets", headers=HEADERS).json()
    if "droplets" in response and response["droplets"]:
        message = "\n".join([f"ID: {d['id']}, IP: {d.get('networks', {}).get('v4', [{}])[0].get('ip_address', 'N/A')}" for d in response["droplets"]])
    else:
        message = "Tidak ada droplet aktif."
    
    await update.message.reply_text(message)

# Rebuild droplet
async def rebuild_droplet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    args = context.args
    if args:
        droplet_id = args[0]
        response = requests.post(f"https://api.digitalocean.com/v2/droplets/{droplet_id}/actions", headers=HEADERS, json={"type": "rebuild"})
        await update.message.reply_text("Rebuild droplet sedang diproses.")
    else:
        await update.message.reply_text("Gunakan perintah: /rebuild_droplet [droplet_id]")

# Hapus droplet
async def delete_droplet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    args = context.args
    if args:
        droplet_id = args[0]
        requests.delete(f"https://api.digitalocean.com/v2/droplets/{droplet_id}", headers=HEADERS)
        await update.message.reply_text("Droplet berhasil dihapus.")
    else:
        await update.message.reply_text("Gunakan perintah: /hapus_droplet [droplet_id]")

# Handler utama
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create_vps))  # Ganti dari /start ke /create
    app.add_handler(CallbackQueryHandler(select_os, pattern="^region:"))
    app.add_handler(CallbackQueryHandler(select_size, pattern="^os:"))
    app.add_handler(CallbackQueryHandler(create_droplet, pattern="^size:"))
    app.add_handler(CommandHandler("cek_droplet", check_droplet))
    app.add_handler(CommandHandler("rebuild_droplet", rebuild_droplet))
    app.add_handler(CommandHandler("hapus_droplet", delete_droplet))

    app.run_polling()

if __name__ == "__main__":
    main()