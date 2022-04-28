# Asus touchpad numpad driver

**Tested only on laptop Asus ZenBook UP5401EA** with type of numpad layout **m433ia** and **backglight without levels** (only enable/disable) and system Elementary OS 6.1 Loki.

| Without % = symbols             |  With % = symbols       |  With % = symbols (but incompatible with the non-universal version) |
|:-------------------------:|:-------------------------:|:-------------------------:|
| Model/Layout = ux433fa          | Model/Layout = m433ia   | Model/Layout = ux581l |
| ![without % = symbols](https://github.com/ldrahnik/asus-touchpad-numpad-driver/blob/master/images/Asus-ZenBook-UX433FA.jpg)  |  ![with % = symbols](https://github.com/ldrahnik/asus-touchpad-numpad-driver/blob/master/images/Asus-ZenBook-UP5401EA.png) | ![model ux581](https://github.com/ldrahnik/asus-touchpad-numpad-driver/blob/master/images/Asus-ZenBook-UX581l.jpg) |


## TODO:

- [x] (Enable/disable backglight of numpad with activation)
- [x] (Two-finger tap support)
- [ ] (Support for all levels of backlight depends on type, enable/disable works only atm)

<br/>

Install required packages

- Debian / Ubuntu / Linux Mint / Pop!_OS / Zorin OS:
```
sudo apt install libevdev2 python3-libevdev i2c-tools git
```

- Arch Linux / Manjaro:
```
sudo pacman -S libevdev python-libevdev i2c-tools git
```

- Fedora:
```
sudo dnf install libevdev python-libevdev i2c-tools git
```


Then enable i2c
```
sudo modprobe i2c-dev
sudo i2cdetect -l
```

Now you can get the latest ASUS Touchpad Numpad Driver for Linux from Git and install it using the following commands.
```
git clone https://github.com/ldrahnik/asus-touchpad-numpad-driver
cd asus-touchpad-numpad-driver
sudo ./install.sh
```

To turn on/off numpad, tap top right corner touchpad area.
To adjust numpad brightness, tap top left corner touchpad area.

To uninstall, just run:
```
sudo ./uninstall.sh
```

**Troubleshooting**

To activate logger, do in a console:
```
LOG=DEBUG sudo -E ./asus_touchpad.py
```

For some operating systems with boot failure (Pop!OS, Mint, ElementaryOS, SolusOS), before installing, please uncomment in the asus_touchpad.service file, this following property and adjust its value:
```
# ExecStartPre=/bin/sleep 2
```

## Credits

Thank you very much [github.com/mohamed-badaoui](github.com/mohamed-badaoui) and all the contributors of [asus-touchpad-numpad-driver](https://github.com/mohamed-badaoui/asus-touchpad-numpad-driver) for your work.

Thank you who-t for great post about multitouch [Understanding evdev](http://who-t.blogspot.com/2016/09/understanding-evdev.html).
