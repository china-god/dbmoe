[app]

# 应用名称
title = 萌漫社漫画下载器

# 包名
package.name = MangaDownloader

# 包名域名（反向域名）
package.domain = org.manga

# 源代码目录
source.dir = .

# 源代码包含的文件扩展名
source.include_ext = py,png,jpg,otf,json

# 版本号
version = 1.0.0

# 依赖库
requirements = python3,kivy,pillow,requests

# 支持的架构
android.archs = arm64-v8a,armeabi-v7a

# 最低 Android SDK 版本
android.minapi = 21

# 目标 Android SDK 版本
android.api = 33

# Android NDK 版本
android.ndk = 25b

# 应用图标
icon.filename = avatar.jpg

# 启动画面（横屏）
presplash.filename = presplash.png

# 启动画面方向
presplash.orientation = portrait

# 屏幕方向：portrait（竖屏）、landscape（横屏）、all（自动）
orientation = portrait

# 全屏模式
fullscreen = 0

# 权限
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# 允许备份
android.allow_backup = True

# 应用主题
android.theme = "@android:style/Theme.NoTitleBar"

# 启用 AndroidX
android.enable_androidx = True

# 编译选项
android.gradle_dependencies = 

# 构建工具版本
android.build_tools_version = 33.0.2

# 接受 Android SDK 许可证
android.accept_sdk_license = True

# 调试模式（发布时设为 False）
android.debuggable = False

# 编译优化
android.release = True

[buildozer]

# 日志级别（0-2，2最详细）
log_level = 2

# 显示警告
show_warnings = True

# 构建目录
build_dir = ./.buildozer

# 二进制文件目录
bin_dir = ./bin