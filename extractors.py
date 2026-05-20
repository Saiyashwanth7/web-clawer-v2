from aiohttp import *
from bs4 import *
from urllib.parse import *
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

        # Logo detection heuristic
        logo_signals = [
            "logo" in alt,
            "logo" in class_str,
            "logo" in id_str,
            "logo" in url_lower,
            img.find_parent(["header", "nav"]) is not None,
            "brand" in class_str,
            "brand" in alt,
        ]
        is_logo = any(logo_signals)

        images.append({
            "image_url": absolute_url,
            "alt_text": img.get("alt", ""),
            "is_logo": is_logo,
        })

    return images

#Helping functions

def is_content_empty(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    # Remove script and style tags
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(strip=True)
    return len(text) < 200  # very little visible text = JS rendered