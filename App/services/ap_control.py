"""
AP control service: change SSID, password, stop/start the AP.
Interacts with wifipumpkin3 Docker container and hostapd config.
"""
import subprocess
import logging
import re

logger = logging.getLogger("ap_control")


def _run(cmd: str, timeout: int = 15) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except Exception as e:
        return 1, str(e)


def get_ap_status() -> dict:
    """Get current AP status from iw and hostapd config."""
    raw = subprocess.run("iw dev wlan1 info", shell=True, capture_output=True, text=True).stdout
    info = {"ssid": None, "bssid": None, "channel": None, "txpower": None,
            "type": None, "running": False, "security": None, "password": None}

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("ssid"):
            info["ssid"] = line.split(" ", 1)[1] if " " in line else None
        elif line.startswith("addr"):
            info["bssid"] = line.split(" ", 1)[1] if " " in line else None
        elif line.startswith("channel"):
            m = re.search(r"(\d+)", line)
            if m:
                info["channel"] = int(m.group(1))
        elif line.startswith("txpower"):
            m = re.search(r"([\d.]+)", line)
            if m:
                info["txpower"] = float(m.group(1))
        elif line.startswith("type"):
            info["type"] = line.split(" ", 1)[1] if " " in line else None

    info["running"] = info["type"] == "AP" and info["ssid"] is not None

    # Get security info from hostapd config
    rc, out = _run("docker exec wifipumpkin3 cat /root/.config/wifipumpkin3/config/hostapd/hostapd.conf")
    if rc == 0:
        for line in out.splitlines():
            if line.startswith("wpa="):
                wpa_ver = line.split("=")[1]
                info["security"] = f"WPA{wpa_ver}-PSK"
            elif line.startswith("wpa_passphrase="):
                info["password"] = line.split("=", 1)[1]

    # Docker container status
    rc2, out2 = _run("docker ps --filter name=wifipumpkin3 --format '{{.Status}}'")
    info["docker_status"] = out2.strip() if rc2 == 0 else "unknown"

    return info


def update_ssid(new_ssid: str) -> dict:
    """Change the SSID of the fake AP."""
    logger.info(f"Changing SSID to: {new_ssid}")

    # Update wifipumpkin3 config
    rc, out = _run(
        f"docker exec wifipumpkin3 sed -i 's/^ssid=.*/ssid={new_ssid}/' "
        "/root/.config/wifipumpkin3/config/app/config.ini"
    )

    # Restart container
    rc2, out2 = _run("docker restart wifipumpkin3", timeout=30)

    return {"success": rc2 == 0, "message": out2.strip()}


def update_password(new_password: str) -> dict:
    """Change the WPA2 password."""
    if len(new_password) < 8:
        return {"success": False, "message": "Password must be at least 8 characters"}

    logger.info("Changing AP password")

    # Update in wifipumpkin3 config
    _run(
        f"docker exec wifipumpkin3 sed -i 's/^wpa_sharedkey=.*/wpa_sharedkey={new_password}/' "
        "/root/.config/wifipumpkin3/config/app/config.ini"
    )

    # Restart container
    rc, out = _run("docker restart wifipumpkin3", timeout=30)

    return {"success": rc == 0, "message": out.strip()}


def stop_ap() -> dict:
    """Stop the fake AP (docker compose down)."""
    logger.info("Stopping AP")
    rc, out = _run("docker stop wifipumpkin3", timeout=30)
    return {"success": rc == 0, "message": "AP stopped" if rc == 0 else out.strip()}


def start_ap() -> dict:
    """Start the fake AP (docker compose up)."""
    logger.info("Starting AP")
    rc, out = _run("docker start wifipumpkin3", timeout=30)
    return {"success": rc == 0, "message": "AP started" if rc == 0 else out.strip()}
