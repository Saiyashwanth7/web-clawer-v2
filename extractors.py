from aiohttp import *
from bs4 import *
from urllib.parse import *

#Helping functions

def is_content_empty(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    # Remove script and style tags
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(strip=True)
    return len(text) < 200  # very little visible text = JS rendered

def _is_logo_sized(img) -> bool:
    try:
        w = int(img.get("width", 0))
        h = int(img.get("height", 0))
        if w == 0 or h == 0:
            return False
        # logos are typically wide and short, under 300px tall
        return h < 150 and w > h
    except:
        return False

def _links_to_homepage(img, page_url) -> bool:
    parent_a = img.find_parent("a")
    if not parent_a:
        return False
    href = parent_a.get("href", "")
    full = urljoin(page_url, href)
    parsed_page = urlparse(page_url)
    parsed_href = urlparse(full)
    # logo links back to root domain
    return (
        parsed_href.netloc == parsed_page.netloc and
        parsed_href.path in ("", "/")
    )
    
    
# In this file, we going to write two functions which are the core for the crawler 
# first is the extract_links, this is like we are adding all possible neighbors of a node in the 
# graph, but we check for the domain name, too

# Second function is the extract_images, this function would extract all image links in a html page.
# just extract soup.find_all('img'), add this domain name to the href and store it in a list, also 
# check if the image belongs to the logo class, we need to stor it as logo if it belongs to logo class


def extract_links(html:str,url:str):
    soup = BeautifulSoup(html,"html.parser")
    base_domain = urlparse(url).netloc
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag.get("href","").strip()
        if not href or href.startswith(('#',"mailto:","javascript","tel:")):
            continue
        complete_link = urljoin(url,href)
        if urlparse(complete_link).netloc==base_domain:
            links.append(complete_link)
    return list(set(links))


def extract_images(html:str,url:str): # returns the list of dict, dict contains image and is_logo flag
    soup = BeautifulSoup(html,"html.parser")
    #base_domain = urlparse(url).netloc
    images = []
    
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src')
        if not src:
            continue
        absolute_url = urljoin(url, src)
        alt = img.get("alt", "").lower()
        class_str = " ".join(img.get("class", [])).lower()
        id_str = img.get("id", "").lower()
        url_lower = absolute_url.lower()
        SKIP_PATTERNS = ["s.gif", "spacer", "blank", "pixel", "tracking"]
        if any(p in url_lower for p in SKIP_PATTERNS):
            continue

        # Logo detection heuristic
        logo_signals = [
            # Text signals
            "logo" in alt,
            "logo" in class_str,
            "logo" in id_str,
            "logo" in url_lower,
            "brand" in class_str,
            "brand" in alt,

            # New: more keyword signals
            "icon" in url_lower and img.find_parent(["header", "nav"]) is not None,
            "emblem" in alt,
            "wordmark" in alt or "wordmark" in url_lower,

            # Position signals
            img.find_parent(["header", "nav"]) is not None,
            img.find_parent(attrs={"id": lambda x: x and "header" in x.lower()}) is not None,

            # Size signals — logos are usually small and wide
            # (only works if width/height attributes exist in HTML)
            _is_logo_sized(img),

            # Link signal — logos almost always link to homepage
            _links_to_homepage(img, url)
            ]

        is_logo = any(logo_signals)

        images.append({
            "image_url": absolute_url,
            "alt_text": img.get("alt", ""),
            "is_logo": is_logo,
        })

    return images
