## PiPyDailyClock

A simple script to display a clock with weather information for a Raspberry Pi and a ssd1306 based
OLED screen.

### Installation
This project is made for Python 3 and provides a `requirements.txt` file, so that virtual environments
can be used. To do so, run the following commands:
```bash
sudo apt install python3-venv
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```
From this moment forward, you should call the file with use of the venv:
`venv/bin/python3 pipydailyclock.py`

### Configuration
The configuration is stored in the `config.yaml` file. You can use the `config.yaml.example` as
a template.

#### Weather API
Weather information is fetched from [Open Weather Map](https://openweathermap.org/api). You have
to configure the following keys in `config.yaml`.

* `api_key` Get your api key from OWM website.
* `city` Look at OWM docs to figure what your city name is. Mine is "Sacramento,US"
* `units` This can either be imperial or metric

#### Fonts

You have to download the fonts manually. Please put them in the `fonts` folder.
* https://fonts.google.com/specimen/Orbitron
* https://www.dafont.com/alarm-clock.font
* https://www.1001fonts.com/digital-7-font.html
* https://fonts.google.com/specimen/Roboto+Mono?query=mono&preview.text=00:15&preview.text_type=custom
