# Minimal Linux for Raspberry Pis

## Configure WiFi
```
cat > board/rpi-zero/overlay/etc/wpa_supplicant/wpa_supplicant.conf << 'EOF'
update_config=1
# country=US

network={
    ssid="mySSID"
    psk="my_passphrase"
    key_mgmt=WPA-PSK
}
EOF
```

### SSH Key (optional)
```
mkdir -p ~/work/br-ext/board/rpi-zero/overlay/root/.ssh
cat > ~/work/br-ext/board/rpi-zero/overlay/root/.ssh/authorized_keys << 'EOF'
ssh-rsa AAAAB3... your-key-here
EOF
```

## Build
In buildroot run:
```
make BR2_EXTERNAL=path-to-this-root rpi0w_autowifi_defconfig
make -j$(nproc)
```

## Write image
Use Raspberry Pi Imager app or dd comand.
