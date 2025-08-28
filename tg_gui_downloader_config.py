# tg_gui_downloader_config.py
import os, json, asyncio
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget,
    QLabel, QFileDialog, QMessageBox, QListWidgetItem
)
from PyQt5.QtCore import Qt
from telethon import TelegramClient
from qasync import QEventLoop, asyncSlot

CONFIG_FILE = "config.json"
SESSION_FILE = "my_session.session"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def unique_path(path):
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(path):
        path = f"{base}({counter}){ext}"
        counter += 1
    return path

class TelegramDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram 批量下载器")
        self.resize(600, 800)
        self.config = load_config()
        self.client = None
        self.dialogs = []
        self.messages = []

        layout = QVBoxLayout()

        # 保存路径选择
        self.path_label = QLabel(f"保存路径: {self.config.get('download_dir', os.getcwd())}")
        layout.addWidget(self.path_label)
        self.choose_path_button = QPushButton("选择保存文件夹")
        self.choose_path_button.clicked.connect(self.choose_folder)
        layout.addWidget(self.choose_path_button)

        # 群组列表
        layout.addWidget(QLabel("请选择群组/频道："))
        self.group_list = QListWidget()
        layout.addWidget(self.group_list)
        self.refresh_button = QPushButton("刷新群组/频道列表")
        self.refresh_button.clicked.connect(self.load_dialogs)
        layout.addWidget(self.refresh_button)

        # 消息文件列表
        layout.addWidget(QLabel("请选择要下载的文件："))
        self.msg_list = QListWidget()
        self.msg_list.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.msg_list)

        # 下载按钮
        self.download_button = QPushButton("开始下载选中文件")
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)

        # 状态与进度
        self.status_label = QLabel("状态: 等待操作")
        layout.addWidget(self.status_label)
        self.progress_label = QLabel("")
        layout.addWidget(self.progress_label)

        self.setLayout(layout)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择保存路径")
        if folder:
            self.config['download_dir'] = folder
            save_config(self.config)
            self.path_label.setText(f"保存路径: {folder}")

    async def connect_client(self):
        if not os.path.exists(SESSION_FILE):
            QMessageBox.critical(self, "错误", "请先用 login_cli.exe 登录生成 session 文件")
            return False
        try:
            self.client = TelegramClient(
                SESSION_FILE,
                int(self.config["api_id"]),
                self.config["api_hash"]
            )
            await self.client.connect()
            if not await self.client.is_user_authorized():
                QMessageBox.critical(self, "错误", "Session 未授权，请先用 login_cli.exe 登录")
                return False
            self.status_label.setText("状态: 已连接")
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"连接失败: {e}")
            return False

    @asyncSlot()
    async def load_dialogs(self):
        if not self.client:
            QMessageBox.warning(self, "提示", "请先连接 Telegram！")
            return
        self.group_list.clear()
        dialogs = await self.client.get_dialogs()
        self.dialogs = [d for d in dialogs if d.is_group or d.is_channel]
        for d in self.dialogs:
            self.group_list.addItem(d.name)
        self.status_label.setText(f"状态: 已加载 {len(self.dialogs)} 个群组/频道")
        self.msg_list.clear()

    @asyncSlot()
    async def load_messages(self, dialog_index):
        if dialog_index < 0:
            return
        self.msg_list.clear()
        target = self.dialogs[dialog_index].entity
        self.messages = [msg async for msg in self.client.iter_messages(target, limit=200) if msg.file and msg.file.name]
        for msg in self.messages:
            item = QListWidgetItem(f"{msg.file.name}")
            item.setCheckState(Qt.Unchecked)
            self.msg_list.addItem(item)

    @asyncSlot()
    async def start_download(self):
        selected_items = [i for i in range(self.msg_list.count())
                          if self.msg_list.item(i).checkState() == Qt.Checked]

        save_dir = self.config.get("download_dir", os.getcwd())
        semaphore = asyncio.Semaphore(5)
        downloaded_files = 0

        # 如果用户没有勾选任何文件，默认下载群组所有文件
        if not selected_items:
            if not self.messages:
                QMessageBox.warning(self, "提示", "当前群组没有可下载的文件！")
                return
            selected_items = list(range(len(self.messages)))

        async def download_message(msg):
            nonlocal downloaded_files
            path = unique_path(os.path.join(save_dir, msg.file.name))
            async with semaphore:
                self.status_label.setText(f"正在下载: {os.path.basename(path)}")
                await msg.download_media(file=path)
                downloaded_files += 1
                self.progress_label.setText(f"已下载 {downloaded_files}/{len(selected_items)} 个文件")

        tasks = [download_message(self.messages[i]) for i in selected_items]
        self.status_label.setText("状态: 开始下载…")
        await asyncio.gather(*tasks)
        self.status_label.setText("状态: 下载完成！")
        QMessageBox.information(self, "完成", f"下载完成！文件保存在 {save_dir}")

# ---------------------- 主程序 ----------------------
def main():
    import sys
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    win = TelegramDownloader()
    win.show()

    # 当选择群组时加载对应消息
    def on_group_changed():
        asyncio.ensure_future(win.load_messages(win.group_list.currentRow()))
    win.group_list.currentRowChanged.connect(on_group_changed)

    with loop:
        loop.run_until_complete(win.connect_client())
        loop.run_forever()

if __name__ == "__main__":
    main()
