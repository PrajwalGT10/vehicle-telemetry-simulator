import pandas as pd
from datetime import datetime
import os

class ExternalLogProvider:
    _shared_df = None
    _source_path = None

    def __init__(self, path: str):
        self.path = path
        self._load_data()

    def _load_data(self):
        # Simple caching to avoid reloading 100k lines per vehicle per day if feasible
        # In multiprocessing, each process has its own memory, so this caches per process.
        if ExternalLogProvider._source_path == self.path and ExternalLogProvider._shared_df is not None:
            self.df = ExternalLogProvider._shared_df
            return

        if not os.path.exists(self.path):
            self.df = pd.DataFrame()
            return

        try:
            # Assume Tab-separated based on user copy-paste
            # Columns: Vehicle_Name, Vehicle_ID, Date, Time, Odometer?, Lat_Lon, Location, Empty, Duration
            df = pd.read_csv(self.path, sep='\t')
            
            # Normalize Date column for querying (DD/MM/YYYY -> YYYY-MM-DD or keep as string)
            # User Input: 26/01/2023. Simulator uses YYYY-MM-DD.
            # Let's standardize to YYYY-MM-DD string for fast filtering
            
            # Function to parse date: 26/01/2023 -> 2023-01-26
            def parse_date(d):
                try:
                    return datetime.strptime(d, "%d/%m/%Y").strftime("%Y-%m-%d")
                except:
                    return d
            
            df['std_date'] = df['Date'].apply(parse_date)
            
            self.df = df
            ExternalLogProvider._shared_df = df
            ExternalLogProvider._source_path = self.path
            
        except Exception as e:
            print(f"⚠️ Failed to load external logs: {e}")
            self.df = pd.DataFrame()

    def get_events(self, vehicle_name: str, date_str: str):
        """
        Returns list of dicts: {'timestamp': datetime, 'lat': float, 'lon': float}
        """
        if self.df.empty:
            return []

        # Filter
        mask = (self.df['Vehicle_Name'] == vehicle_name) & (self.df['std_date'] == date_str)
        rows = self.df[mask]
        
        events = []
        for _, row in rows.iterrows():
            try:
                # Parse Timestamp
                # Time: 23:58:37
                time_str = row['Time']
                full_ts_str = f"{date_str} {time_str}"
                ts = datetime.strptime(full_ts_str, "%Y-%m-%d %H:%M:%S")
                
                # Parse Lat/Lon
                # Lat_Lon: 12.9581/77.6124
                lat_str, lon_str = str(row['Lat_Lon']).split('/')
                lat = float(lat_str)
                lon = float(lon_str)
                
                events.append({
                    "timestamp": ts,
                    "lat": lat,
                    "lon": lon,
                    "speed": 0.0, # detailed report "points" usually imply stationary or snapshot
                    "heading": 0.0
                })
            except Exception as e:
                # print(f"Skipping malformed row: {row} - {e}")
                continue
                
        return events
