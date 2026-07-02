"""
Test prediction locally without running FastAPI server.
Usage: python test_prediction_local.py
"""

import numpy as np
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.model_loader import load_models
from src.services.inference import run_inference

def test_prediction():
    """Test inference with dummy battery readings (30 timestep, 3 features)."""

    print("=" * 60)
    print("🔧 Loading models...")
    print("=" * 60)

    try:
        load_models()
        print("✅ Models loaded successfully\n")
    except Exception as e:
        print(f"❌ Failed to load models: {e}")
        print("\n💡 Make sure you have:")
        print("   1. models/weights/scaler.pkl")
        print("   2. models/weights/soh_lstm_v*.pth")
        print("   3. models/weights/isolation_forest_v*.pkl")
        print("\n   Run: python scripts/preprocess.py && python scripts/train.py")
        return

    # Dummy data: 30 timesteps × 3 features [voltage, current, temperature]
    # Realistic ranges: V [2.5-4.2V], I [0-2A], T [15-45°C]
    np.random.seed(42)
    readings = np.random.uniform(
        low=[2.8, 0.0, 15],
        high=[4.1, 1.5, 40],
        size=(30, 3)
    ).tolist()

    print("=" * 60)
    print("🔮 Running inference on dummy readings...")
    print("=" * 60)
    print(f"Input shape: 30 timesteps × 3 features")
    print(f"Feature ranges: V [2.5-4.2], I [0-2], T [15-45]\n")

    try:
        result = run_inference(readings)

        print("✅ Inference SUCCESS!\n")
        print(f"SOH: {result['soh_percent']:.2f}%")
        print(f"Classification: {result['classification']}")
        print(f"Confidence: {result['confidence']:.4f}")
        print(f"Inference latency: {result['inference_ms']:.2f}ms")
        print(f"Anomaly score: {result.get('anomaly_score', 'N/A')}")

        if 'rul_cycles_estimate' in result:
            print(f"RUL estimate: {result['rul_cycles_estimate']} cycles")

        print(f"\n📊 Feature Summary:")
        for feat, stats in result.get('feature_summary', {}).items():
            print(f"   {feat}: mean={stats['mean']}, min={stats['min']}, max={stats['max']}")

        if result.get('warnings'):
            print(f"\n⚠️  Warnings: {result['warnings']}")

    except Exception as e:
        print(f"❌ Inference failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_prediction()
