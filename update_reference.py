import json
import datetime
import os
from influxdb_client import InfluxDBClient

# Configuration
influxdb_url = os.environ.get("INFLUX_URL")
influxdb_token = os.environ.get("INFLUX_TOKEN")
influxdb_org = os.environ.get("INFLUX_ORG")
influxdb_bucket = os.environ.get("INFLUX_BUCKET")

reference_file_path = 'reference_values.json'

# Initialize InfluxDB client
client = InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)

def load_reference_values():
    try:
        with open(reference_file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_reference_values(reference_values):
    with open(reference_file_path, 'w') as file:
        json.dump(reference_values, file, indent=4)

def fetch_latest_point_values():
    query = f'''
    from(bucket: "{influxdb_bucket}")
    |> range(start: -2h)
    |> filter(fn: (r) => r._measurement == "monitorointi")
    |> filter(fn: (r) => r._field == "DeltaX" or r._field == "DeltaY" or r._field == "DeltaZ")
    |> last()
    '''
    result = client.query_api().query(org=influxdb_org, query=query)
    return result

def update_reference_values():
    reference_values = load_reference_values()
    results = fetch_latest_point_values()

    for table in results:
        for record in table.records:
            point = record.values['Piste']
            if point not in reference_values:
                reference_values[point] = {}
            reference_values[point]['session'] = record.values['Istunto']
            reference_values[point]['timestamp'] = datetime.datetime.utcnow().isoformat() + 'Z'  # Use UTC time for consistency
            for field in ['DeltaX', 'DeltaY', 'DeltaZ']:
                if field == record.get_field():
                    reference_values[point][field] = record.get_value()

    save_reference_values(reference_values)

if __name__ == "__main__":
    update_reference_values()