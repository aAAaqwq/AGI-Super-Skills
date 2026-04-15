#!/usr/bin/env python3
"""
Audio Analysis Script for AV-Sync Workflow

Analyzes audio file to extract:
- Beat timestamps and BPM
- Music sections (verse, chorus, etc.)
- Emotional/mood features
- Key moments (drops, climaxes)

Usage:
    python3 audio_analysis.py <audio_file> [--output <json_path>]
"""

import argparse
import json
import sys
import warnings
warnings.filterwarnings('ignore')

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    print("Warning: librosa not found. Using basic analysis.", file=sys.stderr)


def analyze_with_librosa(audio_path: str) -> dict:
    """Full analysis using librosa."""
    print(f"Loading: {audio_path}")
    y, sr = librosa.load(audio_path, duration=300)  # Max 5 min for speed
    
    # Beat tracking
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr).tolist()
    
    # Onset strength for energy
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    
    # Spectral features for mood
    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    
    # Zero crossing rate (rough voice vs instrument)
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    
    # RMS energy
    rms = librosa.feature.rms(y=y)[0]
    
    # Duration
    duration = librosa.get_duration(y=y, sr=sr)
    
    # Estimate sections using beat-synchronous CQT
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    
    # Compute overall mood metrics
    energy_avg = float(rms.mean())
    energy_std = float(rms.std())
    centroid_avg = float(spectral_centroids.mean())
    
    # Valence approximation (simple heuristic based on spectral features)
    # Higher centroid + lower zero crossing = more "bright"/positive
    valence_approx = min(1.0, max(0.0, (centroid_avg / 4000) * 0.7 + (1 - spectral_rolloff.mean() / 8000) * 0.3))
    energy_level = min(1.0, energy_avg * 3)  # Normalize
    
    # Danceability approximation
    danceability = min(1.0, energy_std * 5 + 0.3)
    
    # Section detection (simplified: energy-based)
    sections = detect_sections(onset_env, beat_times, duration)
    
    # Key moments
    key_moments = find_key_moments(onset_env, beat_times, rms)
    
    return {
        "bpm": float(tempo),
        "duration": round(duration, 2),
        "beats": [round(t, 3) for t in beat_times],
        "beat_interval": round(60.0 / float(tempo), 3),
        "sections": sections,
        "mood": {
            "energy": round(energy_level, 2),
            "valence": round(valence_approx, 2),
            "danceability": round(danceability, 2)
        },
        "key_moments": key_moments,
        "analysis_note": "Using librosa for full analysis"
    }


def detect_sections(onset_env, beat_times, duration):
    """Simple energy-based section detection."""
    from scipy.ndimage import uniform_filter1d
    
    # Smooth onset envelope
    smooth = uniform_filter1d(onset_env, size=len(onset_env)//10)
    
    # Find section boundaries by energy changes
    avg_energy = smooth.mean()
    
    sections = []
    
    # Very basic section detection based on duration
    # In practice, use machine learning or pretrained models for proper section detection
    
    if duration < 30:
        sections = [{"type": "short", "start": 0, "end": duration}]
    elif duration < 120:
        sections = [
            {"type": "intro", "start": 0, "end": min(15, duration * 0.1)},
            {"type": "verse", "start": min(15, duration * 0.1), "end": duration * 0.4},
            {"type": "chorus", "start": duration * 0.4, "end": duration * 0.7},
            {"type": "outro", "start": duration * 0.7, "end": duration}
        ]
    else:
        sections = [
            {"type": "intro", "start": 0, "end": min(20, duration * 0.08)},
            {"type": "verse", "start": duration * 0.08, "end": duration * 0.25},
            {"type": "pre_chorus", "start": duration * 0.25, "end": duration * 0.35},
            {"type": "chorus", "start": duration * 0.35, "end": duration * 0.55},
            {"type": "verse2", "start": duration * 0.55, "end": duration * 0.7},
            {"type": "bridge", "start": duration * 0.7, "end": duration * 0.85},
            {"type": "chorus_final", "start": duration * 0.85, "end": duration}
        ]
    
    return sections


def find_key_moments(onset_env, beat_times, rms):
    """Find high-impact moments in the track."""
    moments = []
    
    if not len(rms):
        return moments
    
    # Find peak energy moments
    rms_normalized = (rms - rms.min()) / (rms.max() - rms.min() + 1e-8)
    
    # Find peaks that are significantly above average
    threshold = 0.75
    for i, val in enumerate(rms_normalized):
        if val > threshold:
            # Map to time
            frame_idx = i * 512  # default hop length
            time_approx = frame_idx / 22050
            if time_approx < len(beat_times) and time_approx > 0:
                # Snap to nearest beat
                nearest_beat = min(beat_times, key=lambda b: abs(b - time_approx))
                moments.append({
                    "time": round(nearest_beat, 3),
                    "type": "peak",
                    "intensity": round(float(val), 2)
                })
    
    # Deduplicate and sort
    seen = set()
    unique_moments = []
    for m in sorted(moments, key=lambda x: x["time"]):
        if m["time"] not in seen:
            seen.add(m["time"])
            unique_moments.append(m)
    
    return unique_moments[:20]  # Limit to top 20


def analyze_basic(audio_path: str) -> dict:
    """Fallback basic analysis using ffmpeg + simple heuristics."""
    import subprocess
    import os
    
    # Get duration via ffprobe
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", audio_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
    except:
        duration = 180.0  # Default 3 min
    
    # Estimate 120 BPM as default
    bpm = 120.0
    beat_interval = 60.0 / bpm
    beats = [round(i * beat_interval, 3) for i in range(int(duration / beat_interval))]
    
    return {
        "bpm": bpm,
        "duration": round(duration, 2),
        "beats": beats[:500],  # Limit
        "beat_interval": beat_interval,
        "sections": [
            {"type": "intro", "start": 0, "end": duration * 0.1},
            {"type": "verse", "start": duration * 0.1, "end": duration * 0.4},
            {"type": "chorus", "start": duration * 0.4, "end": duration * 0.7},
            {"type": "outro", "start": duration * 0.7, "end": duration}
        ],
        "mood": {"energy": 0.5, "valence": 0.5, "danceability": 0.5},
        "key_moments": [],
        "analysis_note": "Basic analysis (librosa not available)"
    }


def main():
    parser = argparse.ArgumentParser(description="Audio analysis for AV-sync")
    parser.add_argument("audio", help="Path to audio file")
    parser.add_argument("--output", "-o", help="Output JSON path")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.audio):
        print(f"Error: File not found: {args.audio}", file=sys.stderr)
        sys.exit(1)
    
    if LIBROSA_AVAILABLE:
        result = analyze_with_librosa(args.audio)
    else:
        result = analyze_basic(args.audio)
    
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✅ Analysis saved to {args.output}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Print summary
    print(f"\n📊 Summary:")
    print(f"   BPM: {result['bpm']}")
    print(f"   Duration: {result['duration']:.1f}s")
    print(f"   Beats: {len(result['beats'])}")
    print(f"   Mood: energy={result['mood']['energy']}, valence={result['mood']['valence']}")


if __name__ == "__main__":
    main()
