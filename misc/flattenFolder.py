import os
import shutil

ROOT = "./z_gannet_seatrack/"

for dirpath, dirnames, filenames in os.walk(ROOT):
    # Skip the top-level directory itself
    if dirpath == ROOT:
        continue

    for filename in filenames:
        src_path = os.path.join(dirpath, filename)
        dst_path = os.path.join(ROOT, filename)

        # Handle filename collisions
        if os.path.exists(dst_path):
            name, ext = os.path.splitext(filename)
            counter = 1
            while True:
                new_name = f"{name}_{counter}{ext}"
                dst_path = os.path.join(ROOT, new_name)
                if not os.path.exists(dst_path):
                    break
                counter += 1

        shutil.copy2(src_path, dst_path)

