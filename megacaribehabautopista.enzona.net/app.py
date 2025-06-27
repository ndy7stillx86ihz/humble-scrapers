import argparse
import sys
import re
import os
import requests
import logging.config
import urllib3
from pathlib import Path

from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# config
NTFY_URL = "https://ntfy.sh"
TARGET_URL = "https://megacaribehabautopista.enzona.net/"

SCRIPT_DIR = Path(__file__).parent

CONFIG_PATH = SCRIPT_DIR / "config" / "logging.conf"
LOGS_DIR = SCRIPT_DIR / "logs"

LOGS_DIR.mkdir(exist_ok=True)

logging.config.fileConfig(CONFIG_PATH, disable_existing_loggers=False, defaults={
    'logfilename': str(LOGS_DIR / "scrapper.log")
})
log = logging.getLogger('appLogger')

def clean_product_title(title) -> str:
    return re.sub(r'\.{3,}$', '', re.sub(r'^\(MLC\)\s*', '',
                                         ' '.join(title.replace('\n', '').replace('\t', '').split()))).strip()

def scrap(client, uri: str):
    response = client.get(
        url=uri,
        verify=False,
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; Redmi Note 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36"
        },
        timeout=90
    )
    response.raise_for_status()

    return response

def main() -> int:
    parser = argparse.ArgumentParser(
        description="megacaribehabautopista.enzona.net crawler",
    )
    parser.add_argument("product")
    parser.add_argument("--endpoint", default="", required=False)
    parser.add_argument("--exclude", required=False, help=
                        "Palabras clave para excluir el producto que las tenga, pueden ser varias en forma de CSV. " \
                        "Ejemplo: 'entero,parranda,rojo'")
    parser.add_argument("--no-notify", action="store_true", help="No enviar notificación a ntfy.sh")

    # extract args
    args: argparse.Namespace = parser.parse_args()

    do_notify: bool = not args.no_notify
    target_endpoint: str = args.endpoint
    excluded_keywords: list[str] = args.exclude.split(',') if args.exclude else []
    product_name: str = args.product.lower()

    client = requests.Session()

    proxy_url = {
        "http": os.getenv("http_proxy"), 
        "https": os.getenv("https_proxy")
    }
    
    if all(proxy_url.values()):
        log.debug("si esta detras de un proxy")
        client.proxies = proxy_url

    # scrap
    target_product_uri: str | None = f"{TARGET_URL.rstrip('/')}/{target_endpoint.lstrip('/')}"
    errors_limit = 5
    errors = 0

    response = None

    try:
        log.info("Iniciando scrappeo a megacaribehabautopista.enzona.net")

        response = scrap(client, target_product_uri)

    except requests.RequestException as e:
        log.error(f"Algo salio mal en la request a {target_product_uri}: {e}")
        
        if errors > errors_limit:
            return 2

        response = scrap(target_product_uri)

    soup = BeautifulSoup(response.text, "html.parser")
    items_list: set[str] = set(
        f"{clean_product_title(a_tag['title'])}"
        for product in soup.select('div.product-container')
        if (h5_tag := product.find("h5", itemprop="name"))
        and (a_tag := h5_tag.find("a", class_="product-name"))
        and 'title' in a_tag.attrs
        and product_name.lower() in a_tag['title'].lower()
        and not any(
            exclusion.lower() in a_tag['title'].lower()
            for exclusion in excluded_keywords
        )
    )

    if len(items_list) > 0:
        log.info(f"Productos encontrados: " + ",".join(items_list))

        if do_notify:
            # ntfy config
            ntfy_channel_uri: str = f"{NTFY_URL}/{target_product_uri.split("https://")[-1].split("/")[0].replace('.', '_')}"
            ntfy_payload: list[str] = "\n".join([f"- {i}" for i in items_list]).encode(encoding='utf-8')
            ntfy_headers: dict[str, str] = {
                    "Title": f"Sacaron {product_name}!!",
                    "Click": target_product_uri,
                    "Priority": "4",
                    "Tags": "loudspeaker, loudspeaker"
                }
            ntfy_timeout: int = 30

            log.info(f"Notificando sobre los productos encontrados a `{ntfy_channel_uri}`")
        
            try:
                response = client.post(
                    url=ntfy_channel_uri,
                    data=ntfy_payload,
                    headers=ntfy_headers,
                    timeout=ntfy_timeout,    
                )

                response.raise_for_status()
            except requests.RequestException as e:
                log.error(f"Error al enviar la notificación: {e}")
            
        return 0

    log.info(f"No se encontro {product_name} aun :c")

    return 0


if __name__ == "__main__":
    try: 
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("KeyboardInterrupt, quitando manualmente")
