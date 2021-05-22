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
from PIL import Image, ImageDraw, ImageOps
import logging
import time

# configure logging
log_level = logging.INFO
if 'DEBUG' in os.environ.keys():
    if os.environ['DEBUG'].lower() == "true":
        log_level = logging.DEBUG

logging.basicConfig(format='%(asctime)s %(message)s', level=log_level)


### helper methods
def map_seconds(x, in_min, in_max, out_min, out_max):
    return int((x-in_min) * (out_max-out_min) / (in_max-in_min) + out_min)


def remove_transparency(im, bg_colour=(255, 255, 255)):

    # Only process if image has transparency (http://stackoverflow.com/a/1963146)
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):

        # Need to convert to RGBA if LA format due to a bug in PIL (http://stackoverflow.com/a/1963146)
        alpha = im.convert('RGBA').getchannel('A')

        # Create a new background image of our matt color.
        # Must be RGBA because paste requires both images have the same format
        # (http://stackoverflow.com/a/8720632  and  http://stackoverflow.com/a/9459208)
        bg = Image.new("RGBA", im.size, bg_colour + (255,))
        bg.paste(im, mask=alpha)
        bg.convert('RGB')
        return bg

    else:
        return im


weather_symbols = {
        "minus_minus": [],
        "minus": [200, 210, 230, 300, 310, 500, 600, 701, 711, 801],
        "neutral": [201, 211, 231, 301, 311, 313, 321, 501, 531, 601, 721, 731, 741, 800, 802],
        "plus": [202, 212, 221, 232, 302, 312, 314, 502, 520, 602, 612, 620, 751, 761, 803],
        "plus_plus": [503, 521, 611, 613, 615, 622, 762, 771, 804],
        "exclamation": [504, 511, 522, 616, 622, 781]
}


class WeatherFetcher:
    def __init__(self):
        logging.debug("Initializing WeatherFetcher")
        self.icon_path = 'icons'
        self.config = None
        self.last_icon = False
        self.max_icon_width = 34
        self.max_icon_height = 27
        self.weather_data = {'cache_ts': -1}

    def get_icon(self, icon_id):
        # check for icon
        icon_name = "%s.png" % icon_id
        icon_url = "http://openweathermap.org/img/wn/%s" % icon_name
        bn = os.path.basename(icon_name)
        for root, dirs, files in os.walk(self.icon_path):
            if bn not in files:
                logging.debug("Downloading missing icon file")
                with open(os.path.join(self.icon_path, bn), "wb") as icon_file:
                    response = requests.get(icon_url)
                    icon_file.write(response.content)
                icon_file.close()

                # convert image for oled screen
                img = Image.open(os.path.join(self.icon_path, bn))

                # crop image
                image_box = img.getbbox()
                cropped_img = img.crop(image_box)

                # normalize image size
                paste_width = int((self.max_icon_width - cropped_img.width) / 2)
                paste_height = int((self.max_icon_height - cropped_img.height) / 2)
                img = Image.new('RGBA', (self.max_icon_width, self.max_icon_height))
                img.paste(cropped_img, (paste_width, paste_height))

                # remove transparency
                img = remove_transparency(img)

                # make everything except transparency black
                thresh = 254
                fn = lambda x: 255 if x > thresh else 0
                img = img.convert('L').point(fn, mode='1')

                # invert image
                img = img.convert('L')
                img = ImageOps.invert(img)
                img = img.convert('1')

                # save image
                img.save(os.path.join(self.icon_path, bn))
        return os.path.join(self.icon_path, bn)

    def png_to_bmp(self, icon):
        img = Image.open(os.path.join(self.icon_path, str(icon)))
        basename = os.path.splitext(icon)[0]
        img = img.convert('1')
        img.save(os.path.join(self.icon_path, "%s.bmp" % basename))
        return "%s.bmp" % basename

    def fetch(self):
        now = time.time()
        cache_filename = 'weather_cache.json'

        if self.weather_data['cache_ts'] < (now - 900):
            logging.info("Fetching weather data from api.openweathermap.org")
            url = 'https://api.openweathermap.org/data/2.5/onecall'
            r = requests.get('{}?lat={}&lon={}&units={}&appid={}'.format(url, self.config['lat'], self.config['lon'],
                                                                         self.config['units'], self.config['api_key']))
            self.weather_data = r.json()
            self.weather_data['cache_ts'] = now

            with open(cache_filename, 'w') as outfile:
                json.dump(self.weather_data, outfile)
        else:
            logging.debug("Using local weather data cache")

        # fetch and prepare icon
        self.get_icon(self.weather_data['daily'][0]['weather'][0]['icon'])

        return self.weather_data


class OledScreen:
    def __init__(self):
        logging.debug("Initializing OledScreen")

        from board import SCL, SDA
        import busio
        import adafruit_ssd1306

        self.i2c = busio.I2C(SCL, SDA)

        try:
            self.disp = adafruit_ssd1306.SSD1306_I2C(128, 32, self.i2c)
        except ValueError as e:
            logging.error("Catched ValueError: %s" % e)
            logging.error("OLED Screen could not be initialized. Exiting...")
            sys.exit(1)

    def clear_display(self):
        self.disp.fill(0)
        self.disp.show()

    def show(self, image):
        self.disp.image(image)
        try:
            self.disp.show()
        except OSError as e:
            logging.error("Catched OSError: %s" % e)
            logging.error("OLED Screen probably disconnected. Exiting...")
            sys.exit(1)

