#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# based on:
# * https://learn.adafruit.com/adafruit-pioled-128x32-mini-oled-for-raspberry-pi/usage
# * https://github.com/oxivanisher/InfoWindow/blob/master/mod_weather/mod_owm.py

import requests
from datetime import datetime
import os
import sys
import yaml
import math
from PIL import Image, ImageDraw, ImageFont
import logging
import time

# configure logging
if os.environ['DEBUG'].lower() == "true":
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

logging.basicConfig(format='%(asctime)s %(message)s', level=log_level)


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
        # ToDo: Cache me for some time plz

        # Sunrise and Sunset.
        if self.config['time_format'] == "12h":
            sunrise = datetime.fromtimestamp(data['sys'].get('sunrise')).strftime('%I:%M %p')
            sunset  = datetime.fromtimestamp(data['sys'].get('sunset')).strftime('%I:%M %p')
        else:
            sunrise = datetime.fromtimestamp(data['sys'].get('sunrise')).strftime('%H:%M')
            sunset  = datetime.fromtimestamp(data['sys'].get('sunset')).strftime('%H:%M')


class OledScreen:
    def __init__(self):
        logging.debug("Initializing OledScreen")

        from board import SCL, SDA
        import busio
        import adafruit_ssd1306

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

        self.oled_screen = None

        self.width = 128
        self.height = 32

        self.image = None
        self.draw = None
        self.font = ImageFont.load_default()
        # self.clock_font = ImageFont.truetype("fonts/RobotoMono-Regular.ttf", 26)

    def create_image(self):
        self.image = Image.new("1", (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)

        # Draw a black filled box to clear the image.
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

    def string_to_digits(self, time_string, position=0):

        img_name = None
        for char in time_string:
            if char == ":":
                img_name = "colon.png"
            else:
                img_name = "%s.png" % char

            digit_image = Image.open(os.path.join("digits", img_name))
            self.image.paste(digit_image, (position, 0))

            position += digit_image.width + 1

        return position

    def render_time(self):
        now = datetime.now()

        if self.config['time_format'] == "12h":
            current_time = now.strftime('%I:%M:%S %p')
        else:
            current_time = now.strftime('%H:%M:%S')

        self.string_to_digits(current_time)

        # self.draw.text((0, 0), current_time, font=self.clock_font, fill=255)

    def init_screen(self):
        self.oled_screen = OledScreen()
        self.oled_screen.clear_display()
        self.create_image()

    def show(self):
        self.oled_screen.show(self.image)

    def store(self):
        self.image.save("current.png", 'PNG')

    def run(self):
        self.render_time()


if __name__ == "__main__":
    logging.debug("Loading config file")
    with open(r'config.yaml') as config_file:
        config = yaml.full_load(config_file)

    b4_ir_init = time.time()
    ir = ImageRenderer(config)
    logging.debug("ImageRenderer took %s seconds to init" % (time.time() - b4_ir_init))

    if sys.argv[0] == "store":

        b4_init = time.time()
        ir.init_screen()
        logging.debug("init_screen took %s seconds" % (time.time() - b4_init))

        b4_run = time.time()
        ir.run()
        logging.debug("run took %s seconds" % (time.time() - b4_run))

        b4_store = time.time()
        ir.store()
        logging.debug("store took %s seconds" % (time.time() - b4_store))

    else:
        b4_init = time.time()
        ir.init_screen()
        logging.debug("init_screen took %s seconds" % (time.time() - b4_init))
        while True:
            run_start = time.time()

            b4_run = time.time()
            ir.run()
            logging.debug("run took %s seconds" % (time.time() - b4_run))

            b4_show = time.time()
            ir.show()
            logging.debug("show took %s seconds" % (time.time() - b4_show))

            time.sleep(1 - (time.time() - run_start))
