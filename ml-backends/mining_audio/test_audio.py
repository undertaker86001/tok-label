import numpy as np
import soundfile as sf
import librosa
import os

# Create a simple test tone
sr = 25000
t = np.linspace(0, 1, sr)
y = np.sin(2 * np.pi * 440 * t)
sf.write('test_audio.wav', y, sr)
print('Test audio file created')

# Test our feature extractor
from model import AudioFeatureExtractor
extractor = AudioFeatureExtractor()
features = extractor.extract_features('test_audio.wav')
print('Features extracted:', features is not None)
if features is not None:
    print('Feature shape:', features.shape)
    print('Feature values:', features[:10])  # First 10 values
else:
    print('Feature extraction failed')