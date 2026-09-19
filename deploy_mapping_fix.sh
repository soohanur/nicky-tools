#!/bin/bash
# Deploy the column-mapping fix to the VPS and restart the app.
#   - kadaster_map.py: recognises the "(Achter)naam - eigenaar 1" header spelling,
#     so the header row is found on row 2 instead of falling back to row 1
#     ("Bron adres") and leaving one useless entry in the dropdown.
#   - files.py: no longer pre-fills the mapping; every field is picked by hand.
set -e
cd "$(dirname "$0")"

scp backend/app/api/files.py                    nicky-server:/tmp/files.py.new
scp backend/app/tasks/automation_tasks.py       nicky-server:/tmp/automation_tasks.py.new
scp scraply/src/modules/kadaster_map.py         nicky-server:/tmp/kadaster_map.py.new
scp scraply/src/modules/browser_automation.py   nicky-server:/tmp/browser_automation.py.new
scp scraply/src/modules/tabular_io.py           nicky-server:/tmp/tabular_io.py.new

ssh nicky-server 'set -e
TS=$(date +%Y%m%d-%H%M%S)
cd /var/www/datainfo
for f in backend/app/api/files.py backend/app/tasks/automation_tasks.py \
         scraply/src/modules/kadaster_map.py scraply/src/modules/browser_automation.py \
         scraply/src/modules/tabular_io.py; do
  cp "$f" "$f.bak.$TS"
done
cp /tmp/files.py.new              backend/app/api/files.py
cp /tmp/automation_tasks.py.new   backend/app/tasks/automation_tasks.py
cp /tmp/kadaster_map.py.new       scraply/src/modules/kadaster_map.py
cp /tmp/browser_automation.py.new scraply/src/modules/browser_automation.py
cp /tmp/tabular_io.py.new         scraply/src/modules/tabular_io.py
chown datainfo:www-data backend/app/api/files.py backend/app/tasks/automation_tasks.py \
      scraply/src/modules/kadaster_map.py scraply/src/modules/browser_automation.py \
      scraply/src/modules/tabular_io.py
rm -f /tmp/files.py.new /tmp/automation_tasks.py.new /tmp/kadaster_map.py.new \
      /tmp/browser_automation.py.new /tmp/tabular_io.py.new
rm -rf scraply/src/modules/__pycache__ backend/app/api/__pycache__ backend/app/tasks/__pycache__
echo "installed, backups tagged $TS"
systemctl restart datainfo-api datainfo-celery
sleep 8
systemctl is-active datainfo-api datainfo-celery
cd /var/www/datainfo/backend && PYTHONPATH=/var/www/datainfo/backend:/var/www/datainfo/scraply \
  ./venv/bin/python -c "
from src.modules.kadaster_map import detect_any
import glob
f = sorted(glob.glob(\"/var/www/datainfo/scraply/csv_files/input/*achterhoek*.xlsx\"))[-1]
d = detect_any(f)
print(\"header_row:\", d[\"header_row\"], \"| headers:\", len([h for h in d[\"headers\"] if h]), \"| sheet:\", repr(d[\"sheet\"]))
"
'
echo
echo "Done. Reload the app, re-open the mapping screen: the dropdown should list all 105 columns."
