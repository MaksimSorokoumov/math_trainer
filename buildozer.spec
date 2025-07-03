[app]
title = Изучение таблицы умножения
package.name = multiplicationlearning
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,wav
version = 2.3
requirements = python3,kivy,pyjnius==1.6.1
icon.filename = %(source.dir)s/icon.png
orientation = portrait
fullscreen = 0

# Добавим описание приложения
author = Автор
email = author@example.com

# В секцию [app]
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1

[android]
arch = arm64-v8a
api = 31
minapi = 21
ndk = 23c
sdk = 31
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO
android.entrypoint = main.py
android.private_storage = True
android.logcat_filters = *:S python:D

# В секцию [android] 
android.gradle_dependencies = 
android.add_jars = 
android.add_src = 
android.add_aars = 