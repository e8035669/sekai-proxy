from typing import Any, Optional, NamedTuple
import json
from dataclasses import dataclass
import re
from requests import Session
import itertools
from PIL import Image, ImageDraw, ImageColor

from sssekai.crypto.APIManager import decrypt, SEKAI_APIMANAGER_KEYSETS
import msgpack

RESOURCE_NAMES = {
    '1': '想いの木材(心願的木材)',
    '2': 'おもたい木材(堅硬的木材)',
    '3': 'かるい木材(輕的木材)',
    '4': 'ベタベタの樹液(黏黏的樹液)',
    '5': '夕桐',
    '6': '想いの石ころ(心願的石塊)',
    '7': '銅',
    '8': '鉄',
    '9': '粘土',
    '10': 'きれいなガラス(玻璃)',
    '11': 'きらきクォーツ(石英)',
    '12': 'ダイヤモンド(鑽石)',
    '13': 'ねじ(螺絲)',
    '14': '釘',
    '15': 'プラスチック(塑膠)',
    '16': 'モーター(馬達)',
    '17': '電池',
    '18': 'ライト(燈泡)',
    '19': '電子基板',
    '20': '四葉のクローバー(四葉草)',
    '21': 'さらさらリネン(亞麻)',
    '22': 'ふわふわコットン(棉花)',
    '23': '花びら',
    '24': 'まっさらな音色',
    '32': 'あおぞらシーグラス',
    '33': '月光石',
    '34': '流れ星のかけら',
    '35': 'スカイブルーメモリア',
    '36': 'パッシンイエローメモリア',
    '37': 'ポピーレッドメモリア',
    '38': 'イエローグリーンメモリア',
    '39': 'アプリコットメモリア',
    '40': 'ストリクトブルーメモリア',
    '41': 'ラブリーピンクメモリア',
    '42': 'オパールグリーンメモリア',
    '43': 'スリーズメモリア',
    '44': 'ターコイズブルーメモリア',
    '45': 'ジョリーコーラルメモリア',
    '46': 'ロイヤルブルーメモリア',
    '47': 'サンフラワーメモリア',
    '48': 'ポカポカピンクメモリア',
    '49': 'スプリンググリーンメモリア',
    '50': 'カンパヌラパープルメモリア',
    '51': 'ファリダメモリア',
    '52': 'ウィスタリアメモリア',
    '53': 'キャメルメモリア',
    '54': 'ッスルメモリア',
    '55': 'ブルーグリーンメモリア',
    '56': 'オレンジメモリア',
    '57': 'イエローメモリア',
    '58': 'ピンクメモリア',
    '59': 'レッドメモリア',
    '60': 'ブルーメモリア',
    '61': '雪の結',
    '62': '最高のオノの刃',
    '63': '最高のツルハシの先端',
    '64': '雷光石',
    '65': '彩虹のビードロ',
    '66': 'ふわもこわたぐも',
}

PLACE_NAME = {
    "1": "マイホーム",
    "2": "1F",
    "3": "2F",
    "4": "3F",
    "5": "さいしょの原っぱ",
    "6": "願いの砂浜",
    "7": "彩りの花畑",
    "8": "忘れ去られた場所",
}

PLACE_MAP_NAME = {
    '5': 'grasslands',
    '6': 'beach',
    '7': 'flowergarden',
    '8': 'memorialplace',
}

FIXTURE_NAME = {
    '1001': '闊葉樹',
    '1002': '針葉樹',
    '1003': '熱帶樹',
    '1004': '夕桐',
    '2001': '岩石',
    '2002': '銅礦',
    '2003': '鐵礦',
    '2004': '玻璃礦',
    '2005': '石英礦',
    '3001': '工具箱',
    '4001': '植物',
    '4002': '發光的植物(幸運草)',
    '4003': '花1',
    '4004': '花2',
    '4005': '花3',
    '4006': '花4',
    '4007': '花5',
    '4008': '花6',
    '4012': '花7',
    '4013': '花8',
    '4014': '花9',
    '4015': '花10',
    '4016': '花11',
    '4017': '花12',
    '5003': '發光的草堆1(沙岸)',
    '5004': '發光的草堆2',
    '6001': '木桶2',
    '7001': '藍色光圈(音符)',
}


@dataclass
class DiamondPlace:
    site_id: int
    drop: dict


@dataclass
class NetworkPackage:
    url: str
    data: bytes


