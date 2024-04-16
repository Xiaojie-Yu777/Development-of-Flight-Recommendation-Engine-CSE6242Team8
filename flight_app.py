import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import urllib.request
import os
import ssl


# Function to allow self-signed HTTPS
def allow_self_signed_https(allowed):
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):
        ssl._create_default_https_context = ssl._create_unverified_context


# Define function to fetch and process data
def fetch_and_process_data(source_airport, destination_airport, out_date):
    allow_self_signed_https(True)  # Allow self-signed HTTPS
    # API parameters
    api_key = "04add5b7cdmshd4b470181d45798p1428bbjsn3f4be7e144f4"
    api_host = "tripadvisor16.p.rapidapi.com"
    url = "https://tripadvisor16.p.rapidapi.com/api/v1/flights/searchFlights"

    # API customer inputs
    itineraryType = "ONE_WAY"
    sortOrder = 'PRICE'
    classOfService = "ECONOMY"
    pageNumber = '1'
    currencyCode = 'USD'

    # Build API inputs
    querystring = {
        "sourceAirportCode": source_airport,
        "destinationAirportCode": destination_airport,
        "date": out_date.strftime("%Y-%m-%d"),
        "itineraryType": itineraryType,
        "sortOrder": sortOrder,
        "classOfService": classOfService,
        "pageNumber": pageNumber,
        "currencyCode": currencyCode
    }

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": api_host
    }

    # Fetch data from API
    response = requests.get(url, headers=headers, params=querystring)

    # Convert json to python dict
    response_text = json.loads(response.text)

    flights_data = []

    for flight_index, flight in enumerate(response_text['data']['flights']):
        segments = flight['segments']
        for segment_index, segment in enumerate(segments):
            legs = segment['legs']
            for leg_index, leg in enumerate(legs):
                departure_time = datetime.fromisoformat(leg['departureDateTime'])
                arrival_time = datetime.fromisoformat(leg['arrivalDateTime'])
                air_time_minutes = (arrival_time - departure_time).total_seconds() / 60

                departure_datetime = datetime.fromisoformat(leg['departureDateTime'])
                fl_date = departure_datetime.strftime("%Y-%m-%d")

                flight_info = {
                    'FL_DATE': str(fl_date),
                    'AIRLINE': str(flight['purchaseLinks'][0]['partnerSuppliedProvider']['displayName']),
                    'AIRLINE_CODE': leg['operatingCarrier']['code'],
                    'DOT_CODE': "0",
                    'FL_NUMBER': leg['flightNumber'],
                    'ORIGIN': leg['originStationCode'],
                    'DEST': leg['destinationStationCode'],
                    'AIR_TIME': air_time_minutes,
                    'DISTANCE': leg['distanceInKM'],
                    'ARR_DELAY': "0",
                    'CANCELLED': "0",
                    'TOTAL_PRICE': flight['purchaseLinks'][0]['totalPrice'],
                    # Assuming only one purchase link per flight
                    'ITINERARY_ID': f'{flight_index}_{segment_index + 1}',  # Unique identifier for each itinerary
                    'LEG_INDEX': leg_index + 1,  # Add leg index to differentiate legs of the same flight
                    'NUM_LEGS': len(legs)  # Total number of legs for the flight
                }
                flights_data.append(flight_info)

    # Create DataFrame
    flights_df = pd.DataFrame(flights_data)
    sub_flight_df = flights_df.iloc[:, :11]
    return sub_flight_df

# Function to make request to ML model
def request_ml_model(sub_flight_df):
    ml_api_key = 'MJ62jbpd130GjJbvoMrI7hHS3PCzIPVm'

    def allowSelfSignedHttps(allowed):
        # bypass the server certificate verification on client side
        if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):
            ssl._create_default_https_context = ssl._create_unverified_context

    allowSelfSignedHttps(True)  # this line is needed if you use self-signed certificate in your scoring service.

    sub_flight_df

    # Convert dataframe to a list of dictionaries
    data_to_send = sub_flight_df.to_dict(orient='records')

    data = {
        "Inputs": {
            "input1": data_to_send
        },
        "GlobalParameters": {}
    }

    body = str.encode(json.dumps(data))

    url = 'http://d16ea803-be49-45c8-a407-8b01a550f87e.eastus2.azurecontainer.io/score'

    # Replace this with the primary/secondary key or AMLToken for the endpoint
    api_key = ml_api_key  # You need to define ml_api_key

    if not api_key:
        raise Exception("A key should be provided to invoke the endpoint")

    headers = {'Content-Type': 'application/json', 'Authorization': ('Bearer ' + api_key)}

    req = urllib.request.Request(url, body, headers)

    try:
        response = urllib.request.urlopen(req)
        result = response.read()
        print(result)
        # Decode bytes to string
        json_string = result.decode('utf-8')
        # Convert string to dictionary
        data = json.loads(json_string)
        # Extract the list of dictionaries from the JSON
        results = data['Results']['WebServiceOutput0']
        # Convert the list of dictionaries to DataFrame
        result_df = pd.DataFrame(results)
        result_df
    except urllib.error.HTTPError as error:
        print("The request failed with status code: " + str(error.code))
        print(error.info())
        print(error.read().decode("utf8", 'ignore'))




# Create the Streamlit app interface
def main():
    st.title("Flight Delay Prediction App")
    st.sidebar.title("Parameters")

    # Define sidebar inputs
    source_airport = st.sidebar.text_input("Source Airport Code", "EWR")
    destination_airport = st.sidebar.text_input("Destination Airport Code", "LAS")
    out_date = st.sidebar.date_input("Outbound Date", datetime.today())
    # Add more sidebar inputs as needed

    # Add a button to trigger the API call and data processing
    if st.sidebar.button("Fetch Flights Data"):
        st.write("Fetching data... Please wait.")
        # Call the function to fetch and process data
        flights_df = fetch_and_process_data(source_airport, destination_airport, out_date)

        # Display the result
        st.write("Here is the processed data:")
        st.write(flights_df)

        # Call ML model API
        st.write("Making prediction using ML model... Please wait.")
        result_df = request_ml_model(flights_df)

        # Display ML model results
        st.write("Here are the predicted delays:")
        st.write(result_df)

        # Merge the original flights data with ML model results
        output_df = pd.concat([flights_df, result_df], axis=1)
        output_df = output_df.loc[:, ~output_df.columns.duplicated()]

        # Rename the 'Scored Labels' column to 'Expected_Delay'
        output_df.rename(columns={'Scored Labels': 'Expected_Delay'}, inplace=True)

        # Drop unnecessary columns
        columns_to_drop = ['ARR_DELAY', 'CANCELLED', 'DOT_CODE']
        output_df = output_df.drop(columns=columns_to_drop)

        # Display the final output
        st.write("Final Output DataFrame:")
        st.write(output_df)


# Start the app
if __name__ == "__main__":
    main()
