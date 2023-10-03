from os import remove
from urllib.parse import urlencode
from tqdm import tqdm
import json
import requests


class APIClient:
    def __init__(self, token):
        self.token = token
        self.other = None

    def connect(self, other, ans=True):
        self.other = other
        if ans:
            other.connect(self, False)


class VKAPIClient(APIClient):
    base_url = 'https://api.vk.com/method'

    def __init__(self, vk_token, user_id):
        super().__init__(vk_token)
        self.user_id = user_id

    def get_common_params(self):
        return {
            'access_token': self.token,
            'v': '5.131',
            'user_id': self.user_id,
            'album_id': 'profile',
            'checkbox': '1',
            'extended': '1'
        }

    def get_photos(self):
        response = requests.get(f'{self.base_url}/photos.get?', params=self.get_common_params())
        return response.json().get('response', {}).get('items', {})

    def info_photos(self):
        photos = self.get_photos()
        info = [{'file_name': f'{photo.get("likes", {}).get("count", 0)}_{photo.get("date", 0)}.jpg',
                 'size': 'z',
                 'vk_photo_url': list(
                        filter(
                             lambda x: x.get('type', '') == 'z',
                             photo.get('sizes', [])
                        )
                    )[0].get('url', '')
                 } for photo in photos]
        return info

    def backup(self, count_photo=5):
        self.other.backup(count_photo, self.info_photos())


class YADiskAPIClient(APIClient):
    base_url = 'https://cloud-api.yandex.net'
    url_for_get_link = f'{base_url}/v1/disk/resources'

    def __init__(self, yadisk_token):
        super().__init__(yadisk_token)
        self.headers = {
            'Authorization': self.token
        }

    def get_info(self):
        params = {
            'path': f'VK_Photos/info.json'
        }
        response = requests.get(f'{self.url_for_get_link}/download',
                                headers=self.headers,
                                params=params)
        if 200 <= response.status_code <= 300:
            url_download = response.json().get('href', 'https://disk.yandex.ru')
            info = requests.get(url_download,
                                headers=self.headers,
                                params=params).json()
            requests.delete(f'{self.base_url}/v1/disk/resources',
                            headers=self.headers,
                            params=params)
        else:
            info = []
        return info

    def update_info(self, new_info):
        info = self.get_info()
        params = {
            'path': f'VK_Photos/info.json'
        }
        with open('info.json', 'w') as file:
            for photo in new_info:
                if photo not in info:
                    info.append(photo)
            json.dump(info, file, indent=1)
        response = requests.get(f'{self.url_for_get_link}/upload',
                                headers=self.headers,
                                params=params)
        url_upload = response.json().get('href', 'https://disk.yandex.ru')
        with open('info.json') as file:
            requests.put(url_upload, files={"file": file})
        remove('info.json')

    def backup(self, count_photos=5, info_photos=''):
        params = {
            'path': 'VK_Photos'
        }
        requests.put(f'{self.base_url}/v1/disk/resources',
                     headers=self.headers,
                     params=params)
        photos = info_photos[:count_photos]
        for _, photo in zip(tqdm(photos), photos):
            photo_content = requests.get(photo.get('vk_photo_url'))
            with open(photo.get('file_name', ''), 'wb') as file:
                file.write(photo_content.content)
            params = {
                'path': f'VK_Photos/{photo.get("file_name", "")}'
            }
            response = requests.get(f'{self.url_for_get_link}/upload',
                                    headers=self.headers,
                                    params=params)
            url_upload = response.json().get('href', 'https://disk.yandex.ru')
            with open(photo.get('file_name', ''), 'rb') as file:
                requests.put(url_upload, files={"file": file})
            remove(photo.get('file_name', ''))
        self.update_info(photos)


if __name__ == '__main__':
    APP_ID = '51759248'
    base_url_for_vk_token = 'http://oauth.vk.com/authorize'
    params_for_vk_token = {
        'client_id': APP_ID,
        'display': 'page',
        'scope': 'photos',
        'responce_type': 'token',
    }
    oauth_url = f'{base_url_for_vk_token}?{urlencode(params_for_vk_token)}'
    print('Получи VK токен здесь:', oauth_url)
    print('Получи ЯДиск токен здесь:', 'https://yandex.ru/dev/disk/poligon/')
    vk_client = VKAPIClient(input('VK токен: '),
                            int(input('VK ID: ')))
    yadisk_client = YADiskAPIClient(f'OAuth {input("ЯДиск токен: ")}')
    yadisk_client.backup(int(input('Колличество фотографий: ')))
