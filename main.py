__version__ = "1.0.0"

import os
import re
import sys
import time
import zipfile
import shutil
import json
from threading import Thread

# 获取资源文件路径（支持开发环境）
def get_resource_path(relative_path):
    """获取资源文件绝对路径，支持开发环境"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar
from kivy.uix.image import Image as KivyImage
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.resources import resource_add_path
from kivy.graphics.texture import Texture
from kivy.uix.behaviors import ButtonBehavior
from kivy.core.clipboard import Clipboard

import requests
from PIL import Image
import io


# 自定义带hover效果的按钮
class HoverButton(Button):
    """带hover效果的按钮"""
    def __init__(self, **kwargs):
        self.normal_color = kwargs.pop('normal_color', (0.2, 0.6, 0.8, 1))
        self.hover_color = kwargs.pop('hover_color', (0.3, 0.7, 0.9, 1))
        super().__init__(**kwargs)
        self.background_color = self.normal_color
        
        # 绑定鼠标位置事件
        from kivy.core.window import Window
        Window.bind(mouse_pos=self.on_mouse_pos)
    
    def on_mouse_pos(self, window, pos):
        """检测鼠标位置，更新按钮颜色"""
        if self.collide_point(*pos):
            self.background_color = self.hover_color
        else:
            self.background_color = self.normal_color


# 注册中文字体
def register_chinese_font():
    """注册中文字体"""
    font_path = get_resource_path('NotoSansCJK-Regular.otf')
    
    # 如果字体文件存在，注册它
    if os.path.exists(font_path):
        resource_add_path(os.path.dirname(font_path))
        LabelBase.register(name='ChineseFont', fn_regular='NotoSansCJK-Regular.otf')
        return 'ChineseFont'
    else:
        # 使用系统默认字体
        return 'Roboto'

FONT_NAME = register_chinese_font()


# 从 translations.json 加载标签翻译字典
def load_translations():
    translations_path = get_resource_path('translations.json')
    try:
        with open(translations_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

TAG_TRANSLATIONS = load_translations()

def translate_tag(tag):
    """将英文标签转换为中文"""
    tag_lower = tag.lower().strip()
    return TAG_TRANSLATIONS.get(tag_lower, tag)

def convert_to_webp(image_data, quality=85):
    """将图片数据转换为webp格式"""
    try:
        if image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            return image_data

        img = Image.open(io.BytesIO(image_data))

        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        webp_data = io.BytesIO()
        img.save(
            webp_data,
            format='WebP',
            quality=quality,
            method=6,
            exif=b'',
            icc_profile=None,
            lossless=False,
            exact=False
        )
        return webp_data.getvalue()
    except Exception as e:
        return None


def format_size(size_bytes):
    """将字节数格式化为可读字符串"""
    if size_bytes is None:
        return "未知"
    try:
        size_bytes = int(size_bytes)
    except (TypeError, ValueError):
        return "未知"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


class MangaDownloader(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', padding=20, spacing=20, **kwargs)

        # 设置背景色
        from kivy.graphics import Color, Rectangle
        with self.canvas.before:
            Color(0.15, 0.15, 0.15, 1)  # 深灰色背景
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_bg, size=self.update_bg)

        # 左侧封面区域
        self.cover_layout = BoxLayout(orientation='vertical', size_hint_x=0.4, spacing=10)

        # 封面容器（与界面背景同色，无边框）
        from kivy.uix.floatlayout import FloatLayout
        cover_container = FloatLayout(size_hint=(1, 0.85))

        # 封面图片 - 使用 size_hint=(1,1) 填满容器，fit_mode 保持宽高比
        self.cover_image = KivyImage(
            size_hint=(1, 1),
            fit_mode='contain',
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            allow_stretch=True,
            keep_ratio=True
        )
        cover_container.add_widget(self.cover_image)
        self.cover_layout.add_widget(cover_container)
        
        # 封面占位文字
        self.cover_placeholder = Label(
            text='等待封面...',
            font_size='12sp',
            font_name=FONT_NAME,
            size_hint_y=0.15,
            color=(0.7, 0.7, 0.7, 1),
            bold=True
        )
        self.cover_layout.add_widget(self.cover_placeholder)
        
        self.add_widget(self.cover_layout)

        # 右侧主内容区域
        self.main_layout = BoxLayout(orientation='vertical', size_hint_x=0.6, spacing=15)

        # 标题
        title_label = Label(
            text='萌漫社漫画下载器',
            font_size='28sp',
            font_name=FONT_NAME,
            size_hint_y=None,
            height=60,
            color=(1, 1, 1, 1),
            bold=True
        )
        self.main_layout.add_widget(title_label)

        # URL输入框
        self.url_input = TextInput(
            hint_text='请输入漫画URL',
            font_name=FONT_NAME,
            font_size='12sp',
            size_hint_y=None,
            height=60,
            multiline=False,
            background_color=(0.25, 0.25, 0.25, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
            hint_text_color=(0.6, 0.6, 0.6, 1),
            padding=[20, 20, 20, 20]
        )
        self.main_layout.add_widget(self.url_input)

        # 按钮容器
        button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        
        # 下载按钮（使用HoverButton）
        self.download_btn = HoverButton(
            text='开始下载',
            font_name=FONT_NAME,
            font_size='14sp',
            bold=True,
            normal_color=(0.2, 0.6, 0.8, 1),
            hover_color=(0.3, 0.7, 0.9, 1),
            color=(1, 1, 1, 1)
        )
        self.download_btn.bind(on_press=self.start_download)
        button_layout.add_widget(self.download_btn)
        
        self.main_layout.add_widget(button_layout)

        # 进度条
        from kivy.uix.progressbar import ProgressBar
        self.progress = ProgressBar(
            size_hint_y=None,
            height=25,
            max=100
        )
        self.main_layout.add_widget(self.progress)

        # 日志显示区域
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.gridlayout import GridLayout

        # 日志标题栏（包含标题和复制按钮）
        log_header = BoxLayout(orientation='horizontal', size_hint_y=None, height=32, spacing=5)
        log_title = Label(
            text='[ 日志输出 ]',
            font_name=FONT_NAME,
            font_size='13sp',
            size_hint_x=0.7,
            halign='left',
            valign='middle',
            padding=(10, 0, 0, 0),
            color=(0.7, 0.8, 0.9, 1),
            bold=True
        )
        log_header.add_widget(log_title)

        # 复制按钮
        self.copy_log_btn = HoverButton(
            text='复制日志',
            font_name=FONT_NAME,
            font_size='12sp',
            size_hint_x=0.3,
            height=30,
            normal_color=(0.4, 0.5, 0.6, 1),
            hover_color=(0.5, 0.6, 0.7, 1),
            color=(1, 1, 1, 1)
        )
        self.copy_log_btn.bind(on_press=self.copy_log_to_clipboard)
        log_header.add_widget(self.copy_log_btn)

        self.main_layout.add_widget(log_header)

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=True, do_scroll_y=True, bar_width=8)
        self.log_label = TextInput(
            text='等待输入...',
            font_name=FONT_NAME,
            font_size='14sp',
            size_hint_y=None,
            readonly=True,
            background_color=(0.15, 0.15, 0.15, 1),
            foreground_color=(0.9, 0.9, 0.9, 1),
            cursor_color=(1, 1, 1, 1),
            selection_color=(0.3, 0.6, 0.9, 0.5),
            padding=(15, 15),
            border=(0, 0, 0, 0)
        )
        self.log_label.bind(minimum_height=self.log_label.setter('height'))
        scroll.add_widget(self.log_label)

        self.scroll_view = scroll  # 保存引用以便自动滚动
        self.main_layout.add_widget(scroll)

        self.add_widget(self.main_layout)

        self.download_thread = None
        self.is_downloading = False

    def update_bg(self, instance, value):
        """更新背景矩形"""
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def log(self, message):
        """添加日志信息"""
        current_text = self.log_label.text
        if current_text == '等待输入...':
            current_text = ''
        self.log_label.text = current_text + message + '\n'
        # 仅当用户在底部时才自动滚动
        if hasattr(self, 'scroll_view'):
            Clock.schedule_once(lambda dt: self._scroll_to_bottom(), 0.05)

    def _scroll_to_bottom(self):
        """仅在用户处于底部时滚动到底部，避免干扰翻阅历史"""
        try:
            if hasattr(self, 'scroll_view') and self.log_label:
                if self.scroll_view.scroll_y <= 0.01:
                    self.log_label.cursor = (0, len(self.log_label.text))
                    self.scroll_view.scroll_y = 0
        except Exception:
            pass

    def copy_log_to_clipboard(self, instance=None):
        """复制日志内容到剪贴板"""
        try:
            log_text = self.log_label.text
            if log_text == '等待输入...' or not log_text.strip():
                self.log('[提示] 日志为空，无需复制')
                return

            # 去除末尾多余的换行
            log_text = log_text.rstrip()
            Clipboard.copy(log_text)

            # 复制按钮文字短暂变化作为反馈
            original_text = self.copy_log_btn.text
            self.copy_log_btn.text = '✓ 已复制'
            Clock.schedule_once(lambda dt: setattr(self.copy_log_btn, 'text', original_text), 1.5)

            self.log(f'[提示] 日志已复制到剪贴板 ({len(log_text)} 字符)')
        except Exception as e:
            self.log(f'[错误] 复制失败: {e}')

    def update_progress(self, value):
        """更新进度条"""
        self.progress.value = value

    def start_download(self, instance):
        """开始下载"""
        if self.is_downloading:
            self.log('下载进行中，请稍候...')
            return

        url = self.url_input.text.strip()
        if not url:
            self.log('请输入有效的URL')
            return

        self.download_btn.disabled = True
        self.is_downloading = True
        self.download_thread = Thread(target=self.download_process, args=(url,))
        self.download_thread.start()

    def download_process(self, url):
        """下载处理流程"""
        try:
            Clock.schedule_once(lambda dt: self.log('正在获取漫画信息...'))

            # 获取画廊信息
            info = self.get_gallery_info(url)

            if not info or not info['gallery_id']:
                Clock.schedule_once(lambda dt: self.log('无法获取漫画信息'))
                Clock.schedule_once(lambda dt: self.reset_ui())
                return

            # 显示信息
            info_text = f"\n标题: {info['title']}\n页数: {info['total_pages']}\n漫画ID: {info['gallery_id']}\n"
            Clock.schedule_once(lambda dt, t=info_text: self.log(t))

            if info['tags']:
                translated_tags = [translate_tag(tag) for tag in info['tags']]
                tags_text = "标签:\n  - " + "\n  - ".join(translated_tags) + "\n"
                Clock.schedule_once(lambda dt, t=tags_text: self.log(t))

            # 提前加载封面，避免封面区域一直黑屏
            self.load_cover_early(info)

            # 下载图片
            self.download_images(info)

        except Exception as e:
            Clock.schedule_once(lambda dt: self.log(f'下载出错: {str(e)}'))
        finally:
            Clock.schedule_once(lambda dt: self.reset_ui())

    def reset_ui(self):
        """重置UI状态"""
        self.download_btn.disabled = False
        self.is_downloading = False

    def load_cover_early(self, info):
        """提前加载封面：先尝试本地 cover 目录，再尝试网络获取"""
        gallery_id = info['gallery_id']

        # 先尝试从本地 cover 目录加载
        cover_png_path = os.path.join('cover', 'manga_cover.png')
        if os.path.exists(cover_png_path):
            cover_bytes = self.load_local_cover(cover_png_path)
            if cover_bytes:
                Clock.schedule_once(lambda dt, b=cover_bytes: self.update_cover(b))
                return

        # 本地没有，从网络获取封面
        cover_bytes = self.fetch_cover_image(gallery_id)
        if cover_bytes:
            Clock.schedule_once(lambda dt, b=cover_bytes: self.update_cover(b))

    def fetch_cover_image(self, gallery_id):
        """获取第一张图片的原始字节数据（不在后台线程创建纹理）"""
        base_url = f"https://i3.wp.com/i3.wp.com/i3.nhentai.net/galleries/{gallery_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://nhentai.net/',
        }
        
        supported_formats = ['jpg', 'png', 'webp']
        
        for format_ext in supported_formats:
            img_url = f"{base_url}/1.{format_ext}"
            try:
                response = requests.get(img_url, headers=headers, timeout=15)
                if response.status_code == 200:
                    return response.content
                else:
                    print(f"封面下载失败: {img_url} - 状态码: {response.status_code}")
            except Exception as e:
                print(f"封面请求失败: {img_url} - {e}")
                continue
        
        print("所有封面格式尝试失败")
        return None

    def load_local_cover(self, cover_png_path):
        """从本地 PNG 封面文件读取原始字节数据（不在后台线程创建纹理）"""
        try:
            if not os.path.exists(cover_png_path):
                return None
            with open(cover_png_path, 'rb') as f:
                return f.read()
        except Exception as e:
            print(f"本地封面加载失败: {e}")
            return None

    def save_cover_png(self, image_data):
        """将图片数据保存为 PNG 封面到 cover 目录"""
        try:
            pil_image = Image.open(io.BytesIO(image_data))
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            # 保存到 cover 目录
            cover_dir = 'cover'
            if not os.path.exists(cover_dir):
                os.makedirs(cover_dir)
            cover_path = os.path.join(cover_dir, 'manga_cover.png')
            pil_image.save(cover_path, 'PNG')
            return cover_path
        except Exception as e:
            print(f"保存 PNG 封面失败: {e}")
            return None

    def update_cover(self, image_bytes):
        """在主线程中从原始字节创建纹理并更新封面"""
        if not image_bytes:
            self.cover_placeholder.text = '封面加载失败'
            print("封面更新失败: 数据为空")
            return

        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            if pil_image.mode != 'RGBA':
                pil_image = pil_image.convert('RGBA')

            texture = Texture.create(size=pil_image.size, colorfmt='rgba')
            texture.blit_buffer(pil_image.tobytes(), colorfmt='rgba', bufferfmt='ubyte')
            texture.flip_vertical()

            self.cover_image.texture = texture
            self.cover_image.canvas.ask_update()
            self.cover_placeholder.text = '封面已加载'
            print(f"封面更新成功, 图片尺寸: {texture.size}")
        except Exception as e:
            self.cover_placeholder.text = '封面加载失败'
            print(f"封面纹理创建失败: {e}")

    def get_gallery_info(self, gallery_url):
        """从画廊页面提取信息"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        try:
            response = requests.get(gallery_url, headers=headers, timeout=30)
            response.encoding = 'utf-8'

            # 提取标题
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
            title = title_match.group(1) if title_match else "unknown"
            title = re.sub(r'\s*-\s*萌漫社\s*$', '', title)

            # 提取页数
            desc_match = re.search(r'(\d+)页', response.text)
            total_pages = int(desc_match.group(1)) if desc_match else 0

            # 提取gallery ID
            img_match = re.search(r'nhentai\.net/galleries/(\d+)/', response.text)
            gallery_id = img_match.group(1) if img_match else None

            # 提取标签
            tags = []
            keywords_match = re.search(r'<meta name="keywords" content="([^"]+)"', response.text)
            if keywords_match:
                keywords = keywords_match.group(1).split(',')
                tags = [k.strip() for k in keywords if k.strip()]

            tag_pattern = r'<a[^>]*class="tag[^"]*"[^>]*>([^<]+)</a>'
            found_tags = re.findall(tag_pattern, response.text, re.IGNORECASE)
            tags.extend(found_tags)
            tags = list(set(tags))

            return {
                'title': title,
                'total_pages': total_pages,
                'gallery_id': gallery_id,
                'tags': tags
            }
        except Exception as e:
            error_msg = str(e)
            Clock.schedule_once(lambda dt, m=error_msg: self.log(f'获取页面信息失败: {m}'))
            return None

    def download_images(self, info):
        """下载漫画图片"""
        gallery_id = info['gallery_id']
        total_pages = info['total_pages']
        base_url = f"https://i3.wp.com/i3.wp.com/i3.nhentai.net/galleries/{gallery_id}"

        # 创建保存目录
        safe_title = re.sub(r'[<>:"/\\|?*]', '', info['title'])
        save_dir = safe_title
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': info.get('url', ''),
        }

        supported_formats = ['webp', 'jpg', 'png']
        preferred_format = [None]
        success_count = 0
        failed_pages = []
        total_bytes = 0  # 累计下载字节数

        Clock.schedule_once(lambda dt: self.log(f'开始下载 {total_pages} 页...'))

        for page in range(1, total_pages + 1):
            save_path = os.path.join(save_dir, f"{page:05d}.webp")

            if os.path.exists(save_path):
                success_count += 1
                file_size = os.path.getsize(save_path)
                total_bytes += file_size
                progress = (page / total_pages) * 100
                Clock.schedule_once(lambda dt, p=progress: self.update_progress(p))
                Clock.schedule_once(lambda dt, pg=page, sz=file_size: self.log(f'[跳过] 第 {pg} 页已存在 ({format_size(sz)})'))

                # 如果是第一页且封面未加载，尝试加载封面
                if page == 1 and self.cover_placeholder.text == '等待封面...':
                    cover_png_path = os.path.join('cover', 'manga_cover.png')
                    if os.path.exists(cover_png_path):
                        cover_bytes = self.load_local_cover(cover_png_path)
                        if cover_bytes:
                            Clock.schedule_once(lambda dt, b=cover_bytes: self.update_cover(b))
                    else:
                        # 本地封面不存在，尝试从网络获取
                        cover_bytes = self.fetch_cover_image(gallery_id)
                        if cover_bytes:
                            Clock.schedule_once(lambda dt, b=cover_bytes: self.update_cover(b))
                continue

            # 尝试不同格式
            downloaded = False
            for format_ext in supported_formats:
                img_url = f"{base_url}/{page}.{format_ext}"

                try:
                    response = requests.get(img_url, headers=headers, timeout=30)

                    if response.status_code == 200:
                        image_data = response.content
                        original_size = len(image_data)

                        if format_ext != 'webp':
                            webp_data = convert_to_webp(image_data)
                            if webp_data:
                                image_data = webp_data
                            else:
                                continue

                        with open(save_path, 'wb') as f:
                            f.write(image_data)

                        file_size = len(image_data)
                        total_bytes += file_size
                        success_count += 1
                        downloaded = True

                        Clock.schedule_once(lambda dt, pg=page, sz=file_size, fmt=format_ext:
                            self.log(f'[完成] 第 {pg} 页 ({fmt}, {format_size(sz)})'))

                        # 如果是第一页，保存 PNG 封面并显示
                        if page == 1:
                            cover_png_path = self.save_cover_png(image_data)
                            if cover_png_path:
                                cover_bytes = self.load_local_cover(cover_png_path)
                                if cover_bytes:
                                    Clock.schedule_once(lambda dt, b=cover_bytes: self.update_cover(b))

                        if not preferred_format[0]:
                            preferred_format[0] = format_ext

                        break
                except:
                    continue

            if not downloaded:
                failed_pages.append(page)
                Clock.schedule_once(lambda dt, pg=page: self.log(f'[失败] 第 {pg} 页下载失败'))

            # 更新进度
            progress = (page / total_pages) * 100
            Clock.schedule_once(lambda dt, p=progress: self.update_progress(p))

        # 压缩和清理
        if success_count > 0:
            Clock.schedule_once(lambda dt: self.log(
                f'下载完成！成功: {success_count}/{total_pages}, 累计大小: {format_size(total_bytes)}'
            ))
            if failed_pages:
                Clock.schedule_once(lambda dt: self.log(f'失败页面: {failed_pages}'))

            zip_name = f"{safe_title}.zip"
            Clock.schedule_once(lambda dt: self.log(f'正在压缩为 {zip_name}...'))
            self.compress_to_zip(save_dir, zip_name)

            # 显示压缩包大小
            try:
                zip_size = os.path.getsize(zip_name)
                Clock.schedule_once(lambda dt: self.log(
                    f'[OK] 压缩完成: {zip_name} ({format_size(zip_size)})  原始: {format_size(total_bytes)}  压缩率: {zip_size / total_bytes * 100:.1f}%'
                    if total_bytes > 0 else
                    f'[OK] 压缩完成: {zip_name} ({format_size(zip_size)})'
                ))
            except Exception:
                Clock.schedule_once(lambda dt: self.log(f'[OK] 压缩完成: {zip_name}'))

            self.delete_source_files(save_dir)

    def compress_to_zip(self, folder_path, zip_name):
        """压缩文件夹"""
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in sorted(os.listdir(folder_path)):
                if file.endswith('.webp'):
                    file_path = os.path.join(folder_path, file)
                    zipf.write(file_path, file)

    def delete_source_files(self, folder_path):
        """删除源文件夹和 cover 目录"""
        try:
            shutil.rmtree(folder_path)
        except Exception as e:
            Clock.schedule_once(lambda dt: self.log(f'删除文件夹失败: {e}'))

        # 删除 cover 目录
        cover_dir = 'cover'
        if os.path.exists(cover_dir):
            try:
                shutil.rmtree(cover_dir)
            except Exception as e:
                Clock.schedule_once(lambda dt: self.log(f'删除 cover 目录失败: {e}'))

class MangaDownloaderApp(App):
    # 设置程序名称
    title = '萌漫社漫画下载器 --开发者: 绯月Abyss'
    
    def build(self):
        # 设置窗口图标
        from kivy.core.window import Window
        icon_path = get_resource_path('avatar.jpg')
        if os.path.exists(icon_path):
            Window.set_icon(icon_path)
        
        # 先显示启动画面
        splash_path = get_resource_path('presplash.png')
        
        if os.path.exists(splash_path):
            # 创建启动画面布局
            self.splash_layout = BoxLayout(orientation='vertical')
            splash_img = KivyImage(
                source=splash_path,
                fit_mode='contain',
                size_hint=(1, 1)
            )
            self.splash_layout.add_widget(splash_img)
            
            # 延迟2秒后加载主界面
            Clock.schedule_once(self.load_main_ui, 2)
            return self.splash_layout
        else:
            # 如果没有splash图片，直接加载主界面
            return MangaDownloader()
    
    def load_main_ui(self, dt):
        """加载主界面"""
        self.root.clear_widgets()
        self.main_widget = MangaDownloader()
        self.root.add_widget(self.main_widget)

if __name__ == '__main__':
    MangaDownloaderApp().run()