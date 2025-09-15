import socket
import pandas as pd
from IPython.display import display, clear_output
import time
from math import radians, sin, cos, sqrt, atan2

MY_LAT=27.6754528
MY_LON=85.3350065
IP="192.168.1.3"
PORT =30003
aircraft_data={}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c = 2*atan2(sqrt(a), sqrt(1-a))
    return R*c

sock= socket.socket(socket.AF_INET,socket.SOCK_STREAM)
sock.connect((IP,PORT))

"""
##4kb chunks = 4096
while True:
    data=sock.recv(4096).decode(errors='ignore')
    for line in data.strip().split("\n"):
        print("RAW:",line)
"""
while True:
    data=sock.recv(4096).decode(errors="ignore")
    for line in data.strip().split("\n"): 
        parts=line.split(",")
        if len(parts)>15 and parts[0]=="MSG" and parts[1]=="3":
            icao=parts[4]
            callsign=parts[10].strip() if parts[10].strip() else icao #remove spaces ,if not empty useit ,else fall back to parts[4]
            altitude=parts[11]
            if altitude:
                altitude=int("".join(filter(str.isdigit,altitude)))
            else:
                altitude=0
            lat=parts[14]
            lon=parts[15]

            if lat and lon:
                lat,lon= float(lat),float(lon)
                distance=haversine(MY_LAT,MY_LON,lat,lon)
                aircraft_data[icao]={
                    "callsign":callsign,
                    "alt":altitude,
                    "lat":lat,
                    "lon":lon,
                    "last_seen":time.time(),
                    "distance_km": round(distance,1)
                }


    now=time.time()
    for icao in list(aircraft_data.keys()):
        if now-aircraft_data[icao]["last_seen"]>60:
            del aircraft_data[icao]
        
    clear_output(wait=True)
    if aircraft_data:
        df = pd.DataFrame.from_dict(aircraft_data, orient="index")
        display(df[["callsign", "alt", "lat", "lon", "distance_km"]].sort_values("distance_km"))
    else:
        print("No aircraft seen in the last 60 seconds.")

    time.sleep(1)


