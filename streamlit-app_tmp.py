import pandas as pd
import folium
import streamlit as st
from streamlit_folium import folium_static
import geopandas as gpd
from folium.plugins import MarkerCluster
import sqlite3

class App():
    def __init__(self, geo_data, localisation, conn):
        self.geo_data = geo_data
        self.conn = conn
        self.localisation = localisation
        self.markers = {}
        self.map_agencies = folium.Map(location=[46.5, 2.5], zoom_start=6, tiles='CartoDB positron')
        self.draw_map()

    def mark_card(self, map, localisation):
        colors = ["green", "yellow", "red"]
        longitudes = localisation["longitude"].to_list()
        latitudes = localisation["latitude"].to_list()
        agences = localisation["agence"].to_list()
        counts =  localisation["Count"].to_list()
        marker_cluster = MarkerCluster().add_to(map)
        for i in range(len((longitudes))):
            agence = agences[i]
            x = longitudes[i]
            y = latitudes[i]
            try:
                color = colors[counts[i]]
            except:
                color = colors[-1]
            icon = folium.plugins.BeautifyIcon(
                                    border_color=color,
                                    text_color="black",
                                    number=agence,
                                    inner_icon_style="margin-top:0;",
                                    border_width=4
                                )
            marker = folium.Marker(location=[y, x],
                                icon=icon,
                                id=f'marker-{i}',
                                tooltip=f'Agence {agence}',
                                popup=folium.Popup(f'Agence {agence}<br> Projets en cours: {counts[i]}', max_height=200, max_width=300))
            marker.add_to(marker_cluster)
            self.marker_cluster = MarkerCluster
            self.markers[agence] = marker

    def selection(self, map_agencies):
        # Set the layout to a menu-like structure
        col = st.sidebar

        with col:
            # Create selectbox and button using streamlit
            selected_id = st.selectbox("Sélectionner une agence", [i for i in self.markers])
            button_clicked = st.button("Attribuer une tâche")

        # Perform task when the button is clicked
        if button_clicked:
            if selected_id:
                col.write(f"Tâche attribuée à l'agence: {selected_id}")
                print(self.localisation[self.localisation["agence"] == selected_id]["Count"].iloc[0])
                self.localisation.loc[self.localisation["agence"] == selected_id, "Count"] += 1
                print(self.localisation[self.localisation["agence"] == selected_id]["Count"].iloc[0])
                
            else:
                col.warning("Veuillez sélectionner une agence avant d'attribuer une tâche.")
                

    def draw_map(self):
        self.mark_card(self.map_agencies, self.localisation)
        # Display the map in Streamlit
        self.selection(self.map_agencies)                       
        folium.GeoJson(self.geo_data).add_to(self.map_agencies)
        folium.plugins.Fullscreen().add_to(self.map_agencies)
        st_map = folium_static(self.map_agencies, width=800, height=800)


@st.cache_resource()
def fetch_and_clean_data(_conn):
    # Establish a connection to the database

    # Fetch data from the database using SQL queries
    localisation_query = "SELECT * FROM planning"
    localisation = pd.read_sql(localisation_query, _conn)

    geo_data = gpd.read_file("departements.geojson")
    # Close the database connection

    cursor = _conn.cursor()

    # Execute the query to fetch all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

    # Fetch all the table names
    tables = cursor.fetchall()

    # Print the table names
    for table in tables:
        print(table[0])
        
    print(localisation)
    return localisation, geo_data


def main():
    conn = sqlite3.connect('planning.db')
    localisation, geo_data = fetch_and_clean_data(conn)
    app = App(geo_data, localisation, conn)    
    app.conn.close()

if __name__=="__main__":
    main()