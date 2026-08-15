import json
import logging
import re
from decimal import Decimal

from bs4 import BeautifulSoup

from utils.safe_http import fetch_url_text, is_safe_request_url

logger = logging.getLogger(__name__)


class EliteVehicleParser:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    MAX_HTML_BYTES = 6 * 1024 * 1024

    @staticmethod
    def is_safe_url(url):
        """Backward-compatible name for outbound URL validation."""
        return is_safe_request_url(url)

    @staticmethod
    def parse_from_url(url):
        """
        Elite Parser Ingestion:
        - Detect site type.
        - Extract metadata (JSON-LD etc.)
        - Map to Django model fields.
        """
        if not is_safe_request_url(url):
            logger.error(f"Unsafe URL rejected: {url}")
            return None

        try:
            html = fetch_url_text(
                url,
                max_bytes=EliteVehicleParser.MAX_HTML_BYTES,
                timeout=15,
                headers=EliteVehicleParser.HEADERS,
            )
            soup = BeautifulSoup(html, "lxml")

            data = {
                "brand_name": "",
                "model_name": "",
                "year": None,
                "price_rub": 0,
                "price_cny": None,
                "mileage": 0,
                "description": f"Импортировано из: {url}",
                "main_image_url": None,
                "specs": {},
            }

            # 1. Look for JSON-LD (Standard for modern car portals)
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    ld = json.loads(script.string)
                    items = ld if isinstance(ld, list) else [ld]
                    for item in items:
                        # Handle potential nesting (e.g. '@graph')
                        if "@graph" in item:
                            items.extend(item["@graph"])
                            continue

                        if item.get("@type") in [
                            "Product",
                            "Car",
                            "Vehicle",
                            "IndividualProduct",
                        ]:
                            # Brand & Model
                            brand_data = item.get("brand")
                            if isinstance(brand_data, dict):
                                data["brand_name"] = brand_data.get("name") or ""
                            elif isinstance(brand_data, str):
                                data["brand_name"] = brand_data

                            data["model_name"] = (
                                item.get("name", "")
                                .replace(data["brand_name"], "")
                                .strip()
                            )

                            # Price
                            offers = item.get("offers")
                            if offers:
                                if isinstance(offers, list):
                                    price = offers[0].get("price")
                                else:
                                    price = offers.get("price")
                                if price:
                                    data["price_rub"] = Decimal(str(price))

                            # Mileage
                            mileage_node = item.get("mileageFromOdometer")
                            if mileage_node:
                                if isinstance(mileage_node, dict):
                                    data["mileage"] = int(
                                        float(mileage_node.get("value", 0))
                                    )
                                else:
                                    data["mileage"] = int(float(mileage_node))

                            # Image
                            image = item.get("image")
                            if image:
                                if isinstance(image, list):
                                    data["main_image_url"] = image[0]
                                elif isinstance(image, dict):
                                    data["main_image_url"] = image.get("url")
                                else:
                                    data["main_image_url"] = image

                            # Description
                            desc = item.get("description")
                            if desc:
                                data["description"] = desc

                            # Specs
                            for field in [
                                "vehicleTransmission",
                                "fuelType",
                                "vehicleEngine",
                                "color",
                                "bodyType",
                            ]:
                                if item.get(field):
                                    data["specs"][field] = item.get(field)
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue

            # 2. Fallbacks (OG tags)
            if not data["brand_name"]:
                og_title = soup.find("meta", property="og:title")
                if og_title:
                    title = og_title["content"]
                    parts = title.split(" ")
                    if len(parts) >= 2:
                        data["brand_name"] = parts[0]
                        data["model_name"] = " ".join(parts[1:])

            if not data["main_image_url"]:
                og_image = soup.find("meta", property="og:image")
                if og_image:
                    data["main_image_url"] = og_image["content"]

            # 3. Year extraction from title if missing
            if not data["year"]:
                # Search in title/heading tags first (more reliable than full page)
                title_tag = soup.find("title")
                h1_tag = soup.find("h1")
                search_text = ""
                if title_tag:
                    search_text += title_tag.get_text()
                if h1_tag:
                    search_text += " " + h1_tag.get_text()
                if not search_text:
                    search_text = soup.get_text()[:2000]  # Fallback: first 2000 chars
                year_match = re.search(r"\b(19[89]\d|20[012]\d)\b", search_text)
                if year_match:
                    data["year"] = int(year_match.group())

            return data

        except Exception as e:
            logger.error(f"Elite Parser failed: {e}")
            return None
