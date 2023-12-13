import pandas as pd
import folium
import streamlit as st
from streamlit_folium import folium_static
import geopandas as gpd
from folium.plugins import MarkerCluster
import sqlite3
import datetime
import traceback
from jinja2 import Template

categ = ["DPT-Agence", "Projet-Commerce-Agence", "Projet-DPP-Agence",
            "Projet Contrôle de gestion", "Projet LTL-FTL", "Projet-DRC-Agence",
                "Projet-Ops-Agence"]

name_table = {'Catégorie':"categorie", "Titre":"titre_projet","Description":"descriptif", "Début": "date_debut","Fin":"date_fin", "Agence":"code_agence"}

if st.session_state.get('step') is None:
    st.session_state['step'] = 0

if "visibility" not in st.session_state:
    st.session_state.visibility = "visible"
    st.session_state.disabled = False

def edit_db(edited, cursor, conn, index):
    for i in edited:
            new_mapping = {}
            try:
                for key, value in edited[i].items():
                    new_mapping[name_table[key]] = value
            except:
                return
            edited[i] = new_mapping

            sql_template = Template("""
            UPDATE Projets
                SET {% for key, value in data.items() %}
                    {{ key }} = {{ '?' }}{% if not loop.last %},{% endif %}
                    {% endfor %}
            WHERE projet_id = {{ '?' }}
            """)
            query = sql_template.render(data=edited[i])
            values = [edited[i][x] for x in edited[i]] + [int(index.iloc[i])]
            cursor.execute(query, values)
            conn.commit()

def delete_rows(to_delete, cursor, conn):
    sql_template = Template("""
        Delete From Projets Where projet_id In (
                            {% for id in ids%}
                             {{ id }} {% if not loop.last %}, {% endif %}
                            {% endfor %}
        )
    """)
    query = sql_template.render(ids=to_delete)
    print(query)
    cursor.execute(query)
    conn.commit()

def callback(index, cursor, conn, obj, agence):
    if "my_key" in st.session_state:
        
        edited = st.session_state.my_key['edited_rows']
        if len(edited) > 0:
            edit_db(edited, cursor, conn, index)

        deleted = st.session_state.my_key["deleted_rows"]
        if len(deleted) > 0:
            deleted = [int(index.iloc[i]) for i in deleted]
            delete_rows(deleted, cursor, conn)
            
        added = st.session_state.my_key["added_rows"]
        if len(added) > 0:
            x = st.session_state.my_key["added_rows"].pop()
            if agence != "Toutes les agences" and len(x) > 0:
                if "Agence" not in x:
                    x["Agence"] = agence
                obj.submit(added_row=x)
        if len(edited) > 0 or len(deleted) > 0 or len(added) > 0:
            st.cache_data.clear()
        if len(added) > 0:        
            st.session_state["my_key"]["added_rows"].clear()
 
def retrieve_information(rows, name, count):
    string = f"Agence {name}<br>"
    string += f"Nombre de projets: {count} <br>"
    for row in rows:
        string += f"<br>{row[1]}: {row[2]}, {row[3]} <br>"
    return string

@st.cache_data()
def request_db(_agences, _conn):
    cursor = _conn.cursor()
    count = []
    dic_infos = {}

    for i in _agences:
        # Execute the SQL query to fetch agency information
        query = f"SELECT COUNT(*) FROM Projets WHERE code_agence = '{i}'"
        cursor.execute(query)
        project_count = cursor.fetchone()

        # Fetch the result
        if project_count is not None:
            try:
                project_count = project_count[0]
                # Print the result
                print(f"{i} nbr de projets: {project_count}")
            except Exception as e:
                print(e)
                project_count = 0
        else:
            project_count = 0
        count.append(project_count)
        sec_query = f"SELECT * FROM Projets WHERE code_agence = '{i}'"
        cursor.execute(sec_query)
        rows = cursor.fetchall()
        dic_infos[i] = retrieve_information(rows,i, project_count)
    cursor.close()
    return count, dic_infos


