#!/bin/bash

# Checking if the script is runned as root (via sudo or other)
if [[ $(id -u) != 0 ]]; then
    echo "Please run the installation script as root (using sudo for example)"
    exit 1
fi

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

if [[ $(sudo apt install 2>/dev/null) ]]; then
    echo 'apt is here' && sudo apt -y install libevdev2 python3-libevdev i2c-tools git python3-pip xinput python3-numpy python3-evdev
elif [[ $(sudo pacman -h 2>/dev/null) ]]; then
    echo 'pacman is here' && sudo pacman --noconfirm --needed -S libevdev python-libevdev i2c-tools git xorg-xinput python-numpy python-evdev
elif [[ $(sudo dnf install 2>/dev/null) ]]; then
    echo 'dnf is here' && sudo dnf -y install libevdev python-libevdev i2c-tools git xinput python-evdev python3-numpy
fi

modprobe i2c-dev

# Checking if the i2c-dev module is successfuly loaded
if [[ $? != 0 ]]; then
    echo "i2c-dev module cannot be loaded correctly. Make sure you have installed i2c-tools package"
    exit 1
fi

interfaces=$(for i in $(i2cdetect -l | grep DesignWare | sed -r "s/^(i2c\-[0-9]+).*/\1/"); do echo $i; done)
if [ -z "$interfaces" ]; then
    echo "No i2c interface can be found. Make sure you have installed libevdev packages"
    exit 1
fi

touchpad_detected=false
for i in $interfaces; do
    echo -n "Testing interface $i : "
    number=$(echo -n $i | cut -d'-' -f2)
    offTouchpadCmd="i2ctransfer -f -y $number w13@0x15 0x05 0x00 0x3d 0x03 0x06 0x00 0x07 0x00 0x0d 0x14 0x03 0x00 0xad"
    i2c_test=$($offTouchpadCmd 2>&1)
    if [ -z "$i2c_test" ]; then
        echo "sucess"
        touchpad_detected=true
        break
    else
        echo "failed"
    fi
done

if [ "$touchpad_detected" = false ]; then
    echo 'The detection was not successful. Touchpad not found.'
    exit 1
fi

if [[ -d numpad_layouts/__pycache__ ]]; then
    rm -rf numpad_layouts/__pycache__
fi

laptop=$(dmidecode -s system-product-name | rev | cut -d ' ' -f1 | rev | cut -d "_" -f1)
laptop_full=$(dmidecode -s system-product-name)

echo "Detected laptop: $laptop_full"

detected_laptop_via_offline_table=$(cat laptop_numpad_layouts | grep $laptop | head -1 | cut -d'=' -f1)
detected_layout_via_offline_table=$(cat laptop_numpad_layouts | grep $laptop | head -1 | cut -d'=' -f2)

if [[ -z "$detected_layout_via_offline_table" || "$detected_layout_via_offline_table" == "none" ]]; then
    echo "Could not automatically detect numpad layout for your laptop. Please create an issue (https://github.com/asus-linux-drivers/asus-touchpad-numpad-driver/issues)."
else
    for option in $(ls numpad_layouts); do
        if [ "$option" = "$detected_layout_via_offline_table.py" ]; then   
            read -r -p "Automatically recommended numpad layout: $detected_layout_via_offline_table (associated to $detected_laptop_via_offline_table). You can specify numpad layout later by yourself and please create an issue (https://github.com/asus-linux-drivers/asus-touchpad-numpad-driver/issues). Is recommended numpad layout correct? [y/N]" response
            case "$response" in [yY][eE][sS]|[yY])
                model=$detected_layout_via_offline_table
                ;;
            *)
                ;;
            esac
        fi
    done
fi

if [ -z "$model" ]; then
    echo
    echo "Select your model keypad layout:"
    PS3='Please enter your choice '
    options=($(ls numpad_layouts) "Quit")
    select selected_opt in "${options[@]}"; do
        if [ "$selected_opt" = "Quit" ]; then
            exit 0
        fi

        for option in $(ls numpad_layouts); do
            if [ "$option" = "$selected_opt" ]; then
                model=${selected_opt::-3}
                break
            fi
        done

        if [ -z "$model" ]; then
            echo "invalid option $REPLY"
        else
            break
        fi
    done
fi

echo "Selected key layout $model"

echo "Installing asus touchpad service to /etc/systemd/system/"

