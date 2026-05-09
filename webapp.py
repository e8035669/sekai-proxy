import asyncio
from dataclasses import dataclass, field
from nicegui import ui, background_tasks, app, Event, run
from queue import Queue, Empty
from collections import deque
import logging
from datetime import datetime
import time
import json

from utils import DiamondPlace, ResourcePlace, SekaiMapDraw, SekaiResources, SekaiTool, NetworkPackage
from manager import QueueManager


class DequeLogger(logging.Handler):

    def __init__(self,
                 mydeque: deque,
                 level: int | str = 0,
                 on_message=None) -> None:
        super().__init__(level)
        self.mydeque = mydeque
        self.on_message = on_message

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.mydeque.append(msg)
            if self.on_message:
                self.on_message(self)
        except Exception:
            self.handleError(record)


@dataclass
class LastDiamondStatus:
    last_update: float = 0
    diamonds: list[DiamondPlace] = field(default_factory=list)


@dataclass
class LastHarvestMapStatus:
    last_update: float = 0
    harvest_map: dict = field(default_factory=dict)
    current_ids: dict[str, set[int]] = field(default_factory=dict)


class Storage:
    INSTANCE = None

    def __init__(self) -> None:
        self.messages = deque(maxlen=100)
        self.log_handle = DequeLogger(self.messages, 0, self.on_message_append)
        self.example_diamond = DiamondPlace(
            5, {
                'resourceType': 'mysekai_material',
                'resourceId': 1,
                'positionX': -1,
                'positionZ': 18,
                'hp': 61,
                'seq': 99,
                'mysekaiSiteHarvestResourceDropStatus': 'before_drop',
                'quantity': 1,
                'mysekaiSiteHarvestSpawnLimitedRelationGroupId': 2503,
            })

        self.event = Event[str]()
        self.last_found_diamonds: dict[str, LastDiamondStatus] = {}
        self.last_harvest_map: dict[str, LastHarvestMapStatus] = {}
        self.append_example('123456')
        pass

    @classmethod
    def instance(cls):
        if cls.INSTANCE is None:
            cls.INSTANCE = cls()
        return cls.INSTANCE

    def on_message_append(self, sender):
        show_messages.refresh()

    def clear_messages(self):
        self.messages.clear()
        show_messages.refresh()

    def update_diamonds(self, user_id: str, diamonds: list[DiamondPlace]):
        if user_id not in self.last_found_diamonds:
            status = LastDiamondStatus()
            self.last_found_diamonds[user_id] = status
        else:
            status = self.last_found_diamonds[user_id]
        status.last_update = time.time()
        status.diamonds = diamonds

    def update_harvest_map(self, user_id: str, harvest_maps: dict):
        if user_id not in self.last_harvest_map:
            status = LastHarvestMapStatus()
            self.last_harvest_map[user_id] = status
        else:
            status = self.last_harvest_map[user_id]
        status.last_update = time.time()
        status.harvest_map = harvest_maps

        exist_ids = SekaiTool.current_exist_ids(harvest_maps)
        status.current_ids = exist_ids

    def emit_event(self, user_id):
        self.event.emit(user_id)

    def append_example(self, user_id: str):
        diamonds = [self.example_diamond] * 2
        self.update_diamonds(user_id, diamonds)
        with open('test1.json') as f:
            data = json.load(f)
        harvest_map = SekaiTool.extract_harvest_map(data)
        if harvest_map is not None:
            self.update_harvest_map(user_id, harvest_map)
        self.emit_event(user_id)


def try_find_diamond(pack: NetworkPackage):
    logger = logging.getLogger()
    try:
        storage = Storage.instance()
        user_id = SekaiTool.extract_user_id(pack.url)
        if not user_id:
            logger.info('Cannot extract user_id')
            return
        decrypted_data = SekaiTool.decrypt_data(pack.data)
        harvest_count = SekaiTool.get_remain_harvest_count(decrypted_data)
        logger.info('harvest_count: %s', harvest_count)

        harvest_map = SekaiTool.extract_harvest_map(decrypted_data)
        if harvest_map is not None:
            storage.update_harvest_map(user_id, harvest_map)

        ret = SekaiTool.find_diamond(decrypted_data, 12)
        # ret = find_diamond(decrypted_data, 1)
        if ret is None:
            return
        if ret:
            logger.info('Find diamond')
            for d in ret:
                logger.info('%s', d)
        else:
            logger.info('Diamond not found')
        storage.update_diamonds(user_id, ret)
        storage.emit_event(user_id)
    except Exception as ex:
        logger.error('Exception: %s %s', type(ex), ex)


async def background_handle():
    logger = logging.getLogger()
    manager = QueueManager(address=('', 50000), authkey=b'abracadabra')
    manager.connect()
    queue: Queue = manager.get_queue()
    logger.info('connect to manager')
    while True:
        await asyncio.sleep(1)
        try:
            pack: NetworkPackage = queue.get_nowait()
            logger.info('get pack for: %s', pack.url)
            logger.info('get data %s bytes', len(pack.data))
            try_find_diamond(pack)
        except Empty:
            pass


