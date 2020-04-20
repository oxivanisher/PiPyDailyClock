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
import json
import math
from PIL import Image, ImageDraw, ImageFont
import logging
import time

# configure logging
log_level = logging.INFO
if 'DEBUG' in os.environ.keys():
    if os.environ['DEBUG'].lower() == "true":
        log_level = logging.DEBUG

logging.basicConfig(format='%(asctime)s %(message)s', level=log_level)

weather_symbols = {
        # Group 2xx: Thunderstorm
        200: "-",
        201: "",
        202: "+",
        210: "-",
        211: "",
        212: "+",
        221: "+",
        230: "-",
        231: "",
        232: "+",

        # Group 3xx: Drizzle
        300: "-",
        301: "",
        302: "+",
        310: "-",
        311: "",
        312: "+",
        313: "",
        314: "+",
        321: "",

        # Group 5xx: Rain
        500: "-",
        501: "",
        502: "+",
        503: "++",
        504: "!",
        511: "!",
        520: "+",
        521: "++",
        522: "!",
        531: "",

        # Group 6xx: Snow
        600: "-",
        601: "",
        602: "+",
        611: "++",
        612: "+",
        613: "++",
        615: "++",
        616: "!",
        620: "+",
        621: "++",
        622: "!",

        # Group 7xx: Atmosphere
        701: "-",
        711: "-",
        721: "",
        731: "",
        741: "",
        751: "+",
        761: "+",
        762: "++",
        771: "++",
        781: "!",

        # Group 800: Clear
        800: "",

        # Group 80x: Clouds
        801: "-",
        802: "",
        803: "+",
        804: "++"
}


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

    def png_to_bmp(self, icon):
        img = Image.open(os.path.join(self.icon_path, str(icon)))
        basename = os.path.splitext(icon)[0]
        img = img.convert('1')
        img.save(os.path.join(self.icon_path, "%s.bmp" % basename))
        return "%s.bmp" % basename

    def fetch(self):
        now = time.time()
        cache_filename = 'weather_cache.json'
        data = {'cache_ts': 0}

        cache_ts = 0
        if os.path.isfile(cache_filename):
            with open(cache_filename) as json_file:
                data = json.load(json_file)
            cache_ts = data['cache_ts']

        if cache_ts < (now - 900):
            logging.debug("Fetching weather data from api.openweathermap.org")
            url = 'https://api.openweathermap.org/data/2.5/onecall'
            r = requests.get('{}?lat={}&lon={}&units={}&appid={}'.format(url, self.config['lat'], self.config['lon'],
                                                                         self.config['units'], self.config['api_key']))
            data = r.json()
            data['cache_ts'] = now

            with open(cache_filename, 'w') as outfile:
                json.dump(data, outfile)
        else:
            logging.debug("Using local weather data cache")

        return data


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

        # self.font = ImageFont.load_default()
        # self.clock_font = ImageFont.truetype("fonts/RobotoMono-Regular.ttf", 26)

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

            position += digit_image.width + 2

        return position

    def render_time(self):
        now = datetime.now()

        seconds = int(time.time() % 60)
        self.draw.line((0, 31, 59, 31), fill=255)

        if self.config['time_format'] == "12h":
            current_time = now.strftime('%I:%M')
        else:
            current_time = now.strftime('%H:%M')

        self.string_to_digits(current_time, 4)

        # self.draw.text((0, 0), current_time, font=self.clock_font, fill=255)

    def render_weather(self):
        weather_data = self.weather_fetcher.fetch()

        # print(weather_data['daily'][0])

        print("daily weather description:", weather_data['daily'][0]['weather'][0]['description'])
        print("daily weather id         :", weather_data['daily'][0]['weather'][0]['id'])
        print("daily weather icon       :", weather_data['daily'][0]['weather'][0]['icon'])

        print("daily wind speed         :", weather_data['daily'][0]['wind_speed'])
        print("daily humidity           :", weather_data['daily'][0]['humidity'])

        print("daily feels_like morn    :", weather_data['daily'][0]['feels_like']['morn'])
        print("daily feels_like day     :", weather_data['daily'][0]['feels_like']['day'])

    def init_screen(self):
        self.oled_screen = OledScreen()
        self.oled_screen.clear_display()

    def show(self):
        self.oled_screen.show(self.image)

    def store(self):
        self.image.save("current.png", 'PNG')

    def run(self):
        self.render_time()
        self.render_weather()


if __name__ == "__main__":
    logging.debug("Loading config file")
    with open(r'config.yaml') as config_file:
        config = yaml.full_load(config_file)

    b4_ir_init = time.time()
    ir = ImageRenderer(config)
    logging.debug("ImageRenderer took %s seconds to init" % (time.time() - b4_ir_init))

    do = False
    if len(sys.argv) > 1:
        do = sys.argv[1]

    if do == "store":
        logging.info("Saving image to file")

        b4_init = time.time()
        logging.debug("init_screen took %s seconds" % (time.time() - b4_init))

        b4_run = time.time()
        ir.run()
        logging.debug("run took %s seconds" % (time.time() - b4_run))

        b4_store = time.time()
        ir.store()
        logging.debug("store took %s seconds" % (time.time() - b4_store))

    else:
        logging.info("Starting display loop")

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
