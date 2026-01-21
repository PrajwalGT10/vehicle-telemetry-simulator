import sqlite3
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import json
import datetime
import os

from vts_core.utils import decimal_to_nmea, get_hemisphere

class SimulationStore:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize optional Metadata DB (Preserving structure)
        self.db_path = self.base_dir / "simulation_metadata.db"
        self._init_db()
        
        # Main Telemetry storage (Parquet)
        self.telemetry_dir = self.base_dir / "telemetry"
        self.telemetry_dir.mkdir(exist_ok=True)
        
        # Legacy/Custom Text Log storage
        self.legacy_dir = self.base_dir / "output" / "tracker"
        self.legacy_dir.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        """Creates metadata tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                imei TEXT PRIMARY KEY,
                config_json TEXT,
                zone_id TEXT
            )
        """)
        conn.commit()
        conn.close()

    def write_telemetry(self, imei: str, date_str: str, records: list, vehicle_name: str):
        """
        Writes simulation data to:
        1. Parquet (Efficient binary format for maps/analytics)
        2. Text Log (data/tracker/{VehicleName}/{Year}/{Month}/{Date}.txt)
        """
        if not records:
            return

        # --- 1. Setup File Paths ---
        year, month, _ = date_str.split("-")
        
        # Parquet Path: data/telemetry/year=2023/month=01/
        parquet_dir = self.telemetry_dir / f"year={year}" / f"month={month}"
        parquet_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = parquet_dir / f"{imei}_{date_str}.parquet"
        
        # Text Log Path: data/tracker/{Vehicle Name}/{Year}/{Month}/
        # User Req: "data - Vehicle Name - Year - Month"
        # base_dir is "data", so we put "tracker" inside.
        tracker_dir = self.base_dir / "tracker" / vehicle_name / year / month
        tracker_dir.mkdir(parents=True, exist_ok=True)
        log_path = tracker_dir / f"{date_str}.txt"

        # --- 2. Write Parquet (Source of Truth) ---
        df = pd.DataFrame(records)
        # Ensure timestamp is datetime for parquet efficiency
        if not df.empty and isinstance(df.iloc[0]['timestamp'], str):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
        df.to_parquet(parquet_path, index=False)

        # --- 3. Write Custom Text Log ---
        # Format: imei:868...,tracker,140...,,F,060722.000,A,1255.4187,N,07733.1281,E,0.81,121.83;
        
        with open(log_path, "w") as f:
            for r in records:
                ts = r["timestamp"]
                # Handle timestamp types (string vs datetime object)
                if isinstance(ts, str):
                    try:
                        ts = datetime.datetime.fromisoformat(ts)
                    except ValueError:
                        # Fallback if unknown format
                        continue
                
                # A. Generate Packet Fields
                # Packet ID: YYMMDDHHMMSS (Unique based on time)
                packet_id = ts.strftime("%y%m%d%H%M%S")
                
                # Time: HHMMSS.000
                time_str = ts.strftime("%H%M%S.000")
                
                # Lat/Lon NMEA conversion
                lat = r["lat"]
                lon = r["lon"]
                lat_nmea = decimal_to_nmea(lat, is_longitude=False)
                lat_dir = get_hemisphere(lat, is_lon=False)
                
                lon_nmea = decimal_to_nmea(lon, is_longitude=True)
                lon_dir = get_hemisphere(lon, is_lon=True)
                
                # Speed: Value is already in Knots from Agent
                speed_knots = r.get("speed", 0.0)
                # speed_kmh = r.get("speed", 0.0)
                # speed_knots = speed_kmh * 0.539957
                
                # Heading
                heading = r.get("heading", 0.0)

                # B. Build Line
                # imei:868...,tracker,packet_id,,F,time,A,lat_nmea,lat_dir,lon_nmea,lon_dir,speed,heading;
                line = (
                    f"imei:{imei},tracker,{packet_id},,F,{time_str},A,"
                    f"{lat_nmea},{lat_dir},{lon_nmea},{lon_dir},"
                    f"{speed_knots:.2f},{heading:.2f};"
                )
                
                f.write(line + "\n")