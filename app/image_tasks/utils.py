import openslide
from PIL import Image

class SmartSlide:
    """
    智能滑片读取器：
    自动适配 OpenSlide (SVS/NDPI) 和 PIL (PNG/JPG) 格式。
    """
    def __init__(self, path):
        self.path = path
        self.mode = 'unknown'
        try:
            # 1. 优先尝试作为病理切片打开 (OpenSlide)
            self._slide = openslide.OpenSlide(path)
            self.mode = 'wsi'
            # SVS 的尺寸是 (width, height)
            self.dimensions = self._slide.dimensions
        except:
            # 2. 失败则作为普通大图打开 (PIL)
            # 解除 PIL 对大图的像素限制
            Image.MAX_IMAGE_PIXELS = None 
            self._slide = Image.open(path)
            self.mode = 'pil'
            self.dimensions = self._slide.size

    def read_region(self, location, level, size):
        """
        统一读取接口：返回 RGBA 的 PIL Image
        location: (x, y) 起始坐标
        level: 金字塔层级 (PIL 模式下忽略)
        size: (w, h) 读取尺寸
        """
        if self.mode == 'wsi':
            return self._slide.read_region(location, level, size)
        else:
            # PIL 的 crop 区域: (left, top, right, bottom)
            x, y = location
            w, h = size
            # 注意：PIL 的 crop 是 lazy 的，这里强转一下防止后续资源占用
            return self._slide.crop((x, y, x+w, y+h)).convert("RGBA")
    
    def get_thumbnail(self, size):
        """
        获取缩略图 (保持比例)
        size: (max_w, max_h)
        """
        if self.mode == 'wsi':
            return self._slide.get_thumbnail(size)
        else:
            img = self._slide.copy()
            img.thumbnail(size)
            return img

    def close(self):
        if hasattr(self._slide, 'close'):
            self._slide.close()