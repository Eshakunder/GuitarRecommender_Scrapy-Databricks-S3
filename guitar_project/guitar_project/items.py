# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class GuitarProjectItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    guitar_id = scrapy.Field()
    scraped_at = scrapy.Field()
    name_guitar = scrapy.Field()
    brand_guitar = scrapy.Field()

    original_price_guitar = scrapy.Field()
    offered_price_guitar = scrapy.Field()
    type_guitar = scrapy.Field()
    color_guitar = scrapy.Field()
    rating_guitar = scrapy.Field()
    num_rating = scrapy.Field()

    #additional later
