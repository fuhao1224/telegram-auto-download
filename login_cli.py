# login_cli.py
import asyncio
import os
import json
import subprocess
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

CONFIG_FILE = "config.json"
SESSION_FILE = "my_session.session"
GUI_EXE = "tg_gui_downloader_config.exe"  # GUI exe 文件名

def save_config(api_id, api_hash):
    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "download_dir": os.getcwd()  # 默认保存目录为当前，用户可在 GUI 修改
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

async def main():
    api_id = int(input("请输入 API ID: "))
    api_hash = input("请输入 API Hash: ")
    phone = input("请输入手机号: ")

    client = TelegramClient(SESSION_FILE, api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = input("请输入 Telegram 验证码: ")
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("请输入二步验证密码: ")
            await client.sign_in(password=password)

    print("登录成功，session 文件已生成！")
    save_config(api_id, api_hash)

    # 登录成功后自动启动 GUI exe
    if os.path.exists(GUI_EXE):
        print("正在启动 GUI...")
        subprocess.Popen([GUI_EXE], shell=True)
    else:
        print(f"未找到 {GUI_EXE}，请确保 GUI exe 与 CLI 在同一目录下")

asyncio.run(main())