async def background():
    logger = logging.getLogger()
    while True:
        try:
            await background_handle()
        except Exception as e:
            logger.error('background connect fail: %s %s', type(e), e)
            await asyncio.sleep(10)
            pass


async def background_material():
    logger = logging.getLogger()
    while True:
        try:
            sekai_material = SekaiResources.instance()
            sekai_material.update()
            await asyncio.sleep(86400)
        except Exception as e:
            logger.error('update material fail: %s %s', type(e), e)
            await asyncio.sleep(30)


@ui.refreshable
def show_messages():
    storage = Storage.instance()
    log = ui.log()
    for i in storage.messages:
        log.push(i)


class InitialPage():

    def __init__(self):

        with ui.header().classes('items-center'):
            with ui.row().classes('w-full max-w-3xl mx-auto'):
                ui.label('Sekai Treasure').props('color=white').classes(
                    'text-xl')

        with ui.column().classes('w-full max-w-3xl mx-auto'):
            ui.label('初始設定').classes('text-h5')
            ui.label('請先輸入帳號id')
            validation = {
                'Cannot be empty': lambda v: len(v) > 0,
                'Invalid input': lambda v: str(v).isalnum(),
            }
            self.user_id = ui.input('User ID', validation=validation)
            self.submit = ui.button('Submit', on_click=self.on_submit_user_id)

    def on_submit_user_id(self):
        if self.user_id.validate():
            value = str(self.user_id.value).strip()
            app.storage.user['user_id'] = value
            ui.navigate.reload()


