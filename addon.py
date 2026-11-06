import socket
import re
from multiprocessing.managers import BaseManager
from queue import Queue, Empty
import threading
import time
from pathlib import Path
from typing import Any
from datetime import datetime
from mitmproxy import http, ctx
from mitmproxy.addonmanager import Loader
from utils import SekaiTool, NetworkPackage
from manager import QueueManager
from holodori import capture as holodori_capture

PATTERNS = [
    r'https://.*\.colorfulpalette\.org/.*/mysekai\?isForceAllReloadOnlyMysekai=(True|False)',
    r'https://.*\.colorfulpalette\.org/.*/mysekai/birthday-party/.*/delivery',
]

# /api/user/123123123123123/mysekai?isForceAllReloadOnlyMysekai=True
# /api/user/123123123123123/mysekai/birthday-party/2/delivery'


class SekaiDataSender:

    def __init__(self):
        self.queue: Queue = Queue(10)
        self.thread = threading.Thread(target=self.sender_loop, daemon=True)
        self.thread.start()

    def send_to_manager(self):
        manager = QueueManager(address=('', 50000), authkey=b'abracadabra')
        manager.connect()
        q: Queue = manager.get_queue()
        print('Connected to manager at 50000')
        while True:
            data = self.queue.get()
            q.put(data)

    def sender_loop(self):
        pending_data = None
        while True:
            manager = None
            q = None
            try:
                manager = QueueManager(address=('', 50000),
                                       authkey=b'abracadabra')
                manager.connect()
                q: Queue = manager.get_queue()
                print('Connected to manager at 50000')
                while True:
                    _ = q.qsize()

                    if pending_data is None:
                        try:
                            pending_data = self.queue.get(timeout=5)
                        except Empty:
                            pass

                    if pending_data is not None:
                        q.put(pending_data)
                        pending_data = None

            except Exception as ex:
                print('Sender Exception:', type(ex), ex)
                time.sleep(5)
            finally:
                del manager
                del q

    def send_data(self, data: Any):
        self.queue.put(data)


class ShowSekai:

    def __init__(self):
        self.data_sender = SekaiDataSender()

    def load(self, loader: Loader):
        loader.add_option(
            name='save_sekai',
            typespec=bool,
            default=False,
            help='save packets for testing',
        )

    def try_find_diamond(self, data: bytes):
        try:
            decrypted_data = SekaiTool.decrypt_data(data)
            harvest_count = SekaiTool.get_remain_harvest_count(decrypted_data)
            print('harvest_count:', harvest_count)
            ret = SekaiTool.find_diamond(decrypted_data, 12)
            if ret is None:
                return
            if ret:
                print('Find diamond')
                for d in ret:
                    print(d)
            else:
                print('Diamond not found')
        except Exception as ex:
            print('Exception:', ex)

    @staticmethod
    def get_time_filename():
        curr = datetime.now()
        return curr.strftime('packet_%Y%m%d_%H%M%S.bin')

    def handle_matched_flow(self, flow: http.HTTPFlow):
        data = flow.response.content
        if data:
            pack = NetworkPackage(flow.request.pretty_url, data)
            self.data_sender.send_data(pack)
            self.try_find_diamond(data)

            if ctx.options.save_sekai:
                try:
                    sekai_data_dir = Path('sekai_data')
                    sekai_data_dir.mkdir(exist_ok=True)
                    filename = sekai_data_dir / self.get_time_filename()
                    filename.write_bytes(data)
                    print('Save to', filename)
                except Exception as ex:
                    print('Error on save packet:', type(ex), ex)

    def handle_holodori_flow(self, flow: http.HTTPFlow):
        data = flow.response.raw_content
        if data:
            print('holodori packet:', flow.request.path)
            pack = NetworkPackage(flow.request.pretty_url, data, 'holodori')
            self.data_sender.send_data(pack)

    def response(self, flow: http.HTTPFlow):
        if holodori_capture.HOST in flow.request.pretty_url:
            # 使用tailscale捕捉後無法信任系統憑證
            # 使用http proxy無法捕捉到封包
            # 目前從supervisord.conf 取消捕捉holodori封包 此段功能無效
            print(flow.request.pretty_url)
            if flow.response and holodori_capture.is_target(
                    flow.request.host, flow.request.path,
                    flow.response.headers.get('content-type', '')):
                self.handle_holodori_flow(flow)
                return

        if 'colorfulpalette.org' in flow.request.pretty_url:
            print(flow.request.pretty_url)

            if (any(re.match(p, flow.request.pretty_url) for p in PATTERNS)
                    and flow.response):
                self.handle_matched_flow(flow)


addons = [ShowSekai()]
