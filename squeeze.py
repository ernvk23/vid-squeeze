import os
import subprocess
import shutil
import time
import re
import signal
import sys
from datetime import datetime

# Global variables to track state for graceful interruption
current_video_processing = None
current_temp_file = None
interrupted = False

def signal_handler(sig, frame):
    global interrupted, current_temp_file
    print("\n\nReceived interrupt signal. Cleaning up...")
    interrupted = True
    
    # Clean up current temporary file if it exists
    if current_temp_file and os.path.exists(current_temp_file):
        try:
            os.remove(current_temp_file)
            log_message(f"Cleaned up temporary file: {current_temp_file}")
        except Exception as e:
            log_message(f"Error cleaning up temporary file: {e}")
    
    # Show summary before exiting
    show_summary()
    sys.exit(0)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)

# Setup logging
log_file = os.path.join(os.getcwd(), f"compression_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

def log_message(message):
    """Log message to both console and log file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message)
    with open(log_file, "a") as f:
        f.write(formatted_message + "\n")

def format_size(size_bytes):
    """Convert bytes to human-readable format"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names)-1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f}{size_names[i]}"

def calculate_reduction(original, compressed):
    """Calculate size reduction percentage"""
    if original == 0:
        return 0
    return ((original - compressed) / original) * 100

def detect_qsv_support():
    """Detect if Intel QSV hardware acceleration is available"""
    try:
        # Test QSV with FFmpeg
        test_cmd = [
            "ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=1",
            "-init_hw_device", "qsv=qsv",
            "-hwaccel", "qsv", "-hwaccel_output_format", "qsv",
            "-c:v", "h264_qsv", "-t", "1", "-f", "null", "-"
        ]
        
        result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return True, "Intel QSV hardware acceleration available"
        else:
            return False, f"QSV test failed"
            
    except subprocess.TimeoutExpired:
        return False, "QSV test timed out"
    except FileNotFoundError:
        return False, "FFmpeg not found"
    except Exception as e:
        return False, f"Error testing QSV: {e}"

def detect_vaapi_support():
    """Detect if VAAPI hardware acceleration is available using vainfo"""
    try:
        # First check if vainfo is available
        vainfo_result = subprocess.run(['vainfo'], capture_output=True, text=True, timeout=5)
        
        if vainfo_result.returncode != 0:
            return False, "vainfo not available or no VAAPI devices"
        
        # Check if H.264 encoding is supported
        vainfo_output = vainfo_result.stdout.lower()
        if 'vah264encodeprofile' in vainfo_output or 'h264' in vainfo_output:
            return True, "VAAPI hardware acceleration available (H.264 encoding supported)"
        else:
            return False, "VAAPI available but H.264 encoding not supported"
            
    except subprocess.TimeoutExpired:
        return False, "vainfo test timed out"
    except FileNotFoundError:
        return False, "vainfo not installed"
    except Exception as e:
        return False, f"Error checking VAAPI: {e}"

def get_cpu_count():
    """Get the number of CPU cores available"""
    try:
        return os.cpu_count() or 4
    except:
        return 4

def get_user_encoding_preferences():
    """Get user preferences for resolution, FPS, and thread count"""
    print("\n" + "="*50)
    print("ENCODING CONFIGURATION")
    print("="*50)
    
    # Resolution selection
    resolution_options = {
        "1": ("1920x1080", "1080p (Full HD)"),
        "2": ("1280x720", "720p (HD)"),
        "3": ("854x480", "480p (SD)"),
        "4": ("640x360", "360p"),
        "5": ("original", "Keep original resolution")
    }
    
    print("\nSelect target resolution:")
    for key, (res, desc) in resolution_options.items():
        print(f"  {key}: {desc}")
    
    while True:
        try:
            res_choice = input("\nEnter choice (1-5): ").strip()
            if res_choice in resolution_options:
                selected_resolution = resolution_options[res_choice][0]
                print(f"Selected: {resolution_options[res_choice][1]}")
                break
            else:
                print("Invalid choice. Please enter 1-5.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            sys.exit(0)
    
    # FPS selection
    fps_options = {
        "0": ("original", "Keep original FPS"),
        "1": ("60", "60 FPS"),
        "2": ("30", "30 FPS"),
        "3": ("24", "24 FPS (Cinema)"),
        "4": ("15", "15 FPS"),
        "5": ("12", "12 FPS")
    }
    
    print("\nSelect target FPS:")
    for key, (fps, desc) in fps_options.items():
        print(f"  {key}: {desc}")
    
    while True:
        try:
            fps_choice = input("\nEnter choice (0-5): ").strip()
            if fps_choice in fps_options:
                selected_fps = fps_options[fps_choice][0]
                print(f"Selected: {fps_options[fps_choice][1]}")
                break
            else:
                print("Invalid choice. Please enter 0-5.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            sys.exit(0)
    
    # Thread count selection
    max_threads = get_cpu_count()
    print(f"\nSelect number of threads (Max available: {max_threads}):")
    print(f"  1: 1 thread (slowest, lowest CPU usage)")
    print(f"  2: 2 threads")
    print(f"  4: 4 threads")
    if max_threads >= 8:
        print(f"  8: 8 threads")
    print(f"  {max_threads}: {max_threads} threads (fastest, highest CPU usage)")
    
    while True:
        try:
            thread_input = input(f"\nEnter number of threads (1-{max_threads}): ").strip()
            if thread_input:
                selected_threads = int(thread_input)
                if 1 <= selected_threads <= max_threads:
                    print(f"Selected: {selected_threads} threads")
                    break
                else:
                    print(f"Invalid choice. Please enter 1-{max_threads}.")
            else:
                selected_threads = min(4, max_threads)  # Default to 4 or max available
                print(f"Using default: {selected_threads} threads")
                break
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            sys.exit(0)
    
    return selected_resolution, selected_fps, selected_threads

def build_ffmpeg_command(input_path, output_path, resolution, fps, threads, hw_type="software"):
    """Build FFmpeg command based on hardware acceleration type and user preferences"""
    
    if hw_type == "qsv":
        # Intel QSV command (your working configuration)
        cmd = [
            "ffmpeg",
            "-init_hw_device", "qsv=qsv",
            "-hwaccel", "qsv",
            "-hwaccel_output_format", "qsv",
            "-i", input_path
        ]
        
        # Build video filter
        filters = []
        
        # Add scaling if not original resolution
        if resolution != "original":
            filters.append(f"scale_qsv={resolution}")
        
        # Add FPS filter if not original
        if fps != "original":
            filters.append(f"fps={fps}")
        
        # Apply filters
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
        
        cmd.extend([
            "-c:v", "h264_qsv",
            "-preset", "faster",
            "-threads", str(threads),
            "-y",  # Overwrite output file
            output_path
        ])
        
    elif hw_type == "vaapi":
        # VAAPI command
        cmd = [
            "ffmpeg",
            "-init_hw_device", "vaapi=va:/dev/dri/renderD128",
            "-hwaccel", "vaapi",
            "-hwaccel_output_format", "vaapi",
            "-i", input_path
        ]
        
        # Build video filter
        filters = []
        
        # Add scaling if not original resolution
        if resolution != "original":
            # VAAPI scale_vaapi needs width:height format, not widthxheight
            width, height = resolution.split('x')
            filters.append(f"scale_vaapi=w={width}:h={height}")
        
        # Add FPS filter if not original
        if fps != "original":
            filters.append(f"fps={fps}")
        
        # Apply filters
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
        
        cmd.extend([
            "-c:v", "h264_vaapi",
            "-qp", "23",  # Quality parameter for VAAPI
            "-y",  # Overwrite output file
            output_path
        ])
        
    else:
        # Software encoding fallback
        cmd = [
            "ffmpeg",
            "-i", input_path
        ]
        
        # Build video filter
        filters = []
        
        # Add scaling if not original resolution
        if resolution != "original":
            filters.append(f"scale={resolution}")
        
        # Add FPS filter if not original
        if fps != "original":
            filters.append(f"fps={fps}")
        
        # Apply filters
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
        
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "faster",
            "-crf", "23",  # Quality parameter for software encoding
            "-threads", str(threads),
            "-y",  # Overwrite output file
            output_path
        ])
    
    return cmd

def is_video_file(filename):
    """Check if file is a video file and not a temporary file"""
    # Skip temporary files
    if filename.startswith('temp_'):
        return False
    
    # Check if file has a video extension
    ext = os.path.splitext(filename)[1].lower()
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm']
    return ext in video_extensions

def clean_filename(filename):
    """Remove duplicate extensions from filename"""
    # Pattern to match duplicate extensions like .mp4.mp4
    pattern = r'(\.[a-zA-Z0-9]+)(\1)$'
    cleaned = re.sub(pattern, r'\1', filename)
    
    if cleaned != filename:
        log_message(f"    Cleaned filename: {filename} -> {cleaned}")
    
    return cleaned

def natural_sort_key(s):
    """
    Key for natural sorting of strings containing numbers.
    Helps sort directories like "Module 1", "Module 2", "Module 10" correctly.
    """
    return [int(text) if text.isdigit() else text.lower() 
            for text in re.split(r'(\d+)', s)]

def get_user_start_index(directories):
    """Prompt user to select a starting directory index"""
    print("\nDirectories found (sorted order):")
    for i, directory in enumerate(directories):
        dir_name = os.path.basename(directory)
        print(f"  {i}: {dir_name}")
    
    print("\nEnter the number of the directory to start from (or press Enter to start from the beginning):")
    
    try:
        user_input = input("Choice: ").strip()
        if user_input:
            start_index = int(user_input)
            if 0 <= start_index < len(directories):
                return start_index
            else:
                print(f"Invalid input. Starting from the beginning.")
        else:
            print("Starting from the beginning.")
    except ValueError:
        print("Invalid input. Starting from the beginning.")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error getting user input: {e}. Starting from the beginning.")
    
    return 0

def show_summary():
    """Display summary of processing"""
    log_message("=" * 80)
    log_message("PROCESSING SUMMARY:")
    log_message(f"Directories processed: {stats['processed_dirs']}/{stats['total_dirs']}")
    log_message(f"Videos found: {stats['total_videos']}")
    log_message(f"Videos successfully processed: {stats['processed_videos']}")
    log_message(f"Videos failed: {stats['failed_videos']}")
    log_message(f"Videos skipped: {stats['skipped_videos']}")
    log_message(f"Videos renamed: {stats['renamed_videos']}")
    log_message(f"Total original size: {format_size(stats['total_original_size'])}")
    log_message(f"Total compressed size: {format_size(stats['total_compressed_size'])}")
    
    if stats['total_original_size'] > 0:
        total_reduction = calculate_reduction(stats['total_original_size'], stats['total_compressed_size'])
        total_saved = stats['total_original_size'] - stats['total_compressed_size']
        
        if total_saved > 0:
            log_message(f"Total space saved: {format_size(total_saved)}")
            log_message(f"Overall reduction: {total_reduction:.2f}%")
        else:
            log_message(f"Total space increased: {format_size(-total_saved)}")
            log_message(f"Overall increase: {-total_reduction:.2f}%")
    
    log_message(f"Detailed log saved to: {log_file}")
    log_message("=" * 80)

def has_video_files(directory):
    """Check if a directory contains any video files"""
    try:
        files = os.listdir(directory)
        for f in files:
            if os.path.isfile(os.path.join(directory, f)) and is_video_file(f):
                return True
    except Exception as e:
        log_message(f"Error checking directory {directory}: {e}")
    return False

# Main execution starts here
print("Video Re-encoding Script with Hardware Acceleration")
print("=" * 60)

# Detect hardware acceleration support
qsv_supported, qsv_message = detect_qsv_support()
vaapi_supported, vaapi_message = detect_vaapi_support()

print("\nHardware Acceleration Detection:")
print(f"Intel QSV: {'✓' if qsv_supported else '✗'} {qsv_message}")
print(f"VAAPI: {'✓' if vaapi_supported else '✗'} {vaapi_message}")

# Determine best hardware acceleration method - prioritize VAAPI as requested
if vaapi_supported:
    hw_acceleration = "vaapi"
    hw_message = "Using VAAPI hardware acceleration"
elif qsv_supported:
    hw_acceleration = "qsv" 
    hw_message = "Using Intel QSV hardware acceleration"
else:
    hw_acceleration = "software"
    hw_message = "Using software encoding (no hardware acceleration)"

print(f"\n{hw_message}")
log_message(f"Hardware acceleration: {hw_message}")

# Get user encoding preferences
target_resolution, target_fps, target_threads = get_user_encoding_preferences()

# Get current directory
current_dir = os.getcwd()

# Get all subdirectories (excluding the current directory)
all_directories = []
for root, dirs, files in os.walk(current_dir):
    for dir_name in dirs:
        full_path = os.path.join(root, dir_name)
        all_directories.append(full_path)

# Check if current directory has video files
if has_video_files(current_dir):
    all_directories.insert(0, current_dir)  # Add current directory at the beginning if it has videos
else:
    log_message(f"Current directory '{os.path.basename(current_dir)}' doesn't contain video files, skipping it.")

# Sort directories using natural sort (so numbered folders are in order)
all_directories.sort(key=lambda x: natural_sort_key(os.path.basename(x)))

# Filter out directories that don't have video files
directories_with_videos = []
for directory in all_directories:
    if has_video_files(directory):
        directories_with_videos.append(directory)
    else:
        log_message(f"Directory '{os.path.basename(directory)}' doesn't contain video files, skipping it.")

# Ask user for starting directory
if directories_with_videos:
    start_index = get_user_start_index(directories_with_videos)
    directories_to_process = directories_with_videos[start_index:]
else:
    log_message("No directories with video files found. Exiting.")
    sys.exit(0)

log_message(f"Video compression process started")
log_message(f"Hardware acceleration: {hw_acceleration.upper()}")
log_message(f"Target resolution: {target_resolution}")
log_message(f"Target FPS: {target_fps}")
log_message(f"Threads: {target_threads}")
log_message(f"Found {len(directories_with_videos)} directories with video files to process")
log_message(f"Starting from directory {start_index}: {os.path.basename(directories_with_videos[start_index])}")
log_message("Directory processing order:")
for i, directory in enumerate(directories_to_process, start_index):
    log_message(f"  {i}. {os.path.basename(directory)}")
log_message("=" * 80)

# Track processing statistics
stats = {
    'total_dirs': len(directories_with_videos),
    'processed_dirs': 0,
    'total_videos': 0,
    'processed_videos': 0,
    'failed_videos': 0,
    'skipped_videos': 0,
    'renamed_videos': 0,
    'total_original_size': 0,  # in bytes
    'total_compressed_size': 0  # in bytes
}

# Process each directory in sorted order
for directory in directories_to_process:
    if interrupted:
        break
        
    # Track folder-level statistics
    folder_stats = {
        'original_size': 0,
        'compressed_size': 0,
        'videos_processed': 0,
        'videos_failed': 0
    }
    
    log_message(f"Processing directory ({stats['processed_dirs'] + 1}/{stats['total_dirs']}): {os.path.basename(directory)}")
    log_message(f"Full path: {directory}")
    
    # List video files in this directory using our custom function
    videos = [f for f in os.listdir(directory) 
              if os.path.isfile(os.path.join(directory, f)) and 
              is_video_file(f)]
    
    # Sort videos using natural sort as well
    videos.sort(key=natural_sort_key)
    
    if not videos:
        log_message("No video files found in this directory")
        stats['processed_dirs'] += 1
        continue
        
    stats['total_videos'] += len(videos)
    log_message(f"Found {len(videos)} video(s) to process in this directory")
    
    # Process each video in the directory
    for i, video in enumerate(videos, 1):
        if interrupted:
            break
            
        input_path = os.path.join(directory, video)
        
        # Clean the filename to remove duplicate extensions
        cleaned_video = clean_filename(video)
        final_output_name = cleaned_video
        
        # Create a safe temporary filename
        temp_output_path = os.path.join(directory, f"temp_{cleaned_video.replace(' ', '_')}")
        
        # Update global variables for interruption handling
        current_video_processing = video
        current_temp_file = temp_output_path
        
        # Check if file still exists before processing
        if not os.path.exists(input_path):
            log_message(f"  ⚠ Skipping video {i}/{len(videos)}: {video} (file no longer exists)")
            stats['skipped_videos'] += 1
            continue
            
        try:
            # Get original file size
            original_size = os.path.getsize(input_path)
            stats['total_original_size'] += original_size
            folder_stats['original_size'] += original_size
            
            log_message(f"  Converting video {i}/{len(videos)}: {video}")
            if video != cleaned_video:
                log_message(f"    Will rename to: {cleaned_video}")
                stats['renamed_videos'] += 1
            log_message(f"    Original size: {format_size(original_size)}")
            
            # Build FFmpeg command
            cmd = build_ffmpeg_command(input_path, temp_output_path, target_resolution, target_fps, target_threads, hw_acceleration)
            
            # Run conversion
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # If conversion successful, replace original
            if os.path.exists(temp_output_path):
                # Get compressed file size
                compressed_size = os.path.getsize(temp_output_path)
                stats['total_compressed_size'] += compressed_size
                folder_stats['compressed_size'] += compressed_size
                
                # Calculate savings
                reduction = calculate_reduction(original_size, compressed_size)
                
                # Remove original
                os.remove(input_path)
                
                # Determine final output path
                final_output_path = os.path.join(directory, final_output_name)
                
                # Rename temp to final name
                shutil.move(temp_output_path, final_output_path)
                
                log_message(f"    ✓ Successfully converted: {video}")
                if video != final_output_name:
                    log_message(f"    Renamed to: {final_output_name}")
                log_message(f"    Compressed size: {format_size(compressed_size)}")
                
                if reduction > 0:
                    log_message(f"    Reduction: {reduction:.2f}% (saved {format_size(original_size - compressed_size)})")
                else:
                    log_message(f"    Increase: {-reduction:.2f}% (added {format_size(compressed_size - original_size)})")
                
                stats['processed_videos'] += 1
                folder_stats['videos_processed'] += 1
            else:
                log_message(f"    ✗ Conversion failed (output missing): {video}")
                stats['failed_videos'] += 1
                folder_stats['videos_failed'] += 1
                
        except subprocess.CalledProcessError as e:
            log_message(f"    ✗ Error converting {video}: {e.stderr if e.stderr else 'Unknown error'}")
            stats['failed_videos'] += 1
            folder_stats['videos_failed'] += 1
            # Clean up temporary file if it exists
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
        except FileNotFoundError as e:
            log_message(f"    ⚠ File not found during processing: {video} - {e}")
            stats['skipped_videos'] += 1
        except Exception as e:
            log_message(f"    ⚠ Unexpected error processing {video}: {e}")
            stats['failed_videos'] += 1
            folder_stats['videos_failed'] += 1
            # Clean up temporary file if it exists
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
        
        # Reset current processing variables
        current_video_processing = None
        current_temp_file = None
    
    # Show folder-level summary
    if folder_stats['original_size'] > 0:
        folder_reduction = calculate_reduction(folder_stats['original_size'], folder_stats['compressed_size'])
        folder_saved = folder_stats['original_size'] - folder_stats['compressed_size']
        
        log_message(f"Folder '{os.path.basename(directory)}' summary:")
        log_message(f"  Videos processed: {folder_stats['videos_processed']}")
        log_message(f"  Videos failed: {folder_stats['videos_failed']}")
        log_message(f"  Original size: {format_size(folder_stats['original_size'])}")
        log_message(f"  Compressed size: {format_size(folder_stats['compressed_size'])}")
        
        if folder_saved > 0:
            log_message(f"  Space saved: {format_size(folder_saved)}")
            log_message(f"  Reduction: {folder_reduction:.2f}%")
        else:
            log_message(f"  Space increased: {format_size(-folder_saved)}")
            log_message(f"  Increase: {-folder_reduction:.2f}%")
    
    stats['processed_dirs'] += 1
    log_message(f"Finished processing directory: {os.path.basename(directory)}")
    log_message("-" * 80)

# Show final summary
show_summary()

# Reset terminal if we were interrupted
if interrupted:
    print("\nProcessing interrupted by user. Summary displayed above.")
    print(f"Detailed log saved to: {log_file}")
