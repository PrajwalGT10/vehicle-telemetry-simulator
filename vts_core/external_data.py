import pandas as pd
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

class ExternalLogProvider:
    _shared_df = None
    _source_path = None

    def __init__(self, path: str = None):
        if path is None:
            # Default to the known path if not provided
            path = os.path.join("data", "external", "VTS Consolidated Report - Final Dataset.csv")
        self.path = path
        self._load_data()

    def _load_data(self):
        # Cache data at class level to share across instances (if logical)
        # Note: If running in multiprocessing, this only caches within the process.
        if ExternalLogProvider._source_path == self.path and ExternalLogProvider._shared_df is not None:
            self.df = ExternalLogProvider._shared_df
            return

        if not os.path.exists(self.path):
            logger.warning(f"External log file not found: {self.path}")
            self.df = pd.DataFrame()
            return

        try:
            logger.info(f"Loading external logs from {self.path}...")
            # CSV Format: Vehicle Description, Device-ID ,Date ,Time ,OdometerKm,Lat/Lon ,...
            # Handling potential whitespace in headers during read isn't standard in read_csv, so we clean after.
            df = pd.read_csv(self.path)
            
            # Clean headers
            df.columns = [c.strip() for c in df.columns]
            
            # Required columns validation
            required = ['Vehicle Description', 'Date', 'Time', 'Lat/Lon']
            if not all(col in df.columns for col in required):
                logger.error(f"Missing required columns in CSV. Found: {df.columns}")
                self.df = pd.DataFrame()
                return

            # Combine Date and Time into a single datetime object for filtering
            # Date format in preview: 1/1/2014, 5/4/2022 (d/m/Y)
            # Time format: 13:30:07
            
            # Create a 'timestamp' column
            # fast parsing
            df['timestamp'] = pd.to_datetime(
                df['Date'] + ' ' + df['Time'], 
                format='%d/%m/%Y %H:%M:%S', 
                errors='coerce'
            )
            
            # Create a normalized vehicle name column for querying
            df['vehicle_key'] = df['Vehicle Description'].str.strip().str.lower()
            
            # --- DATE FILTRATION (May 2021 to April 2024) ---
            start_date = pd.Timestamp("2021-05-01")
            end_date = pd.Timestamp("2024-04-30")
            df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
            
            # Drop invalid rows
            df = df.dropna(subset=['timestamp', 'Lat/Lon'])
            
            # Pre-calculate Lat/Lon floats to avoid doing it in the loop
            # Lat/Lon format: "12.9828/77.5851" or empty
            def split_lat_lon(x):
                try:
                    parts = str(x).split('/')
                    return float(parts[0]), float(parts[1])
                except:
                    return None, None

            df[['lat', 'lon']] = df['Lat/Lon'].apply(lambda x: pd.Series(split_lat_lon(x)))
            df = df.dropna(subset=['lat', 'lon'])
            
            # Sort by timestamp to ensure chronological order for querying
            df = df.sort_values(by=['vehicle_key', 'timestamp'])
            
            self.df = df
            ExternalLogProvider._shared_df = df
            ExternalLogProvider._source_path = self.path
            logger.info(f"Loaded {len(df)} external log entries.")
            
        except Exception as e:
            logger.error(f"Failed to load external logs: {e}")
            self.df = pd.DataFrame()

    def get_events(self, vehicle_name: str, date_str: str):
        """
        Returns sorted list of dicts: {'timestamp': datetime, 'lat': float, 'lon': float}
        for the specific vehicle and date.
        """
        if self.df.empty:
            return []

        # Filter by vehicle
        v_key = vehicle_name.strip().lower()
        
        # Optimize: Filter range
        # date_str is YYYY-MM-DD
        day_start = pd.Timestamp(date_str)
        day_end = day_start + pd.Timedelta(days=1)
        
        # Boolean indexing
        mask = (
            (self.df['vehicle_key'] == v_key) & 
            (self.df['timestamp'] >= day_start) & 
            (self.df['timestamp'] < day_end)
        )
        
        rows = self.df.loc[mask]
        
        if rows.empty:
            return []
            
        events = []
        for _, row in rows.iterrows():
            events.append({
                "timestamp": row['timestamp'].to_pydatetime(),
                "lat": row['lat'],
                "lon": row['lon'],
                "speed": 0.0, # Checkpoints imply being at a spot, speed is derivative
                "heading": 0.0
            })
            
        return events
