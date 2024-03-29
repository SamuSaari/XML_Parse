# XML_Parser tool

This is a Python project that monitors emails and logs XML data to InfluxDB.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

What things you need to install the software and how to install them:

- Python 3.x
- InfluxDB
- An email account with IMAP enabled


## Deployment

To deploy this project on a live system, follow these steps:

1. Set up a production environment with the necessary dependencies, including Python 3.x, InfluxDB, and an email account with IMAP enabled.
2. For Gmail accounts, use app password
3. Clone the repository to your production server.
4. Navigate to the project directory in your terminal.
5. Install the required Python packages by running the following command:

    pip install -r requirements.txt

6. Set up a cron job to run the script at the desired interval. Open your terminal and type:

    crontab -e

7. Add the following line to the crontab file to run the script every hour:

    0 * * * * python /path/to/your/script.py

   Replace `/path/to/your/script.py` with the actual path to your Python script.

8. Save the crontab file and exit the editor.

Now, the script will be executed automatically at the specified interval using cron.

## Built With

* [Python](https://www.python.org/) - The programming language used
* [InfluxDB](https://www.influxdata.com/) - Time Series Database
* [IMAP](https://tools.ietf.org/html/rfc3501) - Internet Message Access Protocol
