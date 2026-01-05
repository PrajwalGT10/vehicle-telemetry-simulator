from vts_core.store import SimulationStore

def main():
    store = SimulationStore(base_dir="data")
    
    # We ask for the data we just generated (2023-01-02)
    # Note: Replace '864895033188200' if your config used a different IMEI
    imei = "864895033188200" 
    date = "2023-01-02"
    
    print(f"📠 Extracting Legacy Log for {imei} on {date}...")
    
    try:
        output_path = store.export_legacy_log(
            vehicle_imei=imei,
            date=date,
            device_id="DEV_TEST"
        )
        print(f"✅ Log Generated: {output_path}")
        
        # Print first 3 lines to prove format
        print("\n--- File Preview ---")
        with open(output_path, "r") as f:
            for _ in range(3):
                print(f.readline().strip())
                
    except FileNotFoundError:
        print("❌ Error: Parquet data not found. Did the simulation save correctly?")

if __name__ == "__main__":
    main()