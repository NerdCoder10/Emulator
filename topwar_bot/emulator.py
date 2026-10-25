"""Start an Android emulator (AVD) or connect to BlueStacks/LDPlayer/MuMu, then launch Top War."""
import shutil
import subprocess
import time

from .device import Device


def adb_devices(adb="adb"):
    out = subprocess.run([adb, "devices"], capture_output=True, text=True, check=True).stdout
    return [line.split()[0] for line in out.splitlines()[1:] if line.strip().endswith("device")]


def start_avd(avd_name, emulator_bin="emulator", headless=False, extra_args=()):
    """Launch an Android Studio AVD in the background and return the process."""
    if not shutil.which(emulator_bin):
        raise FileNotFoundError(
            f"'{emulator_bin}' not found. Install the Android SDK emulator and add "
            "$ANDROID_HOME/emulator to PATH, or set emulator.binary in config.yaml."
        )
    args = [emulator_bin, "-avd", avd_name, "-no-snapshot-save", "-gpu", "auto"]
    if headless:
        args += ["-no-window", "-no-audio"]
    args += list(extra_args)
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def connect(address, adb="adb"):
    """Connect adb to a network emulator such as BlueStacks (127.0.0.1:5555)."""
    subprocess.run([adb, "connect", address], capture_output=True, check=True)


def wait_for_boot(device: Device, timeout=300):
    device.adb("wait-for-device", timeout=timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if device.shell("getprop sys.boot_completed") == "1":
                return
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError("Emulator did not finish booting in time")


def ensure_running(cfg) -> Device:
    """Bring up the emulator described in config and return a ready Device."""
    emu = cfg["emulator"]
    adb = emu.get("adb", "adb")
    mode = emu.get("mode", "avd")

    if mode == "connect":
        connect(emu["address"], adb)
        serial = emu["address"]
    else:
        serial = emu.get("serial")
        if not adb_devices(adb):
            start_avd(emu["avd_name"], emu.get("binary", "emulator"), emu.get("headless", False))
            # The serial isn't known until adb sees the new emulator.
            for _ in range(60):
                if adb_devices(adb):
                    break
                time.sleep(2)
        serial = serial or (adb_devices(adb) or [None])[0]

    device = Device(serial=serial, adb=adb, tap_jitter=cfg["bot"].get("tap_jitter", 3))
    wait_for_boot(device)

    apk = emu.get("install_apk")
    package = cfg["game"]["package"]
    if apk and package not in device.shell("pm list packages"):
        device.adb("install", "-r", apk, timeout=600)
    return device
