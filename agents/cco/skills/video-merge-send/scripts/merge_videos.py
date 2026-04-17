#!/usr/bin/env python3
"""
Merge multiple video clips into one using ffmpeg concat demuxer.
Handles different resolutions/codecs by re-encoding to uniform format.

Usage:
    python merge_videos.py -i clip1.mp4 clip2.mp4 clip3.mp4 -o output.mp4
    python merge_videos.py -d ./clips/ -o output.mp4
    python merge_videos.py -d ./clips/ -o output.mp4 --transition fade --transition-duration 0.5
"""

import argparse
import subprocess
import sys
import os
import tempfile
import glob


def find_videos_in_dir(directory: str) -> list[str]:
    """Find all video files in directory, sorted by name."""
    extensions = ['*.mp4', '*.MP4', '*.mov', '*.MOV', '*.avi', '*.mkv', '*.webm']
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(directory, ext)))
    return sorted(files)


def get_video_info(path: str) -> dict:
    """Get video resolution and fps using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', '-select_streams', 'v:0', path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    import json
    data = json.loads(result.stdout)
    if data.get('streams'):
        s = data['streams'][0]
        return {
            'width': int(s.get('width', 0)),
            'height': int(s.get('height', 0)),
            'fps': eval(s.get('r_frame_rate', '30/1')),
        }
    return {}


def merge_with_reencode(input_files: list[str], output: str, 
                         transition: str = None, transition_duration: float = 0.5) -> bool:
    """Merge videos by re-encoding to uniform format. Optionally add transitions."""
    
    if not input_files:
        print("Error: No input files provided")
        return False
    
    # Get target resolution from first video
    info = get_video_info(input_files[0])
    width = info.get('width', 1080)
    height = info.get('height', 1920)
    
    # Ensure even dimensions
    width = width + (width % 2)
    height = height + (height % 2)
    
    if transition and transition in ('fade', 'xfade') and len(input_files) > 1:
        return merge_with_xfade(input_files, output, width, height, transition_duration)
    
    # Simple concat with re-encode
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for path in input_files:
            f.write(f"file '{os.path.abspath(path)}'\n")
        concat_file = f.name
    
    try:
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            output
        ]
        print(f"Merging {len(input_files)} clips → {output}")
        print(f"Target resolution: {width}x{height}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ffmpeg error: {result.stderr[-500:]}")
            return False
        
        size_mb = os.path.getsize(output) / (1024 * 1024)
        print(f"✅ Done! Output: {output} ({size_mb:.1f} MB)")
        return True
    finally:
        os.unlink(concat_file)


def merge_with_xfade(input_files: list[str], output: str, 
                      width: int, height: int, duration: float) -> bool:
    """Merge with crossfade transitions between clips."""
    
    # Build complex filter for xfade
    # First, scale all inputs
    inputs = []
    filter_parts = []
    
    for i, f in enumerate(input_files):
        inputs.extend(['-i', f])
        filter_parts.append(
            f'[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,'
            f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[v{i}]'
        )
    
    # Chain xfade filters
    current = 'v0'
    # Get durations to calculate offsets
    offsets = []
    cumulative = 0
    for i, f in enumerate(input_files[:-1]):
        info_cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', f
        ]
        r = subprocess.run(info_cmd, capture_output=True, text=True)
        dur = float(r.stdout.strip()) if r.stdout.strip() else 5.0
        cumulative += dur - duration
        offsets.append(cumulative)
    
    cumulative = 0
    for i in range(len(input_files) - 1):
        next_v = f'v{i+1}'
        out_label = f'xf{i}' if i < len(input_files) - 2 else 'vout'
        info_cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', input_files[i]
        ]
        r = subprocess.run(info_cmd, capture_output=True, text=True)
        dur = float(r.stdout.strip()) if r.stdout.strip() else 5.0
        offset = cumulative + dur - duration
        cumulative = offset
        
        filter_parts.append(
            f'[{current}][{next_v}]xfade=transition=fade:duration={duration}:offset={offset:.3f}[{out_label}]'
        )
        current = out_label
    
    filter_complex = ';'.join(filter_parts)
    
    cmd = ['ffmpeg', '-y'] + inputs + [
        '-filter_complex', filter_complex,
        '-map', '[vout]',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
        '-movflags', '+faststart',
        output
    ]
    
    print(f"Merging {len(input_files)} clips with fade transitions → {output}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"xfade error: {result.stderr[-500:]}")
        # Fallback to simple concat
        print("Falling back to simple concat...")
        return merge_with_reencode(input_files, output)
    
    size_mb = os.path.getsize(output) / (1024 * 1024)
    print(f"✅ Done! Output: {output} ({size_mb:.1f} MB)")
    return True


def main():
    parser = argparse.ArgumentParser(description='Merge video clips into one')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--inputs', nargs='+', help='Input video files in order')
    group.add_argument('-d', '--directory', help='Directory containing video clips (sorted by filename)')
    parser.add_argument('-o', '--output', required=True, help='Output video path')
    parser.add_argument('--transition', choices=['fade', 'none'], default='none',
                       help='Transition type between clips')
    parser.add_argument('--transition-duration', type=float, default=0.5,
                       help='Transition duration in seconds (default: 0.5)')
    
    args = parser.parse_args()
    
    if args.directory:
        input_files = find_videos_in_dir(args.directory)
        if not input_files:
            print(f"Error: No video files found in {args.directory}")
            sys.exit(1)
        print(f"Found {len(input_files)} video files:")
        for f in input_files:
            print(f"  - {os.path.basename(f)}")
    else:
        input_files = args.inputs
        for f in input_files:
            if not os.path.exists(f):
                print(f"Error: File not found: {f}")
                sys.exit(1)
    
    transition = args.transition if args.transition != 'none' else None
    success = merge_with_reencode(input_files, args.output, transition, args.transition_duration)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