class App():
    def __init__(self, geo_data, conn, map_agencies, cursor, localisation):
        self.geo_data = geo_data
        self.conn = conn
        self.localisation = localisation
        self.markers = {}
        self.cursor = cursor
        self.marker_cluster = None
        self.map_agencies = map_agencies
        self.draw_map()

    def submit(self, selected_categ="", title="", description="", date_debut="", date_fin="", selected_agence="", added_row=""):
                if added_row != "":
                    new_mapping = {}
                    try:
                        for key, value in added_row.items():
                            new_mapping[name_table[key]] = value
                    except:
                        return
                    added_row = new_mapping
                    return
                query = "INSERT INTO Projets (categorie, titre_projet, descriptif, date_debut, date_fin, code_agence) VALUES (?, ?, ?, ?, ?, ?)"
                parameters = (selected_categ, title, description, date_debut, date_fin, selected_agence)
                self.cursor.execute(query, parameters)
                # Commit the changes to the database
                self.conn.commit()
                st.write(f"Tâche attribuée à l'agence: {selected_agence}")      
                st.cache_data.clear()

    def add_agence(self, agence="", category="", title="", description="", begin="", end=""):
        if agence not in self.agences_name:
            st.write(":red[Merci de sélectionner une agence]")
            return
        if category not in categ:
            st.write(":red[Merci de sélectionner une catégorie]")
            return
        if begin >= end:
            st.write(":red[Merci de sélectionner une date de fin ultérieure à la date de début.]")
            return
        self.submit(category, title, description, begin, end, agence)
        st.write(f":green[{title} ajoutée à l'agence {agence}]")
        st.rerun()

    def display_editable_df(self, agence):
        query = f"SELECT * FROM Projets where code_agence = ?" if agence != "Toutes les agences" else "SELECT * FROM Projets"
        try:
            rows = self.cursor.execute(query, (str(agence), )).fetchall() \
                if agence != "Toutes les agences" else self.cursor.execute(query).fetchall()
            df = pd.DataFrame(rows, columns=['Index', 'Catégorie', 'Titre', 'Description', 'Début', 'Fin', "Agence"])
            cols = df.columns.tolist()
            cols = [cols[-1]] + cols[:-1]
            df = df[cols]
            index = df["Index"]
            df = df.drop(columns=["Index"])
        except Exception as e:
            print(e)
            df = pd.DataFrame()
        st.session_state.updated_df = st.data_editor(df, num_rows="dynamic",  key="my_key", on_change=callback, args=[index, self.cursor, self.conn, self, agence])

    def selection(self):
        # Set the layout to a menu-like structure
        sidebar = st.sidebar

        # Create a button to display the form
        with sidebar:
            agences = [i for i in self.agences_name]
            agences = list(sorted(agences))
            agences.insert(0, "Toutes les agences")
            chosen_agence = st.selectbox("Détail Agence", agences)
            if chosen_agence:
                self.display_editable_df(chosen_agence)
            st.write("Ajouter une tâche")
            with st.form("Ajouter une tâche"):
                agence_picker = st.selectbox("Choisir Agence", [i for i in self.agences_name],
                                             index=None, placeholder="Choisir une agence")
                category = st.selectbox("Choisir catégorie", [i for i in categ], index=None, 
                                        placeholder="Choisir une catégorie")
                title = st.text_input(
                    "Titre 👇",
                    label_visibility=st.session_state.visibility,
                    disabled=st.session_state.disabled,
                    placeholder="Titre",
                )
                description = st.text_input(
                    "Description 👇",
                    label_visibility=st.session_state.visibility,
                    disabled=st.session_state.disabled,
                    placeholder="Description",
                )
                today = datetime.date.today()
                first_date = st.date_input("Date de début", today )
                second_date = st.date_input("Date de fin", today)

                submitted = st.form_submit_button("Submit")
                if submitted:
                    self.add_agence(agence=agence_picker, category=category, title=title,
                               description=description, begin=first_date, end=second_date)


    def mark_card(self):
            colors = ["green", "yellow", "red"]

            longitudes = self.localisation["longitude"].to_list()
            latitudes = self.localisation["latitude"].to_list()
            agences = self.localisation["code_agence"].to_list()
            self.agences_name = agences
            counts, infos = request_db(agences, self.conn)
            marker_cluster = MarkerCluster().add_to(self.map_agencies)
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
                                    popup=folium.Popup(infos[agence], max_height=250, max_width=500))
                self.markers[agence] = counts[i]
                marker.add_to(marker_cluster)
            self.marker_cluster = marker_cluster            

    def draw_map(self):
        if len(self.markers) == 0:
            self.mark_card()
        # Display the map in Streamlit
        self.selection()              
        try:
            st_map = folium_static(self.map_agencies, width=850, height=850)
        except:
            print("Error rendering")
            print(traceback.format_exc())
 

@st.cache_resource()
def fetch_and_clean_data(_conn):
    geo_data = gpd.read_file("departements.geojson")
    query = f"SELECT * FROM Agences"
    localisation = pd.read_sql_query(query, _conn)
    return geo_data, localisation


@st.cache_resource(hash_funcs={folium.Map: lambda _: None})
def create_map(_geo_data):
    map = folium.Map(location=[46.5, 2.5], zoom_start=6, tiles='CartoDB positron')
    folium.GeoJson(_geo_data).add_to(map)
    folium.plugins.Fullscreen().add_to(map)
    return map

def main():

    with sqlite3.connect('planning.db', check_same_thread=False) as conn:
        cursor = conn.cursor()
        # Register the close_connection function to be called at exit
        geo_data, localisation = fetch_and_clean_data(conn)
        map_agency = create_map(geo_data)
        app = App(geo_data, conn, map_agency, cursor, localisation)


if __name__=="__main__":
    main()