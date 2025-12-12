# piledbox

A WS281x LED driver for Raspberry Pi 5 that receives sACN (E1.31) and outputs to LED fixtures via GPIO.

## Features

- **sACN Protocol Support**: Receives lighting data via sACN/E1.31 unicast
- **Multi-Output**: Control up to 4 independent GPIO outputs
- **Pixel Format Support**: RGB8
- **Real-Time Monitoring**: Web dashboard with live sACN data, fixture configuration, and application logs
- **YAML Configuration**: Easy configuration via yaml file

## Requirements

### Hardware
- Raspberry Pi 5

### Software
- Raspberry Pi OS (tested on Debian 13)

## Deployment

Deployment is available manually or via Ansible.

### Manual

#### 1. Check permissions on /dev/pio0

Check `/dev/pio0` is properly configured (important for older Raspbian version):

```bash
ls -l /dev/pio0
```
If the command fails, you must update the board firmware:
```bash
sudo apt update
sudo apt upgrade -y
sudo rpi-eeprom-update -a
```
Then reboot:
```bash
sudo reboot
```
Check `ls -l /dev/pio0` outputs something along the lines of:
```bash
# this is good
crw-rw---- 1 root gpio 240, 0 Dec  6 12:15 /dev/pio0
``` 
If it shows anything different, eg:
```bash
# this is bad
crw-rw---- 1 root root 240, 0 Dec  6 12:15 /dev/pio0
```
Then you must update some permissions:
```bash
sudo nano /etc/udev/rules.d/99-com.rules
```
Add the following line at the end:
```
echo 'SUBSYSTEM=="*-pio", GROUP="gpio", MODE="0660"' 
```
Reboot to apply:
```
sudo reboot
```

Modern Raspberry Pi OS versions should configure this automatically.

### 2. Install system dependencies

Install the lgpio library and development tools:

```bash
sudo apt update
sudo apt install swig python3-dev python3-setuptools liblgpio-dev
```

#### 3. Install uv package manager

Install uv for Python package management:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Update your shell to include uv in PATH (or restart your shell):

```bash
source $HOME/.local/bin/env
```

#### 4. Install piledbox

Clone this repo:

```bash
git clone https://github.com/fabio-rinaldo/piledbox.git
cd piledbox
```

You can either run from source or install as a system-wide tool:

**Option A: Run from source**
```bash
uv run piledbox start -c path-to-config.yml
```

**Option B: Install as system-wide tool**
```bash
uv tool install .
```

### Ansible

Playbooks to provision a microSD card and deploy **piledbox** to a RPi5 via SSH are available at [this repository](https://github.com/fabio-rinaldo/piledbox-ansible).

## Configuration

Create a `config.yaml` file to define your LED setup. The configuration describes network settings, GPIO pins, and LED fixtures.

### Example

```yaml
version: "1.0"

input:
  protocol: "sacn"
  mode: "unicast"
  interface: "eth0"
  # ipv4: "192.168.1.100"
  # web_gui_port: 5011 # default: 5010 if absent

outputs: 
  out1:
    gpio: 14
    pixel_type: "rgb8"
    strips:
      - label: "front door"
        pixel_count: 50
        universe: 14
        start_channel: 100
      # - label: "fence"
      #   pixel_count: 20
      #   universe: 5
      #   start_channel: 197

  out2:
    gpio: 15
    pixel_type: "rgb8"
    strips:
      - label: "living room window"
        pixel_count: 60
        universe: 7
        start_channel: 75

  # out3 and out4 can be configured similarly (optional)
```

### Configuration options

The configuration is imported and validated at startup.

#### Input Section
- `protocol`: Must be `"sacn"` (only sACN/E1.31 is supported)
- `mode`: Must be `"unicast"` (multicast not currently supported)
- `interface`: Network interface name (e.g., `eth0`, `wlan0`)
  - The first IPv4 address found on this interface will be used
  - If `ipv4` is also specified, that address will be validated against this interface
- `ipv4`: Specific IPv4 address to bind to
  - Must exist on the specified interface
  - If omitted, uses the first IPv4 found on `interface`
- `web_gui_port` (optional): TCP port for web dashboard (default: 5010)

Either `ipv4` or `interface` (or both) must be present.
Both sACN receiver and web interface will be bound to the same IP address.

#### Output section
You can define 1 to 4 outputs (`out1`, `out2`, `out3`, `out4`):

- `gpio`: GPIO pin number
- `pixel_type`: LED pixel format - `rgb8` only atm
- `strips`: Array of LED fixtures configuration
  - `label`: Human-readable name (must be unique across all fixtures)
  - `pixel_count`: Number of LEDs in the strip
  - `universe`: sACN universe number
  - `start_channel`: Starting DMX channel (1-512)
    - Each strip must fit within a single 512-channel universe
    - For rgb8: each pixel uses 3 channels, so 170 pixels max per universe

The order in which strips are declared matters, as the WS281x protocol outputs data serially. First strip declared in the array should be the first one physically connected to the GPIO output.

## How to use

### Starting the app

```bash
# Using ./config.yaml in current directory
piledbox start

# Or specify a custom config file
piledbox start -c /path/to/config.yaml

# If running from source
uv run piledbox start -c /path/to/config.yaml
```

The application will:
1. Load and validate `config.yaml`
2. Start the sACN receiver on the specified network interface
3. Spawn a worker process to drive the GPIO outputs
4. Launch the web dashboard on the specified network interface

### Stopping the app

```bash
piledbox stop

# If running from source
uv run piledbox stop
```

This gracefully terminates both the main process and GPIO worker process.

### Web Dashboard

Once started, access the monitoring dashboard at:

```
http://<raspberry-pi-ip>:5010/
```

The dashboard provides:
- **Host machine information**
- **sACN Monitor**: Real-time visualization of incoming DMX data with heatmap display
- **Fixture Patches**: Overview of configured LED fixtures
- **Console Logs**: Live log output

## License

This project is free software, licensed under the GNU General Public License v2.0. You are free to use, study, modify, and share this software. If you distribute copies or modifications, you must do so under the same license terms. See the [LICENSE](LICENSE) file for the full license text.

## Credits

This project dependancies include [Adafruit](https://www.adafruit.com/)'s [Neopixel](https://github.com/adafruit/Adafruit_Blinka_Raspberry_Pi5_Neopixel) library.

The library has been modified by the author ( [project link](https://github.com/fabio-rinaldo/Adafruit_Blinka_Raspberry_Pi5_Neopixel/tree/quad-sm) ) to all 4 state machines provided by the RPi5.