# this works because sudo sets the environment variable SUDO_USER to the original username
session_id=$(loginctl | grep $SUDO_USER | awk '{print $1}')
wayland_or_x11=$(loginctl show-session $session_id -p Type --value)

if [ "$wayland_or_x11" = "x11" ]; then
    echo "X11 is detected"

    xauthority=$(/usr/bin/xauth info | grep Authority | awk '{print $3}')
    cat asus_touchpad.X11.service | LAYOUT=$model CONFIG_FILE_DIR="/usr/share/asus_touchpad_numpad-driver/" XAUTHORITY=$xauthority envsubst '$LAYOUT $XAUTHORITY $CONFIG_FILE_DIR' > /etc/systemd/system/asus_touchpad_numpad.service
    cp asus_touchpad_suspend.service /etc/systemd/system/asus_touchpad_numpad_suspend.service

elif [ "$wayland_or_x11" = "wayland" ]; then
    echo "Wayland is detected, unfortunatelly you will not be able use feature: `Disabling Touchpad (e.g. Fn+special key) disables NumberPad aswell`, at this moment is supported only X11"

    cat asus_touchpad.default.service | LAYOUT=$model CONFIG_FILE_DIR="/usr/share/asus_touchpad_numpad-driver/" envsubst '$LAYOUT $CONFIG_FILE_DIR' > /etc/systemd/system/asus_touchpad_numpad.service
    cp asus_touchpad_suspend.service /etc/systemd/system/asus_touchpad_numpad_suspend.service
else
    echo "Wayland or X11 is not detected"

    cat asus_touchpad.default.service | LAYOUT=$model CONFIG_FILE_DIR="/usr/share/asus_touchpad_numpad-driver/" envsubst '$LAYOUT $CONFIG_FILE_DIR' > /etc/systemd/system/asus_touchpad_numpad.service
    cp asus_touchpad_suspend.service /etc/systemd/system/asus_touchpad_numpad_suspend.service
fi


mkdir -p /usr/share/asus_touchpad_numpad-driver/numpad_layouts
mkdir -p /var/log/asus_touchpad_numpad-driver
install asus_touchpad.py /usr/share/asus_touchpad_numpad-driver/
install -t /usr/share/asus_touchpad_numpad-driver/numpad_layouts numpad_layouts/*.py

echo "Installing udev rules to /usr/lib/udev/rules.d/"

cp udev/90-numberpad-external-keyboard.rules /usr/lib/udev/rules.d/

echo "Added 90-numberpad-external-keyboard.rules"
mkdir -p /usr/share/asus_touchpad_numpad-driver/udev
cat udev/external_keyboard_is_connected.sh | CONFIG_FILE_DIR="/usr/share/asus_touchpad_numpad-driver/" envsubst '$LAYOUT $CONFIG_FILE_DIR' > /usr/share/asus_touchpad_numpad-driver/udev/external_keyboard_is_connected.sh
cat udev/external_keyboard_is_disconnected.sh | CONFIG_FILE_DIR="/usr/share/asus_touchpad_numpad-driver/" envsubst '$LAYOUT $CONFIG_FILE_DIR' > /usr/share/asus_touchpad_numpad-driver/udev/external_keyboard_is_disconnected.sh
chmod +x /usr/share/asus_touchpad_numpad-driver/udev/external_keyboard_is_connected.sh
chmod +x /usr/share/asus_touchpad_numpad-driver/udev/external_keyboard_is_disconnected.sh

sudo udevadm control --reload-rules

echo "i2c-dev" | tee /etc/modules-load.d/i2c-dev.conf >/dev/null

systemctl enable asus_touchpad_numpad

if [[ $? != 0 ]]; then
    echo "Something went wrong when enabling the asus_touchpad_numpad.service"
    exit 1
else
    echo "Asus touchpad service enabled"
fi

systemctl enable asus_touchpad_numpad_suspend

if [[ $? != 0 ]]; then
    echo "Something went wrong when enabling the asus_touchpad_numpad_suspend.service"
    exit 1
else
    echo "Asus touchpad suspend service enabled"
fi

systemctl restart asus_touchpad_numpad
if [[ $? != 0 ]]; then
    echo "Something went wrong when enabling the asus_touchpad_numpad.service"
    exit 1
else
    echo "Asus touchpad service started"
fi

systemctl restart asus_touchpad_numpad_suspend
if [[ $? != 0 ]]; then
    echo "Something went wrong when enabling the asus_touchpad_numpad_suspend.service"
    exit 1
else
    echo "Asus touchpad suspend service started"
fi

exit 0