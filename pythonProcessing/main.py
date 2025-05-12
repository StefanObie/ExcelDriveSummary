import pandas as pd

def ceil_time_to_minute(time):
    """Ceil the time to the nearest minute."""
    return time + pd.Timedelta(minutes=1) - pd.Timedelta(seconds=time.second, microseconds=time.microsecond)

# file_path = 'pythonProcessing\MovementReports\MovementReport17Apr25.csv'
file_path = 'pythonProcessing\MovementReports\MovementReportApr2025.csv'
df = pd.read_csv(file_path)
# print(df.head())

# Remove empty columns
columns_to_remove = ["DriverID","SkillSet","MsgTypeId","LocationTolerance","STATUS1"]
df = df.drop(columns=columns_to_remove, errors='ignore')

# Split the 'Location' column into 'Longitude' and 'Latitude'
df[['Longitude', 'Latitude']] = df['Location'].str.extract(r'Long\s*:\s*([\d\.\-]+)\.\s*Lat\s*:\s*([\d\.\-]+)')
df = df.drop(columns=['Location'], errors='ignore')

# Convert datetime columns to datetime objects 4/1/2025 4:00:26 AM
df['DateTime'] = pd.to_datetime(df['Report Group Date'], format='%m/%d/%Y %I:%M:%S %p', errors='coerce')

print(f"Month-to-Date Distance: {df['MOBILEODO'].iloc[-1]:.0f} km")

# Harsh Braking
df_braking = df[df['VehicleStatus'] == 'Harsh Braking']
df_braking = df_braking.sort_values(by='DateTime') 
df_braking = df_braking[~(df_braking['DateTime'].diff().dt.total_seconds().abs() <= 120)] # Remove false alarms for Harsh Braking
print(f"Harsh Braking Count: {len(df_braking)}")

# Speed Violation
df_speed = df[(df['VehicleStatus'] == 'Speed Violation') & 
              (df['MOBILESPEED'] >= 70)] # Everything under 70 km/h is not a violation
print(f"Speed Violation Count: {len(df_speed)}")
print(f"Speed Vioations: \n{df_speed[['DateTime', 'MOBILESPEED', 'Latitude', 'Longitude']]}")

# Trip Numbering
df['TripNumber'] = (df['VehicleStatus'] == 'Start up').cumsum()
# pd.set_option('display.max_rows', None)
# print(df[['VehicleStatus', 'DateTime', 'TripNumber']])
# print(f"Trip Number Count: {df['TripNumber'].nunique()}")

# Night Time Driving
df['Hour'] = df['DateTime'].dt.hour
df_night_driving = df[((df['Hour'] >= 23) | (df['Hour'] <= 4.5)) & 
                      (df['VehicleStatus'] != 'Health Check; (Ignition off)')].copy()
    
# print(df_night_driving.head())
# print(f"Night Time Driving Count: {len(df_night_driving)}")

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
        print(night_penalty)

        # Ceil the duration to the nearest minute
        # if duration.total_seconds() > 0:
        #     duration = pd.Timedelta(seconds=(duration.total_seconds() // 60 + 1) * 60)
        # # Display as HHh:MM
        # hours, remainder = divmod(duration.total_seconds(), 3600)
        # minutes, _ = divmod(remainder, 60)
        # duration_str = f"{int(hours)}h:{int(minutes):02d}m"
        # Print hours only of Timedelta
        # hours = duration.components.hours
        # minutes = duration.components.minutes
        print(f"Trip Number: {trip}, Duration: {duration.components.hours}h:{duration.components.minutes:02d}m, Night Penalty: {night_penalty} points")
