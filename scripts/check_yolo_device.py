"""Check YOLO device usage and CUDA availability."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from ultralytics import YOLO

print("=" * 80)
print("YOLO DEVICE CHECK")
print("=" * 80)
print()

# Check PyTorch CUDA
print(f"PyTorch CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA device count: {torch.cuda.device_count()}")
    print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
else:
    print("CUDA device: None (CPU only)")

print()

# Load YOLO model
print("Loading YOLO11n-pose...")
model = YOLO('yolo11n-pose.pt')
print(f"Model device: {model.device}")
print()

# Run single prediction to see what device is actually used
print("Running single prediction...")
results = model.predict('test_videos/two_person_crossing.mp4', 
                       stream=True, verbose=False)
next(results)
print(f"Prediction completed on device: {model.device}")
print()

# Check if model can be forced to CPU
print("Testing forced CPU mode...")
model_cpu = YOLO('yolo11n-pose.pt')
results_cpu = model_cpu.predict('test_videos/two_person_crossing.mp4',
                                device='cpu', stream=True, verbose=False)
next(results_cpu)
print(f"Forced CPU device: {model_cpu.device}")
