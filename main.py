from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
import threading
import os

def run_flask():
    from app import app
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)

class NeuroChat(App):
    def build(self):
        self.layout = BoxLayout()
        self.label = Label(text="NeuroChat\nЗагрузка...", font_size=24, halign="center")
        self.layout.add_widget(self.label)
        threading.Thread(target=run_flask, daemon=True).start()
        Clock.schedule_once(self.load_webview, 3)
        return self.layout

    def load_webview(self, dt):
        try:
            from android.runnable import run_on_ui_thread
            from jnius import autoclass

            @run_on_ui_thread
            def open_webview():
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                WebView = autoclass("android.webkit.WebView")
                WebViewClient = autoclass("android.webkit.WebViewClient")
                WebSettings = autoclass("android.webkit.WebSettings")

                activity = PythonActivity.mActivity
                wv = WebView(activity)
                settings = wv.getSettings()
                settings.setJavaScriptEnabled(True)
                settings.setDomStorageEnabled(True)
                settings.setAllowFileAccess(True)
                settings.setMixedContentMode(0)
                wv.setWebViewClient(WebViewClient())
                wv.loadUrl("http://127.0.0.1:5000")
                activity.setContentView(wv)

            open_webview()
        except Exception as e:
            self.label.text = f"Ошибка: {str(e)}"
            Clock.schedule_once(self.load_webview, 2)

if __name__ == "__main__":
    NeuroChat().run()
