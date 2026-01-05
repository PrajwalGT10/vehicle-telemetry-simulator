import sqlite3
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import json
import datetime
import os

from vts_core.utils import decimal_to_ddmm_mmmm, format_time_hhmmss_ms

class SimulationStore:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "simulation_metadata.db"
        self._init_db()
        self.telemetry_dir = self.base_dir / "telemetry"
        self.telemetry_dir.mkdir(exist_ok=True)

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                imei TEXT PRIMARY KEY,
                config_json TEXT,
                zone_id TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_plans (
                plan_id TEXT PRIMARY KEY,
                date TEXT,
                vehicle_imei TEXT,
                route_id TEXT,
                start_time TEXT,
                meta_json TEXT,
                FOREIGN KEY(vehicle_imei) REFERENCES vehicles(imei)
            )
        """)
        conn.commit()
        conn.close()

    def register_vehicle(self, vehicle_config: Dict[str, Any]):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO vehicles (imei, config_json, zone_id) VALUES (?, ?, ?)",
            (vehicle_config['imei'], json.dumps(vehicle_config), vehicle_config.get('zone_id'))
        )
        conn.commit()
        conn.close()

    def write_telemetry(self, vehicle_imei: str, date: str, records: List[Dict]):
        if not records: return
        df = pd.DataFrame(records)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['vehicle_imei'] = vehicle_imei
        
        dt = datetime.datetime.strptime(date, "%Y-%m-%d")
        year = str(dt.year)
        month = f"{dt.month:02d}"
        output_dir = self.telemetry_dir / f"year={year}" / f"month={month}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = output_dir / f"{vehicle_imei}_{date}.parquet"
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            df = pd.concat([existing_df, df])
        
        df.to_parquet(file_path, engine='pyarrow', index=False)
        return str(file_path)

    def export_legacy_log(self, vehicle_imei: str, date: str, device_id: str, output_path: str = None) -> str:
        """
        Export Format (FIXED):
        imei:868...,tracker,140...,,F,060722.000,A,1255.4187,N,07733.1281,E,0.81,121.83;
        """
        dt = datetime.datetime.strptime(date, "%Y-%m-%d")
        year = str(dt.year)
        month = f"{dt.month:02d}"
        parquet_path = self.telemetry_dir / f"year={year}" / f"month={month}" / f"{vehicle_imei}_{date}.parquet"
        
        if not parquet_path.exists():
            raise FileNotFoundError(f"No telemetry data found for {vehicle_imei} on {date}")

        df = pd.read_parquet(parquet_path)
        df = df.sort_values('timestamp')
        
        lines = []
        for _, row in df.iterrows():
            ts_str = format_time_hhmmss_ms(row['timestamp'])
            lat_str = decimal_to_ddmm_mmmm(row['lat'], is_longitude=False)
            lon_str = decimal_to_ddmm_mmmm(row['lon'], is_longitude=True)
            speed = f"{row['speed']:.2f}"
            heading = f"{row['heading']:.2f}"
            
            # --- FIX: Removed '(' and ')' ---
            line = (
                f"imei:{vehicle_imei},tracker,{device_id},,F,{ts_str},"
                f"A,{lat_str},N,{lon_str},E,{speed},{heading};"
            )
            lines.append(line)
            
        if output_path is None:
            output_path = str(self.base_dir / f"{vehicle_imei}_{date}.txt")
            
        with open(output_path, "w") as f:
            f.write("\n".join(lines))
            
        return output_path