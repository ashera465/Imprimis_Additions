
# Imprimis Additions — Setup & Usage

## 1. Clone the Repository

Clone the `Test` branch, including all submodules:

```bash
git clone --recursive -b Test https://github.com/ashera465/Imprimis_Additions.git
cd Imprimis_Additions
```

## 2. Install Dependencies & Build

From the workspace root, install ROS dependencies, build the workspace, and source the environment:

```bash
# Install ROS dependencies
rosdep install --from-paths src --ignore-src -r -y

# Build the workspace with symbolic links
colcon build --symlink-install

# Source the workspace environment
source install/setup.bash
```

## 3. Launch the NTRIP Client

```bash
ros2 launch ntrip_client ntrip.launch.py
```

**Requirements:**
- Valid credentials for the NTRIP caster, if authentication is required.
- Correct caster connection settings.
- A sourced ROS 2 workspace environment.

## 4. Run Without a GPS Receiver

To launch in simulation mode without a GPS receiver connected:

```bash
# Build the workspace
colcon build --symlink-install

# Source the workspace environment
source install/setup.bash

# Launch in simulation mode with the map enabled
ros2 launch ntrip_client ntrip.launch.py sim:=true show_map:=true
```

**Note:** Valid NTRIP caster credentials are still required when connecting to a protected caster. Simulation behavior depends on the launch configuration.

## 5. Create a New ROS 2 Python Package

Create an `ament_python` package with a starter node and the `rclpy` dependency:

```bash
ros2 pkg create \
    --build-type ament_python \
    --node-name my_node \
    my_py_pkg \
    --dependencies rclpy
```

Replace `my_py_pkg` and `my_node` with your desired package and node names.

## 6. Check USB Serial Ports (Linux)

Identify connected USB serial devices:

```bash
# Check kernel messages for serial and USB devices
sudo dmesg | grep -E "tty|ACM"

# List available USB serial ports
ls /dev/ttyUSB* /dev/ttyACM*
```

View serial output using `screen`:

```bash
sudo screen /dev/ttyACM0 38400
```

- Replace `/dev/ttyACM0` with the appropriate device path.
- Replace `38400` with the device's configured baud rate.

To exit `screen`, press `Ctrl+A`, then `K`, and confirm.

## 7. Clean the Workspace

To remove generated build artifacts and perform a clean rebuild:

```bash
# Remove generated workspace directories
rm -rf build/ install/ log/

# Reinstall dependencies
rosdep install --from-paths src --ignore-src -r -y

# Rebuild and source the workspace
colcon build --symlink-install
source install/setup.bash
```

**Warning:** Run these commands from the workspace root. The `rm -rf` command permanently removes the specified directories.
