import argparse
import sys
import re
import requests
import logging.config
import urllib3

from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# config
NTFY_URL = "https://ntfy.sh/"
TARGET_URL = "https://megacaribehabautopista.enzona.net/"

logging.config.fileConfig('config/logging.conf', disable_existing_loggers=False)
log = logging.getLogger('appLogger')


def clean_product_title(title) -> str:
    return re.sub(r'\.{3,}$', '', re.sub(r'^\(MLC\)\s*', '',
                                         ' '.join(title.replace('\n', '').replace('\t', '').split()))).strip()


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

    args: argparse.Namespace = parser.parse_args()

    notify: bool = not args.no_notify
    target_endpoint: str = args.endpoint
    excluded_keywords: list[str] = args.exclude.split(',') if args.exclude else []
    product_name: str = args.product.lower()

    target_url: str | None = TARGET_URL

    try:
        log.info("Iniciando scrappeo a megacaribehabautopista.enzona.net")

        response = requests.get(
            f"{target_url.rstrip('/')}/{args.endpoint.lstrip('/')}",
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            timeout=10
        )
        response.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Algo salio mal en la request a {TARGET_URL}: {e}")
        return 2

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

        if notify:
            log.info(f"Notificando sobre los productos encontrados a `{NTFY_URL}`")
        
        try:
            requests.post(
                f"https://ntfy.sh/{target_url.split("https://")[-1].replace('/', '').replace('.', '_')}",
                data="\n".join([f"- {i}" for i in items_list]).encode(encoding='utf-8'),
                headers={
                    "Title": f"Sacaron {product_name}!!",
                    "Click": target_url + target_endpoint,
                    "Priority": "4",
                    "Tags": "loudspeaker, loudspeaker",
                    "Icon": "https://megacaribehabautopista.enzona.net/img/favicon-50.ico?1709832901"
                },
                timeout=30
            )
        except requests.RequestException as e:
            log.error(f"Error al enviar la notificación: {e}")
            
        return 0

    log.info(f"No se encontro {product_name} aun :c")

    return 0


if __name__ == "__main__":
    sys.exit(main())
