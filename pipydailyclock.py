#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# based on:
# * https://learn.adafruit.com/adafruit-pioled-128x32-mini-oled-for-raspberry-pi/usage
# * https://github.com/oxivanisher/InfoWindow/blob/master/mod_weather/mod_owm.py

import requests
from datetime import datetime as dt
import os
import yaml
import math
from PIL import Image, ImageDraw, ImageFont
import logging
import time
from board import SCL, SDA
import busio
import adafruit_ssd1306

# configure logging
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)


class WeatherFetcher:
    def __init__(self):
        logging.debug("Initializing WeatherFetcher")
        self.icon_path = 'icons'
        self.config = None

    def get_icon(self, icon_url):
        # check for icon
        bn = os.path.basename(icon_url)
        for root, dirs, files in os.walk(self.icon_path):
            if bn not in files:
                with open(os.path.join(self.icon_path, bn), "wb") as icon_file:
                    response = requests.get(icon_url)
                    icon_file.write(response.content)
                icon_file.close()

    def degrees_to_text_desc(self, deg):
        if deg > 337.5: return u"N"
        if deg > 292.5: return u"NW"
        if deg > 247.5: return u"W"
        if deg > 202.5: return u"SW"
        if deg > 157.5: return u"S"
        if deg > 122.5: return u"SE"
        if deg >  67.5: return u"E"
        if deg >  22.5: return u"NE"
        return u"N"

    def png_to_bmp(self, icon):
        img = Image.open(os.path.join(self.icon_path, str(icon)))
        basename = os.path.splitext(icon)[0]
        img = img.convert('1')
        img.save(os.path.join(self.icon_path, "%s.bmp" % basename))
        return "%s.bmp" % basename

    def fetch(self):
        url = 'http://api.openweathermap.org/data/2.5/weather'
        r = requests.get('{}?q={}&units={}&appid={}'.format(url, self.config['city'], self.config['units'],
                                                            self.config['api_key']))

        data = r.json()

        # Sunrise and Sunset.
        if self.config['time_format'] == "12h":
            sunrise = dt.fromtimestamp(data['sys'].get('sunrise')).strftime('%I:%M %p')
            sunset  = dt.fromtimestamp(data['sys'].get('sunset')).strftime('%I:%M %p')
        else:
            sunrise = dt.fromtimestamp(data['sys'].get('sunrise')).strftime('%H:%M')
            sunset  = dt.fromtimestamp(data['sys'].get('sunset')).strftime('%H:%M')


class TimeFetcher:
    def __init__(self):
        logging.debug("Initializing TimeFetcher")
        self.config = None


class OledScreen:
    def __init__(self):
        logging.debug("Initializing OledScreen")
        self.i2c = busio.I2C(SCL, SDA)
        self.disp = adafruit_ssd1306.SSD1306_I2C(128, 32, self.i2c)

    def clear_display(self):
        self.disp.fill(0)
        self.disp.show()

    def show(self, image):
        self.disp.image(image)
        self.disp.show()


class ImageRenderer:
    def __init__(self, config):
        logging.debug("Initializing ImageRenderer")
        self.config = config

        self.weather_fetcher = WeatherFetcher()
        self.weather_fetcher.config = self.config

        self.time_fetcher = TimeFetcher()
        self.time_fetcher.config = self.config

        self.oled_screen = OledScreen()
        self.oled_screen.clear_display()

        self.image = None
        self.draw = None
        self.font = ImageFont.load_default()

    def create_image(self):
        self.image = Image.new("1", (self.oled_screen.disp.width, self.oled_screen.disp.height))
        self.draw = ImageDraw.Draw(self.image)

        # Draw a black filled box to clear the image.
        self.draw.rectangle((0, 0, self.oled_screen.disp.width, self.oled_screen.disp.height), outline=0, fill=0)

    def render_time(self):
        self.draw.text((x, y), "Text: %s" % "something", font=self.font, fill=255)

    def show(self):
        self.oled_screen.show(self.image)

    def run(self):
        self.create_image()
        self.show()


if __name__ == "__main__":
    logging.debug("Loading config file")
    with open(r'config.yaml') as config_file:
        config = yaml.full_load(config_file)

    ir = ImageRenderer(config)
    ir.run()