@dataclass
class OtherItems:
    resouce_name: str
    quantity: int


class ResourceIndex(NamedTuple):
    site_id: int
    res_type: str
    res_id: int
    pos_x: int
    pos_z: int
    spawn_limit: Optional[int]


@dataclass
class ResourcePlace:
    resource_name: str
    place_name: str
    position_x: int
    position_z: int
    quantity: int
    spawn_limit: Optional[int]
    fixture_name: str
    fixture_all_items: list[OtherItems]
    raw_data: list[DiamondPlace]


class SekaiMapDraw:

    def __init__(self) -> None:
        self.maps: dict[str, Image.Image] = {}
        for k, v in PLACE_MAP_NAME.items():
            with Image.open(f'asset/{v}.png') as im:
                im.load()
            self.maps[k] = im
        self.unit_pix = 80

    def draw_pos(
        self,
        place_name: str,
        position_x: int,
        position_z: int,
    ) -> Optional[tuple[int, int]]:
        if place_name not in self.maps:
            return None
        img = self.maps[place_name]
        center_x, center_z = img.width // 2, img.height // 2
        center_x += position_x * self.unit_pix
        center_z -= position_z * self.unit_pix
        return center_x, center_z

    def get_place_img(self, place_name: str, position_x: int, position_z: int):
        if place_name not in self.maps:
            return None
        map_copy = self.maps[place_name].copy()
        pos = self.draw_pos(place_name, position_x, position_z)
        if not pos:
            return None

        draw = ImageDraw.Draw(map_copy)
        ink = ImageColor.colormap['red']
        draw.circle(pos, 10, fill=ink)
        croped = map_copy.crop(
            (pos[0] - 250, pos[1] - 250, pos[0] + 250, pos[1] + 250))
        return croped


class SekaiResources:
    INSTANCE = None

    REPO_JP = 'sekai-master-db-diff'
    REPO_TC = 'sekai-master-db-tc-diff'

    URL = 'https://raw.githubusercontent.com/Sekai-World/{repo}/refs/heads/main/{file}'

    def __init__(self) -> None:
        self.mysekai_materials: dict[int, str] = {}
        self.mysekai_materials_tc: dict[int, str] = {}
        self.mysekai_items: dict[int, str] = {}
        self.mysekai_items_tc: dict[int, str] = {}
        self.materials: dict[int, str] = {}
        self.materials_tc: dict[int, str] = {}
        self.mysekai_fixtures: dict[int, str] = {}
        self.mysekai_fixtures_tc: dict[int, str] = {}

        self.mysekai_materials_combine: dict[int, str] = {}
        self.mysekai_items_combine: dict[int, str] = {}
        self.materials_combine: dict[int, str] = {}
        self.mysekai_fixtures_combine: dict[int, str] = {}

    @classmethod
    def instance(cls):
        if cls.INSTANCE is None:
            cls.INSTANCE = SekaiResources()
        return cls.INSTANCE

    def update(self):
        sess = Session()

        file_repos = [
            ('mysekaiMaterials.json', self.REPO_JP),
            ('mysekaiMaterials.json', self.REPO_TC),
            ('mysekaiItems.json', self.REPO_JP),
            ('mysekaiItems.json', self.REPO_TC),
            ('materials.json', self.REPO_JP),
            ('materials.json', self.REPO_TC),
            ('mysekaiFixtures.json', self.REPO_JP),
            ('mysekaiFixtures.json', self.REPO_TC),
        ]

        mappings = [
            self.mysekai_materials,
            self.mysekai_materials_tc,
            self.mysekai_items,
            self.mysekai_items_tc,
            self.materials,
            self.materials_tc,
            self.mysekai_fixtures,
            self.mysekai_fixtures_tc,
        ]

        for (f, r), d in zip(file_repos, mappings):
            url = self.URL.format(repo=r, file=f)
            ret = sess.get(url)
            if ret.ok:
                data = ret.content
                json_data = json.loads(data)
                extracted = {int(o['id']): str(o['name']) for o in json_data}
                d.clear()
                d.update(extracted)

        combines = [
            (
                self.mysekai_materials_combine,
                self.mysekai_materials,
                self.mysekai_materials_tc,
            ),
            (
                self.mysekai_items_combine,
                self.mysekai_items,
                self.mysekai_items_tc,
            ),
            (self.materials_combine, self.materials, self.materials_tc),
            (
                self.mysekai_fixtures_combine,
                self.mysekai_fixtures,
                self.mysekai_fixtures_tc,
            ),
        ]

        for combine, jp, tc in combines:
            combine.clear()
            for i in jp:
                if i in tc:
                    combine[i] = f'{jp[i]}({tc[i]})'
                else:
                    combine[i] = jp[i]

    def get_resource(self, resource_type: str, rid: int):
        match resource_type:
            case 'mysekai_material':
                return self.get_mysekai_material(rid)
            case 'mysekai_item':
                return self.get_mysekai_item(rid)
            case 'material':
                return self.get_material(rid)
            case 'mysekai_fixture':
                return self.get_mysekai_fixtures(rid)
            case _:
                raise RuntimeError(f'Invalid type {resource_type}')

    def get_mysekai_material(self, rid: int):
        if rid in self.mysekai_materials_combine:
            ret = self.mysekai_materials_combine[rid]
        else:
            ret = f'MysekaiMaterial {rid}'
        return ret

    def get_all_mysekai_material(self):
        return self.mysekai_materials_combine

    def get_mysekai_item(self, rid: int):
        if rid in self.mysekai_items_combine:
            ret = self.mysekai_items_combine[rid]
        else:
            ret = f'MysekaiItem {rid}'
        return ret

    def get_all_mysekai_item(self):
        return self.mysekai_items_combine

    def get_material(self, rid: int):
        if rid in self.materials_combine:
            ret = self.materials_combine[rid]
        else:
            ret = f'Material {rid}'
        return ret

    def get_all_material(self):
        return self.materials_combine

    def get_mysekai_fixtures(self, rid: int):
        if rid in self.mysekai_fixtures_combine:
            ret = self.mysekai_fixtures_combine[rid]
        else:
            ret = f'MysekaiFixture {rid}'
        return ret

    def get_all_mysekai_fixture(self):
        return self.mysekai_fixtures_combine


