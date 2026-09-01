# import scrapy
# import re 
# import pandas as pd
# from guitar_project.items import GuitarProjectItem

# class Guitar1Spider(scrapy.Spider):
#     name = "guitar1"
#     allowed_domains = ["amazon.in"]
#     types = ['acoustic+guitar',"electric+guitar",'classical+guitar']
#     custom_settings = {
#         'ROBOTSTXT_OBEY': False,
#         'DEFAULT_REQUEST_HEADERS': {
#             'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#             'Accept-Language': 'en-US,en;q=0.9',
#             'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
#         }
#     }
#     def start_requests(self):
#         for t in self.types:
#             url = f"https://www.amazon.in/s?k={t}"
#             yield scrapy.Request(url=url, callback=self.parse, meta={"type": t})

#     def parse(self, response):
#         guitar_type = response.meta["type"]
#         products = response.css("div[role='listitem'][data-asin]")
#         for product in products:
#             items = GuitarProjectItem()
#             guitar_id = product.css("div[data-asin]::attr(data-asin)").get()
#             name_guitar = product.css("div[data-cy='title-recipe'] a h2 span::text").get()
#             #brand_guitar = product.css(".a-size-base-plus.a-color-base.a-text-normal::text").extract()
#             offered_price_guitar = product.css("span.a-price span.a-offscreen::text").get()
#             original_price_guitar = product.css('a.a-link-normal span.a-offscreen::text').get()
#             #type_guitar = product.css(".a-size-base.a-color-secondary::text").extract()
#             rating_guitar = product.css("div[data-cy='reviews-block'] div span::text").get()
#             num_rating = product.css("div[data-cy='reviews-block'] div a[aria-label] span[aria-hidden='true']::text").get()
    

#             items["guitar_id"] = guitar_id
#             items["scraped_at"] = pd.Timestamp.now().isoformat()
#             items["name_guitar"] = name_guitar
#         #items["brand_guitar"] = brand_guitar
#             if offered_price_guitar is None:
#                 items["offered_price_guitar"] = "No Offered Price"
#             else:
#                 items["offered_price_guitar"] = offered_price_guitar
#             items["original_price_guitar"] = original_price_guitar
#         #items["type_guitar"] = type_guitar
#             if rating_guitar is None or num_rating is None:
#                 items["rating_guitar"] = "0"
#                 items["num_rating"] = "0"
#             else:
#                 items["rating_guitar"] = rating_guitar
#                 items["num_rating"] = num_rating

#             yield items
import scrapy
from datetime import datetime, timezone
from scrapy_playwright.page import PageMethod
from guitar_project.items import GuitarProjectItem


class Guitar1Spider(scrapy.Spider):
    name = "guitar1"
    allowed_domains = ["amazon.in"]
    types = ['acoustic+guitar', "electric+guitar", 'classical+guitar']

    def start_requests(self):
        for t in self.types:
            url = f"https://www.amazon.in/s?k={t}"
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={
                    "type": t,
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod(
                            "wait_for_selector",
                            "div[role='listitem'][data-asin]",
                            timeout=15000,
                        ),
                    ],
                },
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
                errback=self.errback,
            )

    def parse(self, response):
        guitar_type = response.meta["type"]
        products = response.css("div[role='listitem'][data-asin]")

        self.logger.info(f"[{guitar_type}] Found {len(products)} product blocks")

        for product in products:
            guitar_id = product.attrib.get("data-asin")
            name_guitar = product.css(
                "div[data-cy='title-recipe'] a h2 span::text"
            ).get()

            if not guitar_id or not name_guitar:
                continue

            offered_price_guitar = product.css(
                "span.a-price span.a-offscreen::text"
            ).get()
            original_price_guitar = product.css(
                "span.a-price.a-text-price span.a-offscreen::text"
            ).get()
            rating_guitar = product.css(
                "div[data-cy='reviews-block'] div span::text"
            ).get()
            num_rating = product.css(
                "div[data-cy='reviews-block'] div a[aria-label] "
                "span[aria-hidden='true']::text"
            ).get()

            items = GuitarProjectItem()
            items["guitar_id"] = guitar_id
            items["scraped_at"] = datetime.now(timezone.utc).isoformat()
            items["name_guitar"] = name_guitar.strip()
            items["offered_price_guitar"] = (
                offered_price_guitar if offered_price_guitar else "No Offered Price"
            )
            items["original_price_guitar"] = original_price_guitar
            items["rating_guitar"] = rating_guitar if rating_guitar else "0"
            items["num_rating"] = num_rating if num_rating else "0"

            yield items

    async def errback(self, failure):
        self.logger.error(f"Request failed: {failure}")