from kivy.app import App
from kivy.uix.widget import Widget
from kivy.clock import Clock
from android.runnable import run_on_ui_thread
import threading
import os

# Запускаем Flask в фоне
def run_flask():
    os.environ["FLASK_ENV"] = "production"
    from app import app
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

class AIChatApp(App):
    def build(self):
        threading.Thread(target=run_flask, daemon=True).start()
        Clock.schedule_once(self.load_webview, 1.5)
        return Widget()

    @run_on_ui_thread
    def load_webview(self, dt):
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        WebView = autoclass("android.webkit.WebView")
        WebViewClient = autoclass("android.webkit.WebViewClient")
        activity = PythonActivity.mActivity
        webview = WebView(activity)
        webview.getSettings().setJavaScriptEnabled(True)
        webview.getSettings().setDomStorageEnabled(True)
        webview.getSettings().setMediaPlaybackRequiresUserGesture(False)
        webview.setWebViewClient(WebViewClient())
        webview.loadUrl("http://127.0.0.1:5000")
        activity.setContentView(webview)

if __name__ == "__main__":
    AIChatApp().run()
