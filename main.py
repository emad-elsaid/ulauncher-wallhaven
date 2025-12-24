import urllib.request
import urllib.parse
import urllib.error
import json
import subprocess
import hashlib
import os

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction


def get_screen_resolution():
    """Detect primary monitor resolution using hyprctl."""
    try:
        result = subprocess.run(
            ['hyprctl', 'monitors', '-j'],
            capture_output=True,
            text=True,
            check=True
        )
        monitors = json.loads(result.stdout)
        if monitors:
            width = monitors[0]['width']
            height = monitors[0]['height']
            return f"{width}x{height}"
    except:
        return "1920x1080"


def search_wallhaven(query, min_resolution="1920x1080", limit=10):
    """
    Search Wallhaven API (anonymous).

    Returns: List of wallpaper dicts with id, path, thumbs, resolution, colors
    """
    base_url = "https://wallhaven.cc/api/v1/search"
    params = {
        'q': query,
        'sorting': 'relevance',
        'order': 'desc',
        'page': 1
    }

    if min_resolution != "none":
        params['atleast'] = min_resolution

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read())
        return data['data'][:limit]


def download_thumbnail(thumb_url, cache_dir):
    """
    Download and cache thumbnail.

    Cache filename: MD5 hash of URL
    """
    os.makedirs(cache_dir, exist_ok=True)

    cache_key = hashlib.md5(thumb_url.encode()).hexdigest()
    cache_path = os.path.join(cache_dir, f"{cache_key}.jpg")

    if os.path.exists(cache_path):
        return cache_path

    urllib.request.urlretrieve(thumb_url, cache_path)
    return cache_path


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        query = event.get_argument() or ""

        if len(query) < 2:
            return RenderResultListAction([
                ExtensionResultItem(
                    icon='images/icon.png',
                    name='Type to search Wallhaven...',
                    description='Enter keywords or tags (e.g., "nature sunset")',
                    on_enter=HideWindowAction()
                )
            ])

        min_res = extension.preferences['min_resolution']
        if min_res == 'auto':
            min_res = get_screen_resolution()

        limit = int(extension.preferences['results_limit'])

        try:
            wallpapers = search_wallhaven(query, min_res, limit)
            cache_dir = os.path.expanduser('~/.cache/ulauncher_wallhaven')

            if not wallpapers:
                return RenderResultListAction([
                    ExtensionResultItem(
                        icon='images/icon.png',
                        name='No wallpapers found',
                        description=f'No results for "{query}"',
                        on_enter=HideWindowAction()
                    )
                ])

            items = []
            for wp in wallpapers:
                thumb_path = download_thumbnail(wp['thumbs']['original'], cache_dir)

                colors = ', '.join([f"#{c}" for c in wp['colors'][:3]])
                items.append(ExtensionResultItem(
                    icon=thumb_path,
                    name=f"{wp['resolution']} - {wp['id']}",
                    description=f"Colors: {colors}",
                    on_enter=ExtensionCustomAction({
                        'action': 'set_wallpaper',
                        'url': wp['path'],
                        'id': wp['id']
                    })
                ))

            return RenderResultListAction(items)

        except urllib.error.URLError as e:
            return RenderResultListAction([
                ExtensionResultItem(
                    icon='images/icon.png',
                    name='Network error',
                    description=f'Failed to connect to Wallhaven: {str(e)}',
                    on_enter=HideWindowAction()
                )
            ])
        except Exception as e:
            return RenderResultListAction([
                ExtensionResultItem(
                    icon='images/icon.png',
                    name='Error searching Wallhaven',
                    description=str(e),
                    on_enter=HideWindowAction()
                )
            ])


class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        data = event.get_data()

        if data['action'] == 'set_wallpaper':
            wallpaper_url = data['url']
            id = data['id']

            try:
                dest = os.path.expanduser(f'~/Pictures/{id}.jpg')
                urllib.request.urlretrieve(wallpaper_url, dest)

                subprocess.run(['change-wallpaper', dest], check=True)

            except Exception:
                pass

        return HideWindowAction()


class WallhavenExtension(Extension):
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())


if __name__ == '__main__':
    WallhavenExtension().run()
