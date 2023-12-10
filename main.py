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
        if 200 <= response.status_code < 300:
            if "error" in response.json():
                print(f'VK:\n   {response.json().get("error", {}).get("error_msg", "Повторите попытку позже")}')
                return True, None
            return False, response.json().get('response', {}).get('items', {})
        else:
            print('Повторите попытку позже')
        return True, None

    def info_photos(self):
        error, photos = self.get_photos()
        info = None
        if not error:
            info = [{'file_name': f'{photo.get("likes", {}).get("count", 0)}_{photo.get("date", 0)}.jpg',
                     'size': sorted(photo.get('sizes', []), key=lambda x: x.get('width', 0))[-1].get('type', ''),
                     'vk_photo_url': sorted(photo.get('sizes', []), key=lambda x: x.get('width', 0))[-1].get('url', '')
                     } for photo in photos]
        return error, info

    def backup(self, count_photo=5):
        error, info_photos = self.info_photos()
        if not error:
            self.other.backup(count_photo, info_photos)


class YADiskAPIClient(APIClient):
    base_url = 'https://cloud-api.yandex.net'
    url_for_get_link = f'{base_url}/v1/disk/resources'  # ссылка для получения ссылки для загрузки/удаления файла

    def __init__(self, yadisk_token):
        super().__init__(yadisk_token)
        self.headers = {
            'Authorization': self.token
        }

    def get_info(self):
        params = {
            'path': f'VK_Photos/info.json'
        }
        info = None
        error = False
        response_for_download = requests.get(f'{self.url_for_get_link}/download',
                                             headers=self.headers,
                                             params=params)
        if 200 <= response_for_download.status_code < 300:
            url_download = response_for_download.json().get('href', 'https://disk.yandex.ru')
            download_response = requests.get(url_download,
                                             headers=self.headers,
                                             params=params)
            if download_response.status_code == 200:
                info = download_response.json()
            else:
                print(f'Ядиск:\n    {download_response.json().get("message", "Повторите попытку позже")}')
                error = True
        elif response_for_download.status_code == 404:
            # 404: "Файл не найден"(по причине отсутствия), это нас устраивает
            info = []
        else:
            print(f'Ядиск:\n    {response_for_download.json().get("message", "Повторите попытку позже")}')
            error = True
        return error, info

    def update_info(self, new_info):
        error, info = self.get_info()
        params = {
            'path': 'VK_Photos/info.json'
        }
        if not error:
            for photo in new_info:
                if photo not in info:
                    info.append(photo)
        with open('info.json', 'w') as file:
            json.dump(info, file, indent=1)
        responce_for_delete = requests.delete(f'{self.base_url}/v1/disk/resources',
                                              headers=self.headers,
                                              params=params)
        if 200 <= responce_for_delete.status_code <= 300 or responce_for_delete.status_code == 404:
            # 404: "Файл не найден"(по причине отсутствия), это нас устраивает
            response_for_upload = requests.get(f'{self.url_for_get_link}/upload',
                                               headers=self.headers,
                                               params=params)
            if 200 <= response_for_upload.status_code < 300:
                url_upload = response_for_upload.json().get('href', 'https://disk.yandex.ru')
                with open('info.json') as file:
                    requests.put(url_upload, files={"file": file})
                remove('info.json')
            else:
                print('Данные о фотографиях не были обновленны. Повторите попытку позже для всех фотографий')
        else:
            print('Данные о фотографиях не были обновленны. Повторите попытку позже')

    def backup(self, count_photos=5, info_photos=''):
        params = {
            'path': 'VK_Photos'
        }
        create_folder_response = requests.put(f'{self.base_url}/v1/disk/resources',
                                              headers=self.headers,
                                              params=params)
        if 200 <= create_folder_response.status_code < 300 or create_folder_response.status_code == 409:
            # 409: "Файл уже существует", это нас устраивает
            if count_photos > len(info_photos) or count_photos < 0:
                photos = info_photos[:]
            else:
                photos = info_photos[:count_photos]
            for _, n, photo in zip(tqdm(photos), range(1, len(photos)+1), photos):
                photo_content = requests.get(photo.get('vk_photo_url'))
                with open(photo.get('file_name', ''), 'wb') as file:
                    file.write(photo_content.content)
                params = {
                    'path': f'VK_Photos/{photo.get("file_name", "")}'
                }
                response = requests.get(f'{self.url_for_get_link}/upload',
                                        headers=self.headers,
                                        params=params)
                if not (200 <= response.status_code < 300 or response.status_code == 409):
                    # 409: "Файл уже существует", это нас устраивает
                    print(f'Ядиск: (фотография {n})\n    {response.json().get("message", "Повторите попытку позже")}')
                    return
                url_upload = response.json().get('href', 'https://disk.yandex.ru')
                with open(photo.get('file_name', ''), 'rb') as file:
                    requests.put(url_upload, files={"file": file})
                remove(photo.get('file_name', ''))
                if not (200 <= response.status_code < 300 or response.status_code == 409):
                    # 409: "Файл уже существует", это нас устраивает
                    print(f'Ядиск: (фотография {n})\n    {response.json().get("message", "Повторите попытку позже")}')
                    return
            self.update_info(photos)
        else:
            print(f'Ядиск:\n    {create_folder_response.json().get("message", "Повторите попытку позже")}')


if __name__ == '__main__':
    APP_ID = '51759248'
    base_url_for_vk_token = 'https://oauth.vk.com/authorize'
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
    vk_client.connect(yadisk_client)
    vk_client.backup(int(input('Колличество фотографий (-1 = все фотографии): ')))