class SekaiTool:

    @staticmethod
    def all_resource_names():
        return RESOURCE_NAMES

    @staticmethod
    def get_resource_name(rid: int):
        return RESOURCE_NAMES.get(str(rid), f'Resource {rid}')

    @staticmethod
    def get_place_name(pid: int):
        return PLACE_NAME.get(str(pid), f'Place {pid}')

    @staticmethod
    def get_fixture_name(fix_id: int):
        return FIXTURE_NAME.get(str(fix_id), f'Fixture {fix_id}')

    @staticmethod
    def decrypt_data(data: bytes):
        plain = decrypt(data, SEKAI_APIMANAGER_KEYSETS['jp'])
        msg = msgpack.unpackb(plain)
        return msg

    @staticmethod
    def find_diamond(decrypted_data: dict,
                     resource_id: int = 12) -> Optional[list[DiamondPlace]]:
        root = decrypted_data
        if 'updatedResources' in root:
            root = root['updatedResources']

        if 'userMysekaiHarvestMaps' in root:
            harvest_maps = root['userMysekaiHarvestMaps']
            ret = []
            for harvest_map in harvest_maps:
                site_id = harvest_map['mysekaiSiteId']
                resource_drops = harvest_map[
                    'userMysekaiSiteHarvestResourceDrops']
                find_drop = [
                    drop for drop in resource_drops
                    if drop['resourceId'] == resource_id
                ]
                for drop in find_drop:
                    ret.append(DiamondPlace(site_id, drop))
            return ret
        return None

    @staticmethod
    def get_remain_harvest_count(decrypted_data: dict):
        root = decrypted_data
        if 'updatedResources' in root:
            root = root['updatedResources']

        if 'userMysekaiHarvestMaps' in root:
            harvest_maps = root['userMysekaiHarvestMaps']
            ret = []
            for harvest_map in harvest_maps:
                site_id = harvest_map['mysekaiSiteId']
                resource_drops = harvest_map[
                    'userMysekaiSiteHarvestResourceDrops']
                info = {'site_id': site_id, 'drop_count': len(resource_drops)}
                ret.append(info)
            return ret
        return None

    @staticmethod
    def extract_user_id(url: str) -> Optional[str]:
        PATTERN = r'https://.*\.colorfulpalette\.org/api/user/(\d+)/mysekai.*'
        match = re.match(PATTERN, url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def extract_harvest_map(decrypted_data: dict):
        root = decrypted_data
        if 'updatedResources' in root:
            root = root['updatedResources']

        if 'userMysekaiHarvestMaps' in root:
            harvest_maps = root['userMysekaiHarvestMaps']
            return harvest_maps
        return None

    @classmethod
    def find_fixture(
        cls,
        fixtures: list[dict[str, Any]],
        pos_x: int,
        pos_z: int,
    ):
        found_fixture = [
            f for f in fixtures
            if f['positionX'] == pos_x and f['positionZ'] == pos_z
        ]
        return found_fixture

    @classmethod
    def summary_other_item(
        cls,
        drops: list[dict[str, Any]],
        pos_x: int,
        pos_z: int,
    ):
        sekai_material = SekaiResources.instance()
        found_drops = [
            d for d in drops
            if d['positionX'] == pos_x and d['positionZ'] == pos_z
        ]
        items: dict[tuple[str, int], OtherItems] = {}
        for drop in found_drops:
            res_type: str = drop['resourceType']
            res_id: int = drop['resourceId']
            index = (res_type, res_id)
            quantity: int = drop['quantity']
            if index not in items:
                res_name = sekai_material.get_resource(res_type, res_id)
                items[index] = OtherItems(res_name, quantity)
            else:
                items[index].quantity += quantity
        return list(items.values())

    @classmethod
    def extract_resources(
        cls,
        harvest_maps: dict,
        resource_type: str,
        resource_id: int,
    ):
        sekai_material = SekaiResources.instance()
        ret: dict[ResourceIndex, ResourcePlace] = {}
        for harvest_map in harvest_maps:
            site_id: int = harvest_map['mysekaiSiteId']
            place_name = cls.get_place_name(site_id)
            drops: list[dict[str, Any]] = (
                harvest_map['userMysekaiSiteHarvestResourceDrops'])
            fixtures: list[dict[str, Any]] = (
                harvest_map['userMysekaiSiteHarvestFixtures'])
            find_drop = [
                drop for drop in drops
                if (drop['resourceId'] == resource_id
                    and drop['resourceType'] == resource_type)
            ]

            for drop in find_drop:
                res_type = drop['resourceType']
                res_id = drop['resourceId']
                res_name = sekai_material.get_resource(res_type, res_id)
                pos_x = drop['positionX']
                pos_z = drop['positionZ']
                quantity = drop['quantity']
                limit = drop.get(
                    'mysekaiSiteHarvestSpawnLimitedRelationGroupId')

                index = ResourceIndex(site_id, res_type, res_id, pos_x, pos_z,
                                      limit)

                if index not in ret:
                    found_fixture = cls.find_fixture(fixtures, pos_x, pos_z)
                    fixture_name = 'Not found'
                    if len(found_fixture) > 0:
                        fixture = found_fixture[0]
                        fixture_id = fixture['mysekaiSiteHarvestFixtureId']
                        fixture_name = cls.get_fixture_name(fixture_id)
                    other_items = cls.summary_other_item(drops, pos_x, pos_z)
                    raw_data = [DiamondPlace(site_id, drop)]

                    res = ResourcePlace(res_name, place_name, pos_x, pos_z,
                                        quantity, limit, fixture_name,
                                        other_items, raw_data)
                    ret[index] = res
                else:
                    res = ret[index]
                    res.quantity += quantity
                    res.raw_data.append(DiamondPlace(site_id, drop))
        return list(ret.values())

    @classmethod
    def current_exist_ids(cls, harvest_maps: dict):
        ret = {
            'mysekai_material': set(),
            'mysekai_item': set(),
            'material': set(),
            'mysekai_fixture': set(),
        }

        for harvest_map in harvest_maps:
            drops: list[dict[str, Any]] = (
                harvest_map['userMysekaiSiteHarvestResourceDrops'])
            for drop in drops:
                res_type = drop['resourceType']
                if res_type not in ret:
                    continue
                res_id = drop['resourceId']
                ret[res_type].add(int(res_id))
        return ret


def test():
    with open('temp6.bin', 'rb') as f:
        data = f.read()
    decrypted_data = SekaiTool.decrypt_data(data)
    ret = SekaiTool.find_diamond(decrypted_data, 11)
    if ret:
        print('Find diamond')
        for d in ret:
            print(d)
    else:
        print('Diamond not found')


if __name__ == "__main__":
    test()
