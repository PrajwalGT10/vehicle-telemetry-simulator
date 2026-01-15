import os
import shutil

def delete_path(path):
    if os.path.exists(path):
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        print(f"🗑️ Deleted: {path}")
    else:
        print(f"✅ Already clean: {path}")

# 1. Remove the old generator logic (replaced by vts_core)
delete_path("generator")

# 2. Remove redundant root scripts
delete_path("verify_output.py")

# 3. Clean old output formats (we now use data/telemetry for source truth)
delete_path("data/output") 

print("\n✨ Cleanup Complete. Project structure is now lean.")