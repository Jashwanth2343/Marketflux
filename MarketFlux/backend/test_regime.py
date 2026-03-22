import sys
import asyncio
from vnext.adapter_helpers import classify_regime

def test():
    inputs = {
        'vix': 26.78,
        'sp500_change_percent': -1.51,
        'nasdaq_change_percent': -2.0,
        'tlt_change_percent': 0.5,
        'unemployment_rate': 4.1,
        'ten_two_spread': 0.2
    }
    regime = classify_regime(inputs)
    print(f"\n[REGIME TEST RESULT] => {regime}\n")

if __name__ == "__main__":
    test()
