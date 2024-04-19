import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import urllib.request
import os
import ssl
import altair as alt


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
                    try: 
                        process_flight_data(flight, flights_data, flight_index)
                    except KeyError:
                        pass
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
            arrival_datetime = datetime.fromisoformat(leg['arrivalDateTime'])
            fl_date = departure_datetime.strftime("%Y-%m-%d")
            arrival_date = arrival_datetime.strftime("%Y-%m-%d")

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
                'NUM_LEGS': len(legs),  # Total number of legs for the flight
                'DEPARTURE_TIME': departure_time.strftime('%H:%M:%S'),
                'ARRIVAL_TIME': arrival_time.strftime('%H:%M:%S'),
                'ARR_DATE': arrival_date
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
def display_flight_details(flights_df, sort_order):
    # Set up the table headers
    st.write("""
    <style>
        .btn {
            text-decoration: none;
            display: inline-block;
            color: #007BFF;  /* White text color for contrast */
            background-color: #E0E0E0;  /* Deep blue background color */
            padding: 8px 16px;
            border-radius: 5px;
            text-align: center;
            border: none;  /* Remove default border */
        }
        .btn:hover {
            background-color: #BDBDBD;  /* Slightly darker blue on hover for interactivity */
            color: white;
            cursor: pointer;
        }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("### Flight Details")

    # ensure conversion to datetime
    # flights_df['DEPARTURE_TIME'] = pd.to_datetime(flights_df['DEPARTURE_TIME'])
    # flights_df['ARRIVAL_TIME'] = pd.to_datetime(flights_df['ARRIVAL_TIME'])

    # Aggregate and prepare for sorting
    grouped = flights_df.groupby('ITINERARY_ID').agg({
        'FL_DATE': 'first',
        'AIRLINE': 'first',
        'TOTAL_PRICE': 'sum',
        'AIR_TIME': 'sum',
        'Expected_Delay': 'sum',
        'URL': 'first',
        'LOGO_URL': 'first',
        'DEPARTURE_TIME': 'min', # Assuming you have departure times and want to sort by earliest
        'NUM_LEGS': 'size'   # Count of entries per group to get number of legs
    }).reset_index()

    # Apply sort based on user input
    if sort_order == 'PRICE':
        grouped = grouped.sort_values(by='TOTAL_PRICE')
    elif sort_order == 'DEPARTURE_TIME':
        grouped = grouped.sort_values(by='DEPARTURE_TIME')
    elif sort_order == 'DURATION':
        grouped = grouped.sort_values(by='AIR_TIME')
    elif sort_order == 'ARRIVAL_TIME':
        # Ensure you calculate or store arrival time if needed for this sort
        grouped = grouped.sort_values(by='ARRIVAL_TIME')

    for _, summary in grouped.iterrows():
        if int(summary['Expected_Delay']) > 0:
            with st.expander(f"{summary['AIRLINE']} - {summary['FL_DATE']} | Total Duration: {int(summary['AIR_TIME']//60)}h {int(summary['AIR_TIME']%60)}min | Total Price: ${summary['TOTAL_PRICE']:.2f} | Est. Delay: {int(summary['Expected_Delay'])} min | Legs: {summary['NUM_LEGS']} (Click to expand)"):
                st.image(summary['LOGO_URL'], width=100)  # Adjust width as needed
                itinerary_details = flights_df[flights_df['ITINERARY_ID'] == summary['ITINERARY_ID']]
                for _, flight in itinerary_details.iterrows():
                    st.text(f"Flight Number: {flight['FL_NUMBER']}")
                    st.text(f"Origin → Destination: {flight['ORIGIN']} ➔ {flight['DEST']}")
                    st.text(f"Departure Time: {flight['DEPARTURE_TIME']}, Arrival Time: {flight['ARRIVAL_TIME']}")
                    st.text(f"Duration: {int(flight['AIR_TIME']//60)}h {int(flight['AIR_TIME']%60)}min, Distance: {int(flight['DISTANCE'])} km")
                    st.text(f"Est. Delay: {round(flight['Expected_Delay'],2)} min")
                    st.markdown("---")
                st.markdown(f"<a href='{summary['URL']}' target='_blank' class='btn'>Book Now</a>", unsafe_allow_html=True)
        else:
             with st.expander(f"{summary['AIRLINE']} - {summary['FL_DATE']} | Total Duration: {int(summary['AIR_TIME']//60)}h {int(summary['AIR_TIME']%60)}min | Total Price: ${summary['TOTAL_PRICE']:.2f} | Ahead of Schedule by: {-int(summary['Expected_Delay'])} min | Legs: {summary['NUM_LEGS']} (Click to expand)"):
                st.image(summary['LOGO_URL'], width=100)  # Adjust width as needed
                itinerary_details = flights_df[flights_df['ITINERARY_ID'] == summary['ITINERARY_ID']]
                for _, flight in itinerary_details.iterrows():
                    st.text(f"Flight Number: {flight['FL_NUMBER']}")
                    st.text(f"Origin → Destination: {flight['ORIGIN']} ➔ {flight['DEST']}")
                    st.text(f"Departure Time: {flight['DEPARTURE_TIME']}, Arrival Time: {flight['ARRIVAL_TIME']}")
                    st.text(f"Duration: {int(flight['AIR_TIME']//60)}h {int(flight['AIR_TIME']%60)}min, Distance: {int(flight['DISTANCE'])} km")
                    st.text(f"Ahead of Schedule by: {-round(flight['Expected_Delay'],2)} min")
                    st.markdown("---")
                st.markdown(f"<a href='{summary['URL']}' target='_blank' class='btn'>Book Now</a>", unsafe_allow_html=True)           

# Function to display flights cost-delay scatter plot
def display_flight_details_scatter(flights):
    # Set up the table headers
#    st.write("""
#    <style>
#        .dataframe {text-align: center; vertical-align: middle; font-family: Arial; font-size: 16px;}
#        .dataframe thead {color: #ffffff; background-color: #4a4a4a;}
#    </style>
#    """, unsafe_allow_html=True)

    # Aggregate and prepare for sorting
    grouped = flights.groupby('ITINERARY_ID').agg({
        'FL_DATE': 'first',
        'AIRLINE': 'first',
        'TOTAL_PRICE': 'sum',
        'AIR_TIME': 'sum',
        'Expected_Delay': 'sum',
        'URL': 'first',
        'LOGO_URL': 'first',
        'DEPARTURE_TIME': 'min', # Assuming you have departure times and want to sort by earliest
        'NUM_LEGS': 'size'   # Count of entries per group to get number of legs
    }).reset_index()

    grouped['Estimated Delay'] = (grouped['Expected_Delay'].round())

    y_range_max_1 = grouped['Estimated Delay'].max()
    y_range_min_1 = grouped['Estimated Delay'].min()

    x_range_max_1 = grouped['TOTAL_PRICE'].max()
    x_range_min_1 = grouped['TOTAL_PRICE'].min()



    c = (
       alt.Chart(grouped)
       .mark_circle(size=200)
       .encode(x=alt.X("TOTAL_PRICE:Q", title='Total Price [USD]', scale=alt.Scale(domain=(0.8*x_range_min_1,1.2*x_range_max_1))), y=alt.Y('Estimated Delay', title='Estimated Delay [mins]', scale=alt.Scale(domain=(y_range_min_1-5,y_range_max_1+5))), color=alt.Color("AIRLINE").scale(scheme="category10") , href='URL', tooltip=["TOTAL_PRICE", "Estimated Delay"])
    )

    c['usermeta'] = {
    "embedOptions": {
        'loader': {'target': '_blank'}
        }
    }

    st.markdown("### Expected Flight Delay Vs Cost")
    st.markdown("*Negative numbers mean that our model predicts to arrive ahead of schedule*")
    st.markdown("\n")
    # Create a table-like display using columns
#    st.scatter_chart(
#        flights,
#        x='TOTAL_PRICE',
#        y='Expected_Delay',
#        color='AIRLINE_CODE',
#        # size='col3',
#    )
    st.altair_chart(c, use_container_width=True)

# Create the Streamlit app interface
def main():

    # # Place input widgets in the sidebar
    tomorrow = datetime.today().date() + timedelta(days=1)
    today = datetime.today().date() + timedelta(days=0)

    top_us_airports = {
    "ATL": "Atlanta - Hartsfield-Jackson Atlanta International Airport",
    "LAX": "Los Angeles - Los Angeles International Airport",
    "ORD": "Chicago - O'Hare International Airport",
    "DFW": "Dallas/Fort Worth - Dallas/Fort Worth International Airport",
    "DEN": "Denver - Denver International Airport",
    "JFK": "New York - John F. Kennedy International Airport",
    "SFO": "San Francisco - San Francisco International Airport",
    "SEA": "Seattle - Seattle-Tacoma International Airport",
    "LAS": "Las Vegas - McCarran International Airport",
    "MCO": "Orlando - Orlando International Airport",
    "SAN": "San Diego - San Diego International Airport",
    "MSP": "Minneapolis - St Paul International Airport"
    }

    # # airports with lat/lng
    # airports = {
    # "ATL": {"name": "Atlanta - Hartsfield-Jackson Atlanta International Airport", "lat": 33.6407, "lon": -84.4277},
    # "LAX": {"name": "Los Angeles - Los Angeles International Airport", "lat": 33.9416, "lon": -118.4085},
    # "ORD": {"name": "Chicago - O'Hare International Airport", "lat": 41.9742, "lon": -87.9073},
    # "DFW": {"name": "Dallas/Fort Worth - Dallas/Fort Worth International Airport", "lat": 32.8998, "lon": -97.0403},
    # "DEN": {"name": "Denver - Denver International Airport", "lat": 39.8561, "lon": -104.6737},
    # "JFK": {"name": "New York - John F. Kennedy International Airport", "lat": 40.6413, "lon": -73.7781},
    # "SFO": {"name": "San Francisco - San Francisco International Airport", "lat": 37.6213, "lon": -122.3790},
    # "SEA": {"name": "Seattle - Seattle-Tacoma International Airport", "lat": 47.4502, "lon": -122.3088},
    # "LAS": {"name": "Las Vegas - McCarran International Airport", "lat": 36.0840, "lon": -115.1537},
    # "MCO": {"name": "Orlando - Orlando International Airport", "lat": 28.4312, "lon": -81.3080}
    # }

    with st.sidebar:
        st.header("Search Flights")
        # source_airport_code = st.text_input("Source Airport Code", "")
        # destination_airport_code = st.text_input("Destination Airport Code", "")

        # Dropdown menu for selecting source and destination airports
        source_airport_code = st.selectbox(
            "Select Source Airport Code",
            options=list(top_us_airports.keys()),
            format_func=lambda x: f"{x} - {top_us_airports[x]}",
            index=list(top_us_airports.keys()).index('ATL')
        )

        destination_airport_code = st.selectbox(
            "Select Destination Airport Code",
            options=list(top_us_airports.keys()),
            format_func=lambda x: f"{x} - {top_us_airports[x]}",
            index=list(top_us_airports.keys()).index('LAX')
        )

        out_date = st.date_input("Departure Date", 
                                  min_value=today,  # Users can only select tomorrow or later
                                  value=tomorrow,
                                  max_value=datetime.today().date() + timedelta(days=365), help="You can only select a date starting from tomorrow onwards.")
        class_of_service = st.selectbox(
            "Class of Service",
            ("ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"),
            format_func=lambda x: x.replace("_", " ").title()  # Format the display text
        )
        sort_order = st.selectbox(
            "Sort Order",
            ("PRICE", "DURATION"),
            format_func=lambda x: x.replace("_", " ").title()  # Format the display text
        )
        itinerary_type = st.selectbox(
            "Itinerary Type",
            ("ONE_WAY",)
        )

        # Check if the source and destination are the same
        if source_airport_code == destination_airport_code:
            st.error("Source and destination airports cannot be the same. Please select different airports.")

        # Button to perform search
        search_button = st.button("Search Flights")

    # Button to perform search
    if search_button and source_airport_code != destination_airport_code:
        with st.spinner('Searching for flights...'):
            # st.write("Searching for flights...")
            # st.write(f"Source Airport Code: {source_airport_code}")
            # st.write(f"Destination Airport Code: {destination_airport_code}")
            # st.write(f"Outbound Date: {out_date}")
            # st.write(f"Class of Service: {class_of_service}")
            # st.write(f"Sort Order: {sort_order}")
            # st.write(f"Itinerary Type: {itinerary_type}")
            # Call the function to fetch and process data using the input values
            flights_df=fetch_and_process_data(source_airport_code, destination_airport_code, out_date, class_of_service, sort_order, itinerary_type)

            # Display the result
            # st.write("Here is the processed data:")
            # st.write(flights_df)

            # Call ML model API

            if isinstance(flights_df, pd.DataFrame):
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
                st.success("Flight Results Below:")
                display_flight_details_scatter(output_df)
                display_flight_details(output_df,sort_order)
            else:
                st.error("No flights found for the selected criteria.")

    # else:
    #     st.error("Please select different airports for source and destination.")

# Start the app
if __name__ == "__main__":
    main()
