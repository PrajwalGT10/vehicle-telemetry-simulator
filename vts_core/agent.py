import random
from typing import List, Optional, Tuple, Dict
from shapely.geometry import LineString
from datetime import datetime, timedelta

from vts_core.config import VehicleConfig
from vts_core.store import SimulationStore

class VehicleAgent:
    def __init__(self, config: VehicleConfig, store: SimulationStore):
        self.config = config
        self.store = store
        
        # State
        self.current_time = None
        self.current_location: Tuple[float, float] = (0.0, 0.0)
        self.current_heading: float = 0.0
        self.current_speed: float = 0.0
        
        self.is_active: bool = False
        self.state: str = "OFF_SHIFT"
        
        # Route & Plan
        self.path_geometry: Optional[LineString] = None
        self.path_progress_meters: float = 0.0
        self.scheduled_stops: List[Dict] = []
        self.current_stop_end_time: Optional[datetime] = None
        
        # Operational Window
        self.shift_start_hour = 9
        self.shift_end_hour = 18
        
        self.telemetry_buffer: List[dict] = []

    def start_24h_cycle(self, date_str: str, path_geometry: LineString, 
                       shift_start: int, shift_end: int, stops: List[Dict] = []):
        self.current_time = datetime.strptime(f"{date_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
        self.path_geometry = path_geometry
        self.scheduled_stops = sorted(stops, key=lambda x: x['at_meter'])
        self.shift_start_hour = shift_start
        self.shift_end_hour = shift_end
        
        start_pt = path_geometry.coords[0]
        self.current_location = (start_pt[1], start_pt[0])
        self.path_progress_meters = 0.0
        
        self.state = "OFF_SHIFT"
        self.is_active = True
        self.telemetry_buffer = []

    def tick(self):
        if not self.is_active: return

        # 1. Increment Time (25 +/- 5s)
        dt_seconds = 25 + random.randint(-5, 5)
        self.current_time += timedelta(seconds=dt_seconds)
        
        # 2. Check End of Day
        if self.current_time.hour >= 23 and self.current_time.minute >= 59:
            self.is_active = False

        # 3. State Machine
        hour = self.current_time.hour
        
        if hour < self.shift_start_hour:
            self.state = "OFF_SHIFT"
            self.current_speed = 0.0
            start_pt = self.path_geometry.coords[0]
            self.current_location = (start_pt[1], start_pt[0])
            
        elif self.shift_start_hour <= hour < self.shift_end_hour:
            if self.state == "OFF_SHIFT":
                print(f"   ☀️ Shift Start: {self.current_time.time()}")
                self.state = "DRIVING"
            
            if self.state == "ROUTE_FINISHED":
                self.current_speed = 0.0
            elif self.state == "DWELLING":
                self._handle_dwelling()
            elif self.state == "DRIVING":
                self._handle_driving(dt_seconds)
                
        else:
            if self.state != "OFF_SHIFT":
                self.state = "OFF_SHIFT"
            self.current_speed = 0.0
            
        self._record_telemetry()

    def _handle_dwelling(self):
        self.current_speed = 0.0
        if self.current_time >= self.current_stop_end_time:
            print(f"   🔄 Resuming from stop at {self.current_time.time()}")
            self.state = "DRIVING"
            self.current_stop_end_time = None

    def _handle_driving(self, dt_seconds: int):
        # --- TRAFFIC LOGIC ---
        # Simulate heavy traffic: Only use 15-55% of top speed
        traffic_congestion = random.uniform(0.15, 0.55)
        
        # 10% chance of a clear road (up to 80% speed)
        if random.random() < 0.1:
            traffic_congestion = random.uniform(0.6, 0.8)

        target_speed_knots = self.config.max_speed_knots * traffic_congestion
        
        # Add slight jitter so speed isn't robotic
        target_speed_knots += random.uniform(-1.0, 1.0)
        if target_speed_knots < 0: target_speed_knots = 0.0
        
        speed_mps = target_speed_knots * 0.514444
        move_dist = speed_mps * dt_seconds
        
        # --- STOP LOGIC ---
        next_stop = self.scheduled_stops[0] if self.scheduled_stops else None
        if next_stop:
            dist_to_stop = next_stop['at_meter'] - self.path_progress_meters
            if 0 < dist_to_stop <= move_dist:
                self.path_progress_meters = next_stop['at_meter']
                self.current_speed = 0.0
                self.state = "DWELLING"
                
                duration = random.randint(next_stop.get('duration_min', 15), next_stop.get('duration_max', 45))
                self.current_stop_end_time = self.current_time + timedelta(minutes=duration)
                self.scheduled_stops.pop(0)
                print(f"   🛑 Stop at {self.current_time.time()} for {duration} min.")
                self._update_position_on_path()
                return

        # --- MOVE ---
        self.path_progress_meters += move_dist
        self.current_speed = target_speed_knots
        
        # Check End of Route
        path_len_meters = self.path_geometry.length * 111139.0
        if self.path_progress_meters >= path_len_meters:
            self.path_progress_meters = path_len_meters
            self.state = "ROUTE_FINISHED"
            self.current_speed = 0.0
            print(f"   🏁 Route Finished at {self.current_time.time()}. Waiting for shift end.")
            
        self._update_position_on_path()

    def _update_position_on_path(self):
        distance_deg = self.path_progress_meters / 111139.0
        if distance_deg > self.path_geometry.length:
            distance_deg = self.path_geometry.length

        pt = self.path_geometry.interpolate(distance_deg)
        self.current_location = (pt.y, pt.x)
        
        next_dist = distance_deg + (5.0 / 111139.0)
        pt_next = self.path_geometry.interpolate(next_dist)
        from vts_core.geo import calculate_bearing_shapely
        self.current_heading = calculate_bearing_shapely(pt, pt_next)

    def _record_telemetry(self):
        # User Requirement: Only log data during shift timings
        if self.state == "OFF_SHIFT":
            return

        rec = {
            "timestamp": self.current_time,
            "lat": self.current_location[0],
            "lon": self.current_location[1],
            "speed": self.current_speed,
            "heading": self.current_heading,
            "device_id": self.config.device_id
        }
        self.telemetry_buffer.append(rec)

    def flush_memory(self):
        if not self.telemetry_buffer: return
        
        # Sort buffer by timestamp to ensure external events are in order
        self.telemetry_buffer.sort(key=lambda x: x['timestamp'])
        
        date_str = self.telemetry_buffer[0]['timestamp'].strftime("%Y-%m-%d")
        self.store.write_telemetry(self.config.imei, date_str, self.telemetry_buffer, vehicle_name=self.config.name)
        self.telemetry_buffer = []

    def inject_external_logs(self, events: List[Dict]):
        """
        Injects fixed points from external sources (e.g., Google Sheets).
        These bypass the 'Shift Only' filter.
        """
        for e in events:
            rec = {
                "timestamp": e['timestamp'],
                "lat": e['lat'],
                "lon": e['lon'],
                "speed": e.get('speed', 0.0),
                "heading": e.get('heading', 0.0),
                "device_id": self.config.device_id
            }
            self.telemetry_buffer.append(rec)
            print(f"   💉 Injected External Log: {rec['timestamp'].time()}")