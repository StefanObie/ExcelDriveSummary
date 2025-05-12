import pandas as pd
import urllib.parse
import requests
import config

def ceil_time_to_minute(time):
    """Ceil the time to the nearest minute."""
    return time + pd.Timedelta(minutes=1) - pd.Timedelta(seconds=time.second, microseconds=time.microsecond)

def load_file():
    # file_path = 'pythonProcessing\\MovementReports\\MovementReport17Apr25.csv'
    file_path = 'pythonProcessing\\MovementReports\\MovementReportApr2025.csv' # 1-3 April missing (max data retention 38 days)
    df = pd.read_csv(file_path)
    # print(df.head())
    return df

def preprocessing(df):
    # Remove empty columns
    columns_to_remove = ["DriverID","SkillSet","MsgTypeId","LocationTolerance","STATUS1"]
    df = df.drop(columns=columns_to_remove, errors='ignore')

    # Split the 'Location' column into 'Longitude' and 'Latitude'
    df[['Longitude', 'Latitude']] = df['Location'].str.extract(r'Long\s*:\s*([\d\.\-]+)\.\s*Lat\s*:\s*([\d\.\-]+)')
    df = df.drop(columns=['Location'], errors='ignore')

    # Convert datetime columns to datetime objects 4/1/2025 4:00:26 AM
    df['DateTime'] = pd.to_datetime(df['Report Group Date'], format='%m/%d/%Y %I:%M:%S %p', errors='coerce')

    # Trip Numbering
    df['TripNumber'] = (df['VehicleStatus'] == 'Start up').cumsum()
    # print(df[['VehicleStatus', 'DateTime', 'TripNumber']])
    # print(f"Trip Number Count: {df['TripNumber'].nunique()}")

    return df

def harsh_braking(df):
    # Harsh Braking
    df_braking = df[df['VehicleStatus'] == 'Harsh Braking']
    df_braking = df_braking.sort_values(by='DateTime') 
    df_braking = df_braking[~(df_braking['DateTime'].diff().dt.total_seconds().abs() <= 120)] # Remove false alarms for Harsh Braking
    print(f"Harsh Braking: {len(df_braking)} ({len(df_braking) * 8} Points)\n")

def get_speed_limit(lat, lon):
    """Get the speed limit for a given latitude and longitude using HERE API."""
    base_url = "https://revgeocode.search.hereapi.com/v1/revgeocode"
    params = {
        "at": f"{lat},{lon},50",
        "maxResults": "1",
        "apiKey": config.HERE_API_KEY,
        "showNavAttributes": "speedLimits",
        "types": "street"
    }
    
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    print(f"Calling HERE API...")
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if 'items' in data and len(data['items']) > 0:
            speed_limits = data['items'][0].get('navigationAttributes', {}).get('speedLimits', [])
            if speed_limits and 'maxSpeed' in speed_limits[0]:
                return speed_limits[0]['maxSpeed']
    return None

def speed_violation(df, call_here_api_for_speedlimit=False):
    df_speed = df[(df['VehicleStatus'] == 'Speed Violation') & 
                (df['MOBILESPEED'] >= 70)] # Everything under 70 km/h is not a violation
    
    print(f"Speed Violations") # Heading
    
    if len(df_speed) > 10: # Do not call HERE API if there are too many speed violations
        print(df_speed[['DateTime', 'MOBILESPEED', 'Latitude', 'Longitude']]) 
        print(f"Too many speed violations: {len(df_speed)}. Using default speed limit.")
        call_here_api_for_speedlimit = False

    speed_penalty_total = 0
    for index, row in df_speed.iterrows():
        speed = row['MOBILESPEED']

        if call_here_api_for_speedlimit:
            speedlimit = get_speed_limit(row['Latitude'], row['Longitude'])
        else: # Use a fixed speed limit
            speedlimit = 70 # Default speed limit

        if speedlimit is None:
            print(f"[ERROR] No speed limit found for coordinates: {row['Latitude']}, {row['Longitude']}")
            continue # Skip to the next iteration

        if speed - speedlimit >= 10:
            if speed - speedlimit <= 15: # 10..15
                penalty = 3
            elif speed - speedlimit <= 25: # 16..25
                penalty = 8
            elif speed - speedlimit > 25: # 26..
                penalty = 15

            speed_penalty_total += penalty
            print(f"\tSpeed Violation: {speed} km/h, Speed Limit: {speedlimit} km/h, Penalty: {penalty} points")

    print(f"Speed Violation Total: {speed_penalty_total} Points\n")

def night_time_driving(df):
    # Night Time Driving
    df['Hour'] = df['DateTime'].dt.hour
    df_night_driving = df[((df['Hour'] >= 23) | (df['Hour'] <= 4.5)) & 
                        (df['VehicleStatus'] != 'Health Check; (Ignition off)')].copy()
        
    # print(df_night_driving.head())
    print(f"Night Time Driving")
    night_penalty_total = 0

    # For each TripNumber in the night driving dataframe
    trip_nums = df_night_driving['TripNumber'].unique()
    for trip in trip_nums:
        trip_df = df[df['TripNumber'] == trip]
        # Find difference between startup and ignition off
        if len(trip_df) > 1:
            start_time = trip_df[trip_df['VehicleStatus'] == 'Start up']['DateTime'].min()
            end_time = trip_df[trip_df['VehicleStatus'] == 'Ignition off']['DateTime'].max()
            duration = end_time - start_time

            # If time between 23h and 4h30 add a penalty of 2 points for each minute. The penalty is increased by 1 point for each hour.
            t = start_time + pd.Timedelta(minutes=1, seconds=-1)
            night_penalty = 0
            while t <= end_time:
                if t.hour in [23, 4]:
                    night_penalty += 2
                elif t.hour in [0, 3]:
                    night_penalty += 4
                elif t.hour in [1, 2]:
                    night_penalty += 6
                # print(t, night_penalty)
                t += pd.Timedelta(minutes=1)
            # print(night_penalty)

            night_penalty_total += night_penalty 
            print(f"\tTrip Number: {trip}, Duration: {duration.components.hours}h:{duration.components.minutes:02d}m, Night Penalty: {night_penalty} points")

    print(f"Night Time Driving Total: {night_penalty_total}\n")


def main():
    df = load_file()
    df = preprocessing(df)

    harsh_braking(df)
    night_time_driving(df)
    speed_violation(df, call_here_api_for_speedlimit=True)

    print(f"Month-to-Date Distance: {df['MOBILEODO'].iloc[-1]:.0f} km")

if main() == '__main__':
    main()