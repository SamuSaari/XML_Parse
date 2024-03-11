import json
from influxdb_client import InfluxDBClient
import requests
import os
from datetime import datetime
import pytz

# InfluxDB settings
influxdb_url = os.environ.get("INFLUX_URL")
influxdb_token = os.environ.get("INFLUX_TOKEN")
influxdb_org = os.environ.get("INFLUX_ORG")
influxdb_bucket = os.environ.get("INFLUX_BUCKET")

# Pushover settings
pushover_token = os.environ.get("PO_TOKEN")
pushover_user = os.environ.get("PO_USER")

reference_file_path = 'reference_values.json'

# Thresholds
lower_threshold = -0.002
upper_threshold = 0.002

def load_reference_values():
    try:
        with open(reference_file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def send_pushover_notification(message):
    requests.post("https://api.pushover.net/1/messages.json", data={
        "token": pushover_token,
        "user": pushover_user,
        "message": message
    })

def determine_location(piste):
    if piste.startswith("8"):
        return "Gummeruksenkatu"
    elif piste.startswith("48"):
        return "Ponttiseinä"
    elif piste.startswith("4"):
        return "Kilpisenkatu"
    return "Unknown location"

def is_outside_threshold(value, reference_value):
    difference = value - reference_value
    return difference < lower_threshold or difference > upper_threshold

def query_and_alert():
    reference_values = load_reference_values()
    alerts_triggered = False

    # Define Helsinki timezone
    helsinki_timezone = pytz.timezone('Europe/Helsinki')

    with InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org) as client:
        query = f'''
        from(bucket: "{influxdb_bucket}")
        |> range(start: -2h)
        |> filter(fn: (r) => r._measurement == "monitorointi" and (r._field == "DeltaX" or r._field == "DeltaY" or r._field == "DeltaZ"))
        |> sort(columns: ["_time"], desc: true)
        '''
        result = client.query_api().query(org=influxdb_org, query=query)

        for table in result:
            for record in table.records:
                piste = record.values['Piste']
                field_name = record.get_field()
                value = record.get_value()
                if piste in reference_values:
                    reference_point_info = reference_values[piste]
                    reference_value = reference_point_info.get(field_name, 0)
                    reference_timestamp = reference_point_info.get('timestamp', 'N/A')

                    # Define field_name_display outside the if condition
                    delta_mapping = {
                        'DeltaX': 'ΔX',
                        'DeltaY': 'ΔY',
                        'DeltaZ': 'ΔZ',
                    }
                    field_name_display = delta_mapping.get(field_name, field_name)  # Ensure it has a value regardless of the threshold check

                    # Parse and convert the reference timestamp to Helsinki timezone
                    if reference_timestamp != 'N/A':
                        reference_timestamp_datetime = datetime.fromisoformat(reference_timestamp.rstrip('Z')).replace(tzinfo=pytz.utc)
                        reference_timestamp_helsinki = reference_timestamp_datetime.astimezone(helsinki_timezone)
                        formatted_reference_timestamp = reference_timestamp_helsinki.strftime("%d-%m-%Y %H:%M:%S")
                    else:
                        formatted_reference_timestamp = 'N/A'

                    # Convert current UTC time to Helsinki timezone
                    current_timestamp_helsinki = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(helsinki_timezone)
                    current_timestamp_formatted = current_timestamp_helsinki.strftime("%d-%m-%Y %H:%M:%S")
                    
                    if is_outside_threshold(value, reference_value):
                        alerts_triggered = True
                        message = (f"Mittaus: {reference_point_info['session']}\n"
                                f"Mittapiste: {piste} ({determine_location(piste)})\n"
                                f"Akseli: {field_name_display}\n"
                                f"Arvo: {value:.3f}\n"
                                f"Vertailuarvo: {reference_value:.3f}\n"
                                f"Vertailuarvo päivitetty: {formatted_reference_timestamp}\n"
                                f"Aika: {current_timestamp_formatted}")
                        send_pushover_notification(message)

        if not alerts_triggered:
            print("Arvot Ok")

if __name__ == "__main__":
    query_and_alert()