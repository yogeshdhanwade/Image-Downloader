"""Download images from a link.

The link can be a direct image URL or a web page; for a page, every image it
references (<img>, srcset, og:image) is downloaded.

Standard library only.

Run:  python image_downloader.py URL [URL ...] [-o OUTPUT_DIR]
"""
import argparse
import os
import re
import sys
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

BLOCKED_HOSTS = ("sellercentral.amazon.com",)
USER_AGENT = "Mozilla/5.0 (compatible; image-downloader/1.0)"
MAX_BYTES = 25 * 1024 * 1024
TIMEOUT = 20
CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "image/svg+xml": ".svg", "image/bmp": ".bmp",
    "image/avif": ".avif",
}


class _ImageFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "img":
            for key in ("src", "data-src", "data-original"):
                if a.get(key):
                    self.urls.append(a[key])
            for part in (a.get("srcset") or "").split(","):
                if part.strip():
                    self.urls.append(part.strip().split()[0])
        elif tag == "meta" and a.get("property") in ("og:image", "twitter:image"):
            if a.get("content"):
                self.urls.append(a["content"])


def check_allowed(url):
    host = (urlparse(url).hostname or "").lower()
    if host in BLOCKED_HOSTS:
        raise ValueError(f"Downloading from {host} is not allowed.")
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError(f"Only http(s) links are supported: {url}")


def _open(url):
    check_allowed(url)
    return urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=TIMEOUT)


def find_image_urls(page_url, html):
    """Absolute, de-duplicated image URLs referenced by an HTML page."""
    finder = _ImageFinder()
    finder.feed(html)
    out = []
    for u in finder.urls:
        if u.startswith("data:"):
            continue
        full = urljoin(page_url, u)
        if full not in out:
            out.append(full)
    return out


def _unique_path(folder, name):
    base, ext = os.path.splitext(name)
    path, n = os.path.join(folder, name), 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{base}_{n}{ext}")
        n += 1
    return path


def _filename(url, content_type):
    name = unquote(os.path.basename(urlparse(url).path)) or "image"
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    ext = CONTENT_TYPE_EXT.get(content_type)
    if ext and not os.path.splitext(name)[1]:
        name += ext
    return name


def download_image(url, folder):
    """Download one image. Returns the saved path, or None if it isn't an image."""
    with _open(url) as resp:
        ctype = resp.headers.get_content_type()
        if not ctype.startswith("image/"):
            return None
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError(f"Image larger than {MAX_BYTES // (1024 * 1024)} MB: {url}")
    path = _unique_path(folder, _filename(url, ctype))
    with open(path, "wb") as f:
        f.write(data)
    return path


def download_from_link(url, folder):
    """Download the image at `url`, or every image on the page. Returns saved paths."""
    os.makedirs(folder, exist_ok=True)
    with _open(url) as resp:
        ctype = resp.headers.get_content_type()
        if ctype.startswith("image/"):
            direct = True
            html = ""
        else:
            direct = False
            charset = resp.headers.get_content_charset() or "utf-8"
            html = resp.read(MAX_BYTES).decode(charset, errors="replace")
    if direct:
        path = download_image(url, folder)
        return [path] if path else []

    saved = []
    for img_url in find_image_urls(url, html):
        try:
            path = download_image(img_url, folder)
        except (URLError, ValueError, OSError) as e:
            print(f"  skipped {img_url}: {e}", file=sys.stderr)
            continue
        if path:
            saved.append(path)
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("urls", nargs="+", help="image or page URL(s)")
    ap.add_argument("-o", "--output", default="downloaded_images", help="output folder")
    args = ap.parse_args()

    total = 0
    for url in args.urls:
        print(f"{url}")
        try:
            saved = download_from_link(url, args.output)
        except (URLError, ValueError, OSError) as e:
            print(f"  failed: {e}", file=sys.stderr)
            continue
        for p in saved:
            print(f"  saved {p}")
        total += len(saved)
    print(f"Done: {total} image(s) in {os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
