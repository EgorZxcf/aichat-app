from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.animation import Animation
import threading
import os

Window.clearcolor = (0.031, 0.027, 0.086, 1)  # #080816

def run_flask():
    from app import app
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)

class SplashScreen(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.progress = 0

        # Logo image
        self.logo = Image(
            source="icon.png",
            size_hint=(None, None),
            size=(220, 220),
            pos_hint={"center_x": 0.5, "center_y": 0.58}
        )
        self.add_widget(self.logo)

        # App name
        self.title = Label(
            text="NeuroChat",
            font_size="28sp",
            bold=True,
            color=(0.78, 0.71, 0.99, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.38}
        )
        self.add_widget(self.title)

        # Subtitle
        self.subtitle = Label(
            text="AI Assistant",
            font_size="14sp",
            color=(0.4, 0.38, 0.6, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.33}
        )
        self.add_widget(self.subtitle)

        # Progress bar background
        self.bar_bg = Widget(
            size_hint=(None, None),
            size=(260, 4),
            pos_hint={"center_x": 0.5, "center_y": 0.22}
        )
        with self.bar_bg.canvas:
            Color(0.15, 0.13, 0.25, 1)
            self.bar_bg_rect = RoundedRectangle(
                pos=self.bar_bg.pos,
                size=self.bar_bg.size,
                radius=[2]
            )
        self.bar_bg.bind(pos=self._update_bg, size=self._update_bg)
        self.add_widget(self.bar_bg)

        # Progress bar fill
        self.bar_fill = Widget(
            size_hint=(None, None),
            size=(0, 4),
            pos_hint={"center_x": 0.5, "center_y": 0.22}
        )
        with self.bar_fill.canvas:
            Color(0.6, 0.44, 0.98, 1)
            self.bar_rect = RoundedRectangle(
                pos=self.bar_fill.pos,
                size=(0, 4),
                radius=[2]
            )
        self.bar_fill.bind(pos=self._update_fill)
        self.add_widget(self.bar_fill)

        # Loading text
        self.loading_label = Label(
            text="Загрузка...",
            font_size="12sp",
            color=(0.4, 0.38, 0.6, 1),
            pos_hint={"center_x": 0.5, "center_y": 0.17}
        )
        self.add_widget(self.loading_label)

    def _update_bg(self, instance, value):
        self.bar_bg_rect.pos = instance.pos
        self.bar_bg_rect.size = instance.size

    def _update_fill(self, instance, value):
        self.bar_rect.pos = instance.pos

    def set_progress(self, value, text="Загрузка..."):
        self.progress = value
        self.loading_label.text = text
        # Обновляем ширину бара
        max_width = 260
        new_width = max_width * value / 100
        # Позиция бара (центр минус половина полной ширины)
        center_x = Window.width / 2
        bar_x = center_x - max_width / 2
        bar_y = Window.height * 0.22 - 2
        self.bar_fill.pos = (bar_x, bar_y)
        self.bar_rect.pos = (bar_x, bar_y)
        self.bar_rect.size = (new_width, 4)


class NeuroChat(App):
    def build(self):
        self.splash = SplashScreen()
        # Запускаем Flask в фоне
        threading.Thread(target=run_flask, daemon=True).start()
        # Анимируем прогресс
        Clock.schedule_once(lambda dt: self.splash.set_progress(15, "Запуск сервера..."), 0.3)
        Clock.schedule_once(lambda dt: self.splash.set_progress(35, "Инициализация..."), 0.8)
        Clock.schedule_once(lambda dt: self.splash.set_progress(60, "Загрузка данных..."), 1.5)
        Clock.schedule_once(lambda dt: self.splash.set_progress(85, "Почти готово..."), 2.2)
        Clock.schedule_once(lambda dt: self.splash.set_progress(100, "Готово! ✓"), 2.8)
        Clock.schedule_once(self.load_webview, 3.2)
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
