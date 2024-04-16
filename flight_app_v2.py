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

# def remove_duplicates_from_dataframe(flights_df):
#     # Define columns to consider for identifying duplicates
#     columns_to_consider =['FL_NUMBER', 'AIRLINE', 'FL_DATE','AIRLINE_CODE','ORIGIN','DEST','AIR_TIME','DISTANCE']
#     unique_flights_df = flights_df.drop_duplicates(subset=columns_to_consider)
#     return unique_flights_df

# Define function to fetch and process data
def fetch_and_process_data(source_airport, destination_airport, out_date, class_of_service, sort_order, itinerary_type):
    allow_self_signed_https(True)  # Allow self-signed HTTPS
    # API parameters
    api_key = "04add5b7cdmshd4b470181d45798p1428bbjsn3f4be7e144f4"
    api_host = "tripadvisor16.p.rapidapi.com"
    url = "https://tripadvisor16.p.rapidapi.com/api/v1/flights/searchFlights"

    # # API customer inputs
    # itineraryType = "ONE_WAY"
    # sortOrder = 'PRICE'
    # classOfService = "ECONOMY"
    # pageNumber = '1'
    # currencyCode = 'USD'
    
    flights_data = []
    page_limit = 10  # Set the page limit to 10

    for page_number in range(1, page_limit + 1):
    # Build API inputs
        querystring = {
            "sourceAirportCode": source_airport,
            "destinationAirportCode": destination_airport,
            "date": out_date.strftime('%Y-%m-%d'),  # Format date for API
            "classOfService": class_of_service,
            "sortOrder": sort_order,
            "itineraryType": itinerary_type,
            "pageNumber": '1',
            "currencyCode": 'USD'
        }

        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": api_host
        }

        # # Debug print to verify API inputs
        # st.write("API URL:", url)
        # st.write("Headers:", headers)
        # st.write("Querystring Parameters:", querystring)

        # Fetch data from API
        response = requests.get(url, headers=headers, params=querystring, verify=False)

        if response.status_code == 200:
            response_text = response.json()  # Convert response to JSON format
            # Check if the expected keys exist in the response
            if 'data' in response_text and 'flights' in response_text['data']:
                for flight_index, flight in enumerate(response_text['data']['flights']):
                    # Process each flight
                    process_flight_data(flight, flights_data, flight_index)
                    # pass
            else:
                break
        else:
            print(f"Failed to fetch data from API on page {page_number}. Status code: {response.status_code}")
            break

        # Convert json to python dict
        # response_text = json.loads(response.text)
        # Create DataFrame
        flights_df = pd.DataFrame(flights_data)
        return flights_df

def process_flight_data(flight, flights_data, flight_index):
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
                'LOGO_URL': str(flight['purchaseLinks'][0]['partnerSuppliedProvider']['logoUrl']),
                'URL': str(flight['purchaseLinks'][0]['url']),
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


# Function to make request to ML model
def request_ml_model(sub_flight_df):
    ml_api_key = 'MJ62jbpd130GjJbvoMrI7hHS3PCzIPVm'

    def allowSelfSignedHttps(allowed):
        # bypass the server certificate verification on client side
        if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):
            ssl._create_default_https_context = ssl._create_unverified_context

    allowSelfSignedHttps(True)  # this line is needed if you use self-signed certificate in your scoring service.

    columns_to_keep = ['FL_DATE','AIRLINE','AIRLINE_CODE','DOT_CODE','FL_NUMBER','ORIGIN','DEST','AIR_TIME','DISTANCE','ARR_DELAY','CANCELLED']
    sub_flight_df = sub_flight_df[columns_to_keep]

    # sub_flight_df

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
        return result_df
    except urllib.error.HTTPError as error:
        print("The request failed with status code: " + str(error.code))
        print(error.info())
        print(error.read().decode("utf8", 'ignore'))

