import imaplib
import email
import io
import os
import tempfile
import xml.etree.ElementTree as ET
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
from urllib3.exceptions import ReadTimeoutError
import pytz
import logging

# Gmail credentials
username = os.environ.get("MAIL_USER") 
app_password = os.environ.get("APP_PASSWORD")  

# InfluxDB credentials
influxdb_url = os.environ.get("INFLUX_URL")
influxdb_token = os.environ.get("INFLUX_TOKEN")
influxdb_org = os.environ.get("INFLUX_ORG")
influxdb_bucket = os.environ.get("INFLUX_BUCKET")
measurement_name = 'monitorointi'

# Initialize IMAP and login
imap = imaplib.IMAP4_SSL('imap.gmail.com')
imap.login(username, app_password)
imap.select('INBOX')

# Initialize InfluxDB client
client = InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)
write_api = client.write_api(write_options=SYNCHRONOUS)

# Define the namespace map for XML parsing
namespaces = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}

# Threshold for excluding measurement
threshold = 0.100

# Timezone of data
local_tz = pytz.timezone("Europe/Helsinki")  # Replace with the correct time zone

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Backup for float conversion. Handles situations where conversion might fail by returning None
def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

# Function to check if data point already exists
def data_point_exists(client, timestamp, piste_name):
    try:
        query = f'from(bucket: "{influxdb_bucket}") |> range(start: -1d) |> filter(fn: (r) => r._measurement == "monitorointi" and r.piste == "{piste_name}" and r._time == "{timestamp}")'
        result = client.query_api().query(query)
        return len(result) > 0
    except ReadTimeoutError:
        logging.error(f"Timeout occurred while checking data point for {piste_name} at {timestamp}")
        return False  # or handle as appropriate

# Function to write data to InfluxDB
def write_data_to_influx(client, write_api, data_points, influxdb_bucket):
    for data_point in data_points:
        local_timestamp = datetime.strptime(data_point['Pvm'], '%d-%m-%Y %H.%M.%S')
        utc_timestamp = local_tz.localize(local_timestamp).astimezone(pytz.utc)

        if not data_point_exists(client, utc_timestamp.isoformat(), data_point['Piste']):
            point = Point(measurement_name)\
                .tag("Piste", data_point['Piste'])\
                .tag("Istunto", data_point['Istunto'])\
                .field("Y", safe_float(data_point['Y']))\
                .field("X", safe_float(data_point['X']))\
                .field("Z", safe_float(data_point['Z']))\
                .field("DeltaY", safe_float(data_point['DeltaY']))\
                .field("DeltaX", safe_float(data_point['DeltaX']))\
                .field("DeltaZ", safe_float(data_point['DeltaZ']))\
                .time(utc_timestamp, WritePrecision.NS)

            if all(safe_float(data_point[key]) is not None and abs(safe_float(data_point[key])) <= threshold for key in ['DeltaY', 'DeltaX', 'DeltaZ']):
                if None not in (data_point['Y'], data_point['X'], data_point['Z']):
                    write_api.write(bucket=influxdb_bucket, record=point)
                else:
                    logging.warning("Required data fields are missing, skipping this point.")
            else:
                logging.warning("Threshold exceeded, skipping point")
        else:
            logging.info(f"Data point at {utc_timestamp} for {data_point['Piste']} already exists. Data not added.")

# Function to process XML file and extract data points
def process_xml_file(file_content, client, write_api):
    with tempfile.TemporaryFile() as temp_file:
        temp_file.write(file_content)
        temp_file.seek(0)  # Go back to the start of the file
        try:
            tree = ET.parse(temp_file)
            root = tree.getroot()
            data_points = []
            
            for worksheet in root.findall('.//ss:Worksheet', namespaces):
                piste_name = worksheet.find('.//ss:Row[2]//ss:Cell[1]//ss:Data', namespaces).text
                table = worksheet.find('.//ss:Table', namespaces)
                rows = table.findall('.//ss:Row', namespaces)[4:]

                for row in rows:
                    data_row = {
                        'Piste': piste_name,
                        'Istunto': row.find('.//ss:Cell[1]//ss:Data', namespaces).text if row.find('.//ss:Cell[1]//ss:Data', namespaces) is not None else None,
                        'Pvm': row.find('.//ss:Cell[2]//ss:Data', namespaces).text if row.find('.//ss:Cell[2]//ss:Data', namespaces) is not None else None,
                        'Y': row.find('.//ss:Cell[3]//ss:Data', namespaces).text if row.find('.//ss:Cell[3]//ss:Data', namespaces) is not None else None,
                        'X': row.find('.//ss:Cell[4]//ss:Data', namespaces).text if row.find('.//ss:Cell[4]//ss:Data', namespaces) is not None else None,
                        'Z': row.find('.//ss:Cell[5]//ss:Data', namespaces).text if row.find('.//ss:Cell[5]//ss:Data', namespaces) is not None else None,
                        'DeltaY': row.find('.//ss:Cell[6]//ss:Data', namespaces).text if row.find('.//ss:Cell[6]//ss:Data', namespaces) is not None else None,
                        'DeltaX': row.find('.//ss:Cell[7]//ss:Data', namespaces).text if row.find('.//ss:Cell[7]//ss:Data', namespaces) is not None else None,
                        'DeltaZ': row.find('.//ss:Cell[8]//ss:Data', namespaces).text if row.find('.//ss:Cell[8]//ss:Data', namespaces) is not None else None
                    }
                    data_points.append(data_row)

            write_data_to_influx(client, write_api, data_points, influxdb_bucket)
        except ET.ParseError as e:
            logging.error(f"Error parsing XML file, Error: {e}")

# Search for unread emails
status, messages = imap.search(None, '(UNSEEN)')
if status == 'OK':
    for num in messages[0].split():
        # Fetch each email
        status, data = imap.fetch(num, '(RFC822)') #Is=Unread
        if status == 'OK':
            email_msg = email.message_from_bytes(data[0][1])
            # Check for attachments
            for part in email_msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue

                filename = part.get_filename()
                if filename and 'ReportPoints' in filename and filename.endswith('.xml'):
                    logging.info(f"Processing {filename}...")
                    file_content = part.get_payload(decode=True)
                    # Process XML file and extract data points
                    process_xml_file(file_content, client, write_api)

# Close the IMAP connection
imap.close()
imap.logout()

# Close the InfluxDB client
client.close()
logging.info('Code completed.')