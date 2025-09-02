import json
import subprocess
from run import run

with open("data/test/test_2.json", "r") as f:
    test_data = json.load(f)

test_requests = [t["description"] for t in test_data]


for data in test_data[:1]:
    request = data["description"]
    id = data["use_case_id"]

    try:
        run(
            db="data/logistics.db",
            schema="data/db.sql",
            request=request,
            id=id,
            description="data/description.txt",
            examples="data/examples.sql",
        )
    except Exception as e:
        print(f"Executed request `{id}` failed. Error: {e}")
