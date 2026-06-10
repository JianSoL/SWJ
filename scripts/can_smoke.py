import argparse
import json
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ZLGCanControl import Communication


def load_config():
    defaults = {
        "can_type": "usb_can_2eu",
        "can_idx": 0,
        "chn": 1,
        "baud_rate": 500,
    }
    config_path = PROJECT_DIR / "config.json"
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
        defaults.update({key: loaded[key] for key in defaults.keys() & loaded.keys()})
    defaults["can_idx"] = int(defaults["can_idx"])
    defaults["chn"] = int(defaults["chn"])
    defaults["baud_rate"] = int(defaults["baud_rate"])
    return defaults


def format_frame(frame):
    data = " ".join(f"{value:02X}" for value in frame.data)
    frame_type = "EXT" if frame.extern_flag else "STD"
    return f"id=0x{frame.frame_id:X},{frame_type},dlc={frame.data_len},data=[{data}]"


def main():
    parser = argparse.ArgumentParser(description="AIDC CAN hardware smoke test")
    parser.add_argument("--duration", type=float, default=5.0, help="listen duration in seconds")
    parser.add_argument("--send-check", action="store_true", help="send one safe CMD_CHK_CAN frame")
    parser.add_argument("--target", type=lambda value: int(value, 0), default=0xA0, help="target BCU address")
    parser.add_argument("--source", type=lambda value: int(value, 0), default=0xF2, help="upper computer source address")
    args = parser.parse_args()

    config = load_config()
    can = Communication()
    ok, message = can.set_can_board_configuration(
        config["can_type"],
        config["can_idx"],
        config["chn"],
        config["baud_rate"],
    )
    if not ok:
        raise RuntimeError(message)

    print(
        "can_smoke,open,"
        f"type={config['can_type']},index={config['can_idx']},"
        f"channel={config['chn']},baud={config['baud_rate']}k",
        flush=True,
    )

    total_rx = 0
    samples = []
    try:
        can.open_new()
        if args.send_check:
            frame_id = 0x1C000000 | (0xEE << 16) | ((args.target & 0xFF) << 8) | (args.source & 0xFF)
            result = can.Transmit(frame_id, [0] * 8, extern_flag=True, data_len=8)
            print(f"can_smoke,tx_check,id=0x{frame_id:X},result={result}", flush=True)

        deadline = time.time() + max(args.duration, 0)
        while time.time() < deadline:
            frames = can.receive_frames(max_count=200, timeout_ms=50)
            total_rx += len(frames)
            for frame in frames:
                if len(samples) < 20:
                    samples.append(format_frame(frame))
            time.sleep(0.02)

        print(f"can_smoke,rx_total={total_rx}", flush=True)
        for sample in samples:
            print(f"can_smoke,rx_sample,{sample}", flush=True)
    finally:
        can.Close()
        print("can_smoke,close=ok", flush=True)


if __name__ == "__main__":
    main()