class ImageRenderer:
    def __init__(self, config):
        logging.debug("Initializing ImageRenderer")
        self.config = config

        self.weather_fetcher = WeatherFetcher()
        self.weather_fetcher.config = self.config

        self.oled_screen = None

        self.width = 128
        self.height = 32
        self.weather_start = 82

        # self.font = ImageFont.load_default()
        # self.clock_font = ImageFont.truetype("fonts/RobotoMono-Regular.ttf", 26)

        self.image = Image.new("1", (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)

        self.blackout_image()

    def blackout_image(self):
        # Draw a black filled box to clear the image.
        self.draw.rectangle((0, 0, self.width - 1, self.height - 1), outline=0, fill=0)

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

    def string_to_small_digits(self, time_string, position=0, rev=False):

        # ensure its a string after rounding
        time_string = str(time_string)

        if rev:
            # calculating position "from behind"
            position = position - 1 - (len(time_string) * 5 + 2)

        img_name = None
        for char in str(time_string):
            img_name = "s%s.png" % char

            digit_image = Image.open(os.path.join("digits", img_name))
            self.image.paste(digit_image, (position, 27))

            position += digit_image.width + 1

        digit_image = Image.open(os.path.join("digits", "sdeg.png"))
        self.image.paste(digit_image, (position, 27))

        return position + 1

    def render_time(self):
        now = datetime.now()

        seconds = int(time.time() % 60)
        self.draw.line((0, 31, 78, 31), fill=0)
        self.draw.line((0, 31, map_seconds(seconds, 0, 59, 0, 78), 31), fill=255)

        if self.config['time_format'] == "12h":
            current_time = now.strftime('%I:%M')
        else:
            current_time = now.strftime('%H:%M')

        self.string_to_digits(current_time)

        # self.draw.text((0, 0), current_time, font=self.clock_font, fill=255)

    def render_weather(self):
        weather_data = self.weather_fetcher.fetch()

        # get the weather icon
        logging.debug("Using icon %s" % weather_data['daily'][0]['weather'][0]['icon'])
        icon_image_path = self.weather_fetcher.get_icon(weather_data['daily'][0]['weather'][0]['icon'])
        icon_image = Image.open(icon_image_path)

        # get the weather symbol
        symbol_name = "error"
        for current_symbol in weather_symbols.keys():
            if weather_data['daily'][0]['weather'][0]['id'] in weather_symbols[current_symbol]:
                symbol_name = current_symbol
                logging.debug("Using symbol %s" % symbol_name)

        # calculate positions
        symbol_image = False
        try:
            symbol_image = Image.open(os.path.join("digits", "%s.png" % symbol_name))
        except FileNotFoundError:
            logging.warning("Unable to find file: %s" % os.path.join("digits", "%s.png" % symbol_name))

        symbol_length = 0
        if symbol_image:
            symbol_length = symbol_image.width + 2

        weather_icon_offset = math.floor((self.width - 1 - self.weather_start - icon_image.width - symbol_length) / 2)
        weather_icon_start = self.weather_start + weather_icon_offset
        self.image.paste(icon_image, (weather_icon_start, 0))

        if symbol_image:
            self.image.paste(symbol_image, (weather_icon_start + icon_image.width + 2, 0))

        # print("daily weather description:", weather_data['daily'][0]['weather'][0]['description'])
        # print("daily weather id         :", weather_data['daily'][0]['weather'][0]['id'])
        # print("daily weather icon       :", weather_data['daily'][0]['weather'][0]['icon'])

        # print("daily wind speed         :", weather_data['daily'][0]['wind_speed'])
        # print("daily humidity           :", weather_data['daily'][0]['humidity'])
        #
        # print("daily feels_like morn    :", weather_data['daily'][0]['feels_like']['morn'])
        # print("daily feels_like day     :", weather_data['daily'][0]['feels_like']['day'])
        # print("daily feels_like day     :", weather_data['daily'][0]['feels_like']['eve'])

        now = datetime.now()
        if int(now.strftime('%H')) < 12:
            # its morning
            first = weather_data['daily'][0]['feels_like']['morn']
            second = weather_data['daily'][0]['feels_like']['day']
        elif int(now.strftime('%H')) > 20:
            # its evening
            first = weather_data['daily'][0]['feels_like']['eve']
            second = weather_data['daily'][1]['feels_like']['morn']
        else:
            # its daytime
            first = weather_data['daily'][0]['feels_like']['day']
            second = weather_data['daily'][0]['feels_like']['eve']

        position = self.string_to_small_digits(int(first), self.weather_start)
        self.string_to_small_digits(int(second), self.width, True)

    def init_screen(self):
        self.oled_screen = OledScreen()
        self.oled_screen.clear_display()

    def show(self):
        self.oled_screen.show(self.image)

    def store(self):
        self.image.save("current.png", 'PNG')

    def run(self, skip_loop = False):
        self.blackout_image()
        if not skip_loop:
            self.render_time()
            self.render_weather()


if __name__ == "__main__":
    logging.info("PiPyDailyClock starting up")
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
        loop_count = 0
        while True:
            run_start = time.time()

            skip_loop = False
            b4_run = time.time()
            if config['screensaver']:
                if loop_count % config['screensaver'] == 0:
                    skip_loop = True

            ir.run(skip_loop)
            logging.debug("run took %s seconds" % (time.time() - b4_run))

            b4_show = time.time()
            ir.show()
            logging.debug("show took %s seconds" % (time.time() - b4_show))

            loop_sleep = 1 - (time.time() - run_start)
            if loop_sleep > 0:
                time.sleep(loop_sleep)
                
            loop_count += 1