# Function to display flight details
def display_flight_details(flights):
    # Set up the table headers
    st.write("""
    <style>
        .dataframe {text-align: center; vertical-align: middle; font-family: Arial; font-size: 16px;}
        .dataframe thead {color: #ffffff; background-color: #4a4a4a;}
    </style>
    """, unsafe_allow_html=True)
    st.markdown("### Flight Details")
    # Create a table-like display using columns
    header_columns = st.columns([4, 4, 4, 4, 4, 4, 4,4])
    headers = ["Airline", "Flight Number","Date","Route", "Duration (min)", "Price (USD)","Est. Delay (min)","Book Link"]
    for header, col in zip(headers, header_columns):
        col.write(header)

    for index, flight in flights.iterrows():
        cols = st.columns([4, 4, 4, 4, 4, 4, 4,4])
        cols[0].image(flight['LOGO_URL'], width=50)
        # cols[1].write(flight['AIRLINE'])
        cols[1].write(f"{flight['AIRLINE_CODE']}-{flight['FL_NUMBER']}")
        cols[2].write(f"{flight['FL_DATE']}")
        cols[3].write(f"{flight['ORIGIN']} ➔ {flight['DEST']}")
        cols[4].write(f"{round(flight['AIR_TIME']//60)}hr {round(flight['AIR_TIME']%60)}min")
        cols[5].write(f"${flight['TOTAL_PRICE']}")
        cols[6].write(f"{round(flight['Expected_Delay'])} min")
        with cols[7]:
            # Link styled as a button directly clickable
            st.markdown(f"<a href='{flight['URL']}' target='_blank' class='btn'>Book Now</a>", unsafe_allow_html=True)

# Create the Streamlit app interface
def main():
    st.title("Flight Search")

    # Input for source airport code
    source_airport_code = st.text_input("Source Airport Code", "")

    # Input for destination airport code
    destination_airport_code = st.text_input("Destination Airport Code", "")

    # Input for outbound date
    out_date = st.date_input("Outbound Date", min_value=datetime.today())

    # Select box for class of service
    class_of_service = st.selectbox(
        "Class of Service",
        ("ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"),
        format_func=lambda x: x.replace("_", " ").title()  # Format the display text
    )

    # Select box for sort order
    sort_order = st.selectbox(
        "Sort Order",
        ("PRICE", "DEPARTURE_TIME", "ARRIVAL_TIME", "DURATION"),
        format_func=lambda x: x.replace("_", " ").title()  # Format the display text
    )

    # Select box for itinerary type
    itinerary_type = st.selectbox(
        "Itinerary Type",
        ("ONE_WAY", "ROUND_TRIP")
    )

    # Button to perform search
    if st.button("Search Flights"):
        st.write("Searching for flights...")
        # Call the function to fetch and process data using the input values
        flights_df=fetch_and_process_data(source_airport_code, destination_airport_code, out_date, class_of_service, sort_order, itinerary_type)

        # Display the result
        # st.write("Here is the processed data:")
        # st.write(flights_df)

        # Call ML model API
        # st.write("Making prediction using ML model... Please wait.")
        result_df = request_ml_model(flights_df)
        # columns_to_keep = ['FL_DATE','AIRLINE','AIRLINE_CODE','DOT_CODE','FL_NUMBER','ORIGIN','DEST','AIR_TIME','DISTANCE','ARR_DELAY','CANCELLED']
        # output_df = flights_df.merge(result_df, on = columns_to_keep, how = 'left')


        #Display ML model results
        # st.write("Here are the predicted delays:")
        # st.write(result_df)

        # # Merge the original flights data with ML model results
        output_df = pd.concat([flights_df, result_df], axis=1)
        output_df = output_df.loc[:, ~output_df.columns.duplicated()]

        # # Rename the 'Scored Labels' column to 'Expected_Delay'
        output_df.rename(columns={'Scored Labels': 'Expected_Delay'}, inplace=True)

        # # Drop unnecessary columns
        columns_to_drop = ['ARR_DELAY', 'CANCELLED', 'DOT_CODE']
        output_df = output_df.drop(columns=columns_to_drop)

        # # Display the final output
        # st.write("Final Output DataFrame:")
        # st.write(output_df)

        # Display flight details
        # cleaned_flights_df = remove_duplicates_from_dataframe(output_df)
        display_flight_details(output_df)

# Start the app
if __name__ == "__main__":
    main()