class MainPage():

    def __init__(self):
        pass

    async def show(self):
        with ui.header().classes('items-center'):
            with ui.row().classes('w-full max-w-3xl mx-auto'):
                ui.label('Sekai Treasure').props('color=white').classes(
                    'text-xl')
                ui.space()
                (ui.button(icon='logout', on_click=self.logout)  # 
                 .props('flat round dense color=white'))

        with ui.column().classes('w-full max-w-3xl mx-auto'):
            self.current_id = app.storage.user['user_id']
            ui.label(f'Current ID: {self.current_id}')
            self.event = Storage.instance().event
            self.event.subscribe(self.on_update_event)
            # self.show_diamonds()

            # Resource Type Selection Section
            with ui.column().classes('w-full gap-3'):
                ui.label('素材類型').classes('text-lg font-semibold')
                self.radio_res_type = ui.radio(
                    {
                        'mysekai_material': 'MySekai Material',
                        'mysekai_item': 'MySekai Item',
                        'material': 'Material',
                        'mysekai_fixture': 'MySekai Fixture',
                    },
                    value='mysekai_material',
                    on_change=self.on_res_type_change).props('inline')

            # Filter and Selection Section
            with ui.column().classes('w-full gap-4'):
                ui.label('篩選與選擇').classes('text-lg font-semibold')

                with ui.row().classes('items-center gap-4'):
                    self.checkbox_filter_current = ui.checkbox(
                        '僅顯示現在可得的素材',
                        on_change=self.on_res_type_change).classes('flex-wrap')

                with ui.row().classes('items-center gap-4'):
                    ui.label('選擇素材').classes('font-medium')
                    resources = SekaiResources.instance()
                    self.select_res = ui.select(
                        resources.get_all_mysekai_material(),
                        value=12,
                        on_change=self.show_resources.refresh,
                    ).classes('flex-grow')

            await self.show_resources()

            # ui.button('Test Function',
            #           on_click=lambda _: Storage.instance().append_example(
            #               self.current_id))

    def on_res_type_change(self):
        res = SekaiResources.instance()
        obj = self.radio_res_type

        match obj.value:
            case 'mysekai_material':
                options = res.get_all_mysekai_material()
            case 'mysekai_item':
                options = res.get_all_mysekai_item()
            case 'material':
                options = res.get_all_material()
            case 'mysekai_fixture':
                options = res.get_all_mysekai_fixture()
            case _:
                options = {}

        need_filter = self.checkbox_filter_current.value
        if need_filter:
            storage = Storage.instance()
            if self.current_id in storage.last_harvest_map:
                status = storage.last_harvest_map[self.current_id]
                current_ids = status.current_ids.get(str(obj.value))
                if current_ids:
                    new_options = {
                        k: res.get_resource(str(obj.value), k)
                        for k in current_ids
                    }
                    options = new_options

        self.select_res.set_options(options)
        self.show_resources.refresh()

    def on_update_event(self, msg: str):
        user_id = msg
        if user_id == self.current_id:
            # self.show_diamonds.refresh()
            self.show_resources.refresh()

    @ui.refreshable_method
    async def show_resources(self):
        storage = Storage.instance()
        status = storage.last_harvest_map.get(self.current_id)
        if not status:
            ui.label('Waiting for network packets...')
            return
        harvest_map = status.harvest_map
        last_update = datetime.fromtimestamp(status.last_update)
        last_update = last_update.isoformat(sep=' ', timespec='seconds')
        ui.label(f'Last update: {last_update}')

        selected_res_id = self.select_res.value
        if selected_res_id is None:
            ui.label('No selected resource id')
            return
        selected_res_type = self.radio_res_type.value
        if selected_res_type is None:
            ui.label('No selected resource type')
        found_resources = SekaiTool.extract_resources(harvest_map,
                                                      str(selected_res_type),
                                                      int(selected_res_id))
        await self.show_resources0(found_resources)

    async def show_resources0(self, found_resources: list[ResourcePlace]):
        if not found_resources:
            ui.label('No Resources Found').classes('text-gray-500')
            return
        ui.label(f'Found {len(found_resources)} places').classes(
            'text-green-600')

        map_containers = []

        with ui.grid().classes('w-full grid grid-cols-1 md:grid-cols-2 gap-4'):
            for res in found_resources:
                with ui.card().classes('w-full'):
                    with ui.card_section():
                        ui.label(
                            res.resource_name).classes('text-lg font-bold')

                    with ui.card_section():
                        ui.label(f'📍 {res.place_name}')
                        ui.label(f'坐標: ({res.position_x}, {res.position_z})')
                        ui.label(f'數量: {res.quantity}')
                        if res.spawn_limit is not None:
                            ui.label(f'期間限定: {res.spawn_limit}').classes(
                                'text-sm text-blue-600')
                        if res.fixture_name:
                            ui.label(f'Fixture: {res.fixture_name}').classes(
                                'text-sm text-purple-600')
                        if res.fixture_all_items:
                            ui.label('其他物品:').classes('text-sm text-gray-500')
                            with ui.row().classes('flex-wrap gap-2'):
                                for it in res.fixture_all_items:
                                    item_name = it.resouce_name
                                    item_qty = it.quantity
                                    ui.label(
                                        f'{item_name} x {item_qty}'
                                    ).classes(
                                        'text-sm bg-gray-100 px-2 py-1 rounded'
                                    )

                    container = ui.column().classes('w-full')
                    with container:
                        ui.spinner()
                    map_containers.append((container, res.site_id,
                                           res.position_x, res.position_z))

        map_draw = await run.io_bound(SekaiMapDraw.instance)
        for container, site_id, px, pz in map_containers:
            map_img = await run.io_bound(map_draw.get_place_img, site_id, px,
                                         pz)
            container.clear()
            if map_img is not None:
                with container:
                    ui.image(map_img)

    @ui.refreshable_method
    def show_diamonds(self):
        storage = Storage.instance()
        diamond_status = storage.last_found_diamonds.get(self.current_id)
        if not diamond_status:
            ui.label('Waiting for network packets...')
            return
        last_update = datetime.fromtimestamp(diamond_status.last_update)
        last_update = last_update.isoformat(sep=' ', timespec='seconds')
        ui.label(f'Last update: {last_update}')

        diamonds = diamond_status.diamonds
        with ui.list().props('bordered separator'):
            if not diamonds:
                with ui.item():
                    with ui.item_section():
                        ui.item_label('No Diamond').props('header')
                return

            for diamond in diamonds:
                drop = diamond.drop
                item_id = drop.get('resourceId', -1)
                position_x = drop.get('positionX')
                position_z = drop.get('positionZ')
                item_name = SekaiTool.get_resource_name(item_id)
                place_name = SekaiTool.get_place_name(diamond.site_id)
                spawn_limit = drop.get(
                    'mysekaiSiteHarvestSpawnLimitedRelationGroupId')
                with ui.item():
                    with ui.item_section():
                        ui.item_label(item_name)
                        ui.item_label(f'Place: {place_name}').props('caption')
                        ui.item_label(f'positionX: {position_x}').props(
                            'caption')
                        ui.item_label(f'positionZ: {position_z}').props(
                            'caption')
                        ui.item_label(f'Spawn Limit: {spawn_limit}').props(
                            'caption')

    def logout(self):
        app.storage.user.pop('user_id')
        ui.navigate.reload()


@ui.page('/')
async def main():
    if 'user_id' not in app.storage.user:
        InitialPage()
    else:
        main_page = MainPage()
        await main_page.show()


# @ui.page('/')
# def main():
#     show_diamonds()
#     ui.button('clear', on_click=lambda: Storage.instance().clear_messages())
#     show_messages()
#     pass

app.on_startup(lambda: background_tasks.create(background_material()))
app.on_startup(lambda: background_tasks.create(background()))

if __name__ in {"__main__", "__mp_main__"}:
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    formatter = logging.Formatter('%(asctime)s %(message)s',
                                  '%Y-%m-%d %H:%M:%S')
    handler = Storage.instance().log_handle
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.addHandler(handler)
    ui.run(
        reload=False,
        storage_secret='private key to secure the browser session cookie',
    )
