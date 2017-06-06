#!/usr/bin/python3

from kivy.app import App
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.network.urlrequest import UrlRequest
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty, NumericProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
import datetime
import os


WEATHER_API_URL = "http://api.openweathermap.org/data/2.5/"


class AddLocationForm(ModalView):
    current_weather = ObjectProperty()
    search_input = ObjectProperty()

    def __init__(self, **kwargs):
        super(AddLocationForm, self).__init__(**kwargs)
        self.store = JsonStore("weather_store.json", indent=4, sort_keys=True)
        if self.store.exists("locations"):
            locations = self.store.get('locations')
            if 'location_history' in locations:
                prev_loc = locations['location_history']
                self.locations_found.data = [{'city': prev_loc[location][0],
                                              'country': prev_loc[location][1],
                                              'location_id': prev_loc[location][2]} for location in prev_loc]

    def search_location(self):
        config = WeatherApp.get_running_app().config
        api_key = config.get("App", "weather_api_key")
        search_template = WEATHER_API_URL + "find?q={}&type=like&APPID=" + api_key
        search_url = search_template.format(self.search_input.text)
        request = UrlRequest(search_url, self.found_location)

    def found_location(self, request, data):
        cities = [(d['name'], d['sys']['country']) for d in data['list']]
        if len(cities):
            # Kivy 1.10 RecycleView
            self.locations_found.data = [{'city': d['name'], 'country': d['sys']['country'],
                                          'location_id': d['id']} for d in data['list']]
        else:
            print("No match found")


class CurrentWeather(BoxLayout):
    conditions = StringProperty()
    conditions_image = StringProperty()
    location = ListProperty(['New York', 'US'])
    temp = NumericProperty()
    temp_max = NumericProperty()
    temp_min = NumericProperty()

    def update_weather(self):
        config = WeatherApp.get_running_app().config
        api_key = config.get("App", "weather_api_key")
        temp_type = config.get("Weather", "temp_type").lower()
        weather_template = WEATHER_API_URL + "weather?q={},{}&units={}&APPID=" + api_key
        weather_url = weather_template.format(self.location[0], self.location[1], temp_type)
        request = UrlRequest(weather_url, self.weather_retrieved)

    def weather_retrieved(self, request, data):
        self.conditions = data['weather'][0]['description']
        self.conditions_image = "http://openweathermap.org/img/w/{}.png".format(data['weather'][0]['icon'])
        self.temp = data['main']['temp']
        self.temp_max = data['main']['temp_max']
        self.temp_min = data['main']['temp_min']


class Forecast(BoxLayout):
    forecast_container = ObjectProperty()
    location = ListProperty(['New York', 'US'])

    def update_weather(self):
        config = WeatherApp.get_running_app().config
        api_key = config.get("App", "weather_api_key")
        temp_type = config.get("Weather", "temp_type").lower()
        weather_template = WEATHER_API_URL + "forecast/daily?q={},{}&cnt=3&units={}&APPID=" + api_key
        weather_url = weather_template.format(self.location[0], self.location[1], temp_type)
        request = UrlRequest(weather_url, self.weather_retrieved)

    def weather_retrieved(self, request, data):
        self.forecast_container.clear_widgets()
        for day in data['list']:
            label = Factory.ForecastLabel()
            label.date = datetime.datetime.fromtimestamp(day['dt']).strftime(" %a %b %d")
            label.conditions = day['weather'][0]['description']
            label.conditions_image = "http://openweathermap.org/img/w/{}.png".format(day['weather'][0]['icon'])
            label.temp_max = day['temp']['max']
            label.temp_min = day['temp']['min']
            self.forecast_container.add_widget(label)


class WeatherApp(App):
    def build_config(self, config):
        config.setdefaults('App', {"save_search_history": 1,
                                   "search_history_file_path": os.path.join(os.getcwd(),
                                   "weather_store.json"),
                                   "weather_api_key": "0"})
        config.setdefaults('Weather', {"temp_type": "Metric"})

    def build_settings(self, settings):
        settings.add_json_panel("App Settings", self.config,
                                data="""[{"type": "string",
                                          "title": "Open Weather Map API Key",
                                          "section": "App",
                                          "key": "weather_api_key"
                                         },
                                         {"type": "bool",
                                          "title": "Save Search History",
                                          "section": "App",
                                          "key": "save_search_history"
                                         },
                                         {"type": "path",
                                          "title": "Search History File Path",
                                          "section": "App",
                                          "key": "search_history_file_path"
                                          }]""")
        settings.add_json_panel("Weather Settings", self.config,
                                data="""[{"type": "options",
                                          "title": "Temperature System",
                                          "section": "Weather",
                                          "key": "temp_type",
                                          "options": ["Metric", "Imperial"]
                                         }]""")

    def on_config_change(self, config, section, key, value):
        if config is self.config and key == "temp_type":
            try:
                self.root.current_weather.update_weather()
            except AttributeError:
                pass


class WeatherRoot(BoxLayout):
    add_location_form = ObjectProperty()
    carousel = ObjectProperty
    current_weather = ObjectProperty()
    forecast = ObjectProperty
    locations = ObjectProperty

    def __init__(self, **kwargs):
        super(WeatherRoot, self).__init__(**kwargs)

        config = WeatherApp.get_running_app().config
        if len(config.get("App", "weather_api_key")) <= 0:
            print("No API key provided")
            exit()
        self.store = JsonStore("weather_store.json", indent=4, sort_keys=True)
        if self.store.exists("locations"):
            locations = self.store.get('locations')
            if 'current_location' in locations:
                current_location = tuple(locations['current_location'])  # List in JSON
                self.show_current_weather(current_location)
            else:
                Clock.schedule_once(lambda dt: self.show_add_location_form())
        else:
            Clock.schedule_once(lambda dt: self.show_add_location_form())

    def show_add_location_form(self):
        self.add_location_form = AddLocationForm()
        self.add_location_form.open()

    def show_current_weather(self, location=None):
        config = WeatherApp.get_running_app().config
        if config.get("App", "save_search_history"):
            if not self.store.exists('locations'):
                self.store.put('locations')
            locations = self.store.get('locations')
            if 'location_history' not in locations:
                locations['location_history'] = {}
            location_history = locations['location_history']
            if str(location[2]) not in location_history:  # JSON keys are string
                location_history[str(location[2])] = location
            self.store.put('locations', location_history=location_history,
                           current_location=location)

        self.current_weather.location = location
        self.current_weather.update_weather()

        self.forecast.location = location
        self.forecast.update_weather()

        self.carousel.load_slide(self.current_weather)
        if self.add_location_form is not None:
            self.add_location_form.dismiss()


if __name__ == '__main__':
    WeatherApp().run()
