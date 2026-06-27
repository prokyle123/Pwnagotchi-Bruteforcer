# Release Verification

Before packaging, the release source was checked with:

```bash
python3 -m py_compile Bruteforcer.py
python3 -m py_compile extras/fan_control_telemetry.py
```

A local, dependency-light Mutator Lab smoke test also completed successfully. This does not replace testing on a real Pwnagotchi image with your active Pwnagotchi, Aircrack-ng, fan hardware, and configuration.
