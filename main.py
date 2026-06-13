from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.core.window import Window
import threading

Window.clearcolor = (0.031, 0.027, 0.086, 1)

def run_flask():
    from app import app
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)

class SplashScreen(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._progress = 0

        self.logo = Image(
            source="icon.png",
            size_hint=(None, None),
            size=(200, 200),
            pos_hint={"center_x": 0.5, "center_y": 0.62}
        )
        self.add_widget(self.logo)

        self.title = Label(
            text="NeuroChat",
            font_size="30sp",
            bold=True,
            color=(0.78, 0.71, 0.99, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.42}
        )
        self.add_widget(self.title)

        self.subtitle = Label(
            text="AI Assistant",
            font_size="14sp",
            color=(0.4, 0.38, 0.6, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.37}
        )
        self.add_widget(self.subtitle)

        self.bar_bg = Widget(size_hint=(None, None), size=(1, 1))
        with self.bar_bg.canvas:
            Color(0.12, 0.10, 0.22, 1)
            self.bar_bg_rect = RoundedRectangle(size=(1,1), pos=(0,0), radius=[4])
        self.add_widget(self.bar_bg)

        self.bar_fill = Widget(size_hint=(None, None), size=(1, 1))
        with self.bar_fill.canvas:
            Color(0.6, 0.44, 0.98, 1)
            self.bar_rect = RoundedRectangle(size=(1,1), pos=(0,0), radius=[4])
        self.add_widget(self.bar_fill)

        self.percent_label = Label(
            text="0%",
            font_size="12sp",
            color=(0.6, 0.44, 0.98, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.245}
        )
        self.add_widget(self.percent_label)

        self.loading_label = Label(
            text="Загрузка...",
            font_size="12sp",
            color=(0.4, 0.38, 0.6, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.20}
        )
        self.add_widget(self.loading_label)

        self.bind(size=self._redraw, pos=self._redraw)
        Clock.schedule_once(self._redraw, 0)

    def _redraw(self, *args):
        W = Window.width
        H = Window.height
        bar_w = W * 0.80
        bar_h = 7
        bar_x = (W - bar_w) / 2
        bar_y = H * 0.27

        self.bar_bg_rect.pos = (bar_x, bar_y)
        self.bar_bg_rect.size = (bar_w, bar_h)

        fill_w = bar_w * self._progress / 100
        self.bar_rect.pos = (bar_x, bar_y)
        self.bar_rect.size = (max(fill_w, 0), bar_h)

    def set_progress(self, value, text="Загрузка..."):
        self._progress = value
        self.loading_label.text = text
        self.percent_label.text = f"{int(value)}%"
        self._redraw()


class NeuroChat(App):
    def build(self):
        self.splash = SplashScreen()
        threading.Thread(target=run_flask, daemon=True).start()
        Clock.schedule_once(lambda dt: self.splash.set_progress(10, "Запуск сервера..."), 0.2)
        Clock.schedule_once(lambda dt: self.splash.set_progress(30, "Инициализация..."), 0.7)
        Clock.schedule_once(lambda dt: self.splash.set_progress(55, "Загрузка данных..."), 1.3)
        Clock.schedule_once(lambda dt: self.splash.set_progress(75, "Настройка UI..."), 1.9)
        Clock.schedule_once(lambda dt: self.splash.set_progress(90, "Почти готово..."), 2.4)
        Clock.schedule_once(lambda dt: self.splash.set_progress(100, "Готово! ✓"), 2.8)
        Clock.schedule_once(self.load_webview, 3.3)
        return self.splash

    def load_webview(self, dt):
        try:
            from android.runnable import run_on_ui_thread
            from jnius import autoclass

            @run_on_ui_thread
            def open_webview():
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                WebView = autoclass("android.webkit.WebView")
                WebViewClient = autoclass("android.webkit.WebViewClient")
                activity = PythonActivity.mActivity
                try:
                    context = activity.getApplicationContext()
                    appInfo = context.getApplicationInfo()
                    appInfo.flags = appInfo.flags | 0x08000000
                except:
                    pass
                wv = WebView(activity)
                settings = wv.getSettings()
                settings.setJavaScriptEnabled(True)
                settings.setDomStorageEnabled(True)
                settings.setAllowFileAccess(True)
                settings.setMixedContentMode(0)
                settings.setAllowContentAccess(True)
                wv.setWebViewClient(WebViewClient())
                wv.loadUrl("http://127.0.0.1:5000")
                activity.setContentView(wv)
            open_webview()
        except Exception as e:
            self.splash.loading_label.text = f"Ошибка: {str(e)}"
            Clock.schedule_once(self.load_webview, 2)

if __name__ == "__main__":
    NeuroChat().run()
