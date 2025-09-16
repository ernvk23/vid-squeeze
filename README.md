# 🚀 Video Re-encoder with Hardware Acceleration

A powerful and user-friendly Python script to efficiently re-encode your video files, significantly reducing their size while maintaining quality. It intelligently leverages hardware acceleration (Intel QSV or VAAPI) when available for faster processing, or falls back to optimized software encoding.

## ✨ Features

- **Smart Video Compression:** Reduce video file sizes without noticeable quality loss.
- **Hardware Acceleration:** Automatically detects and utilizes Intel Quick Sync Video (QSV) or VAAPI for blazing-fast encoding.
- **Customizable Output:** Choose your desired resolution, frame rate (FPS), and CPU thread count.
- **Batch Processing:** Recursively processes video files across multiple directories.
- **Graceful Interruption:** Safely stop the process at any time with `Ctrl+C`, ensuring temporary files are cleaned up.
- **Detailed Logging:** Keeps a comprehensive log of all processing activities and space savings.
- **Natural Sorting:** Processes directories and video files in a human-friendly, natural order.

## 🛠️ Installation & Usage

1.  **Download the script:**
    You can download the `squeeze.py` script directly using `curl`:
    ```bash
    curl -O https://raw.githubusercontent.com/ernvk23/vid-squeeze/main/squeeze.py
    ```
    *(Ensure you have `curl` installed. If not, install it via your package manager, e.g., `sudo apt install curl` on Debian/Ubuntu.)*

2.  **Install FFmpeg:**
    This script relies on `ffmpeg` for video processing. Ensure it's installed and accessible in your system's PATH.
    -   **Ubuntu/Debian:** `sudo apt update && sudo apt install ffmpeg`
    -   **Fedora:** `sudo dnf install ffmpeg`
    -   **Arch Linux:** `sudo pacman -S ffmpeg`
    -   **macOS (with Homebrew):** `brew install ffmpeg`

3.  **Install `vainfo` (for VAAPI detection on Linux):**
    If you plan to use VAAPI hardware acceleration on Linux, `vainfo` is recommended for detection.
    -   **Ubuntu/Debian:** `sudo apt install vainfo`
    -   **Fedora:** `sudo dnf install libva-utils`
    -   **Arch Linux:** `sudo pacman -S libva-utils`

4.  **Run the script:**
    Once downloaded and dependencies are met, navigate to the directory where you saved `squeeze.py` and run it:
    ```bash
    python3 squeeze.py
    ```

5.  **Follow the prompts:**
    The script will guide you through selecting your preferred resolution, FPS, and the number of CPU threads to use. It will then automatically detect and utilize available hardware acceleration.

    The script will process video files in the current directory and its subdirectories, replacing original files with their re-encoded, smaller versions. A detailed log file (`compression_log_*.txt`) will be created in the script's directory.

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.