# sensor_sim.py
import random, math

class SensorSim:
    def __init__(self):
        self.t = 0.0
        self.speed = 20.0  # km/h
        self.heading = 0.0

    def step(self, dt=0.1):
        self.t += dt
        self.speed += random.uniform(-0.5,0.5)
        tilt = max(-25, min(25, math.sin(self.t/3.0)*10 + random.uniform(-2,2)))
        return {
            'timestamp': self.t,
            'speed_kmh': max(0.0, self.speed),
            'tilt_deg': tilt
        }
