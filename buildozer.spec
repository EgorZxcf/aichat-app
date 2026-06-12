[app]
title = NeuroChat
package.name = neurochat
package.domain = org.neurochat
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,css,js,xml
version = 1.0
requirements = python3,kivy==2.2.1,flask,requests
orientation = portrait
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = True
android.network_security_config = res/xml/network_security_config.xml
fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 0
