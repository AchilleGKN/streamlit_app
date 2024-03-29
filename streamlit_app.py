import pandas as pd
import folium
import streamlit as st
from streamlit_folium import st_folium, folium_static
import geopandas as gpd
from folium.plugins import MarkerCluster
import sqlite3
import datetime
from jinja2 import Template
import traceback
from collections import Counter
import plotly.graph_objects as go

semesters = {"all":"all",
            "first":   datetime.datetime(1999, 1, 1),
            "second":   datetime.datetime(1999, 4, 1), 
            "third":    datetime.datetime(1999, 7, 1),
            "fourth":   datetime.datetime(1999, 10, 1)
            }

categ = ["DPT-Agence", "Projet-Commerce-Agence", "Projet-DPP-Agence",
        "Projet Contrôle de gestion", "Projet LTL-FTL", "Projet-DRC-Agence",
        "Projet-Ops-Agence"]

name_table = {'Catégorie':"categorie", "Titre":"titre_projet","Description":"descriptif", "Début": "date_debut","Fin":"date_fin", "Agence":"code_agence"}
@st.cache_data()
def init_data(_obj):
    marker_cluster = None
    markers = {}
    today = datetime.date.today()
    return today, marker_cluster, markers

def  init_session_state():
    if st.session_state.get('step') is None:
        st.session_state['step'] = 0
    
    if st.session_state.get("tmp") is None:
        st.session_state["tmp"] = "all"

    if st.session_state.get('semestre') is None:
        st.session_state["semestre"] = "all"
        
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
                    {{ key }} = {{ '?' }} {% if not loop.last %},{% endif %}
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
    cursor.execute(query)
    conn.commit()

def display_circular_chart(data):
    cnter = Counter(data)
    categ = list(cnter.keys())
    qtity = list(cnter.values())
    if len(categ) > 1:
        fig = go.Figure(data=[go.Pie(labels=categ, values=qtity, hole=.3)])
        st.plotly_chart(fig, use_container_width=True)
    return


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
    string = f"<b>Agence {name}</b><br>"
    string += f"Nombre de projets: {count} <br>"
    for row in rows:
        string += f"<br>{row[1]}: {row[2]}, {row[3]} <br>"
    return string

@st.cache_data()
def request_db(_agences, _conn, _condition):
    cursor = _conn.cursor()
    count = []
    dic_infos = {}
    for i in _agences:
        # Execute the SQL query to fetch agency information
        query = f"SELECT COUNT(*) FROM Projets WHERE code_agence = '{i}'" + _condition
        cursor.execute(query)
        project_count = cursor.fetchone()
        # Fetch the result
        if project_count is not None:
            try:
                project_count = project_count[0]
            # Print the result
            except Exception as e:
                print(e)
                project_count = 0
        else: project_count = 0
        count.append(project_count)
        sec_query = f"SELECT * FROM Projets WHERE code_agence = '{i}'" +  _condition
        cursor.execute(sec_query)
        rows = cursor.fetchall()
        dic_infos[i] = retrieve_information(rows,i, project_count)
    cursor.close()
    return count, dic_infos

class App():
    def __init__(self, geo_data, conn, map_agencies, cursor, localisation, year):
        self.geo_data = geo_data
        self.year = year
        self.conn = conn
        self.get_date()
        self.localisation = localisation
        self.cursor = cursor
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
        query = "insert into projets (categorie, titre_projet, descriptif, date_debut, date_fin, code_agence) values (?, ?, ?, ?, ?, ?)"
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
        begin = datetime.datetime.combine(begin, datetime.datetime.min.time())
        end = datetime.datetime.combine(end, datetime.datetime.min.time())

        self.submit(category, title, description, begin, end, agence)
        st.write(f":green[{title} ajoutée à l'agence {agence}]")
        st.rerun()

    def get_date(self):
        if st.session_state["semestre"] == "all":
            self.condition = ""
        if st.session_state["semestre"] == semesters["first"]:
            self.condition = "AND (strftime('%m', date_debut) < '04')"
        if st.session_state["semestre"] == semesters["second"]:
            self.condition = "AND (strftime('%m', date_debut) > '03' AND strftime('%m', date_debut) < '07')"
        if st.session_state["semestre"] == semesters["third"]:
            self.condition = "AND (strftime('%m', date_debut) > '06' AND strftime('%m', date_debut) < '10')"
        if st.session_state["semestre"] == semesters["fourth"]:
            self.condition = "AND (strftime('%m', date_debut) > '09' AND strftime('%m', date_debut) < '13')"

    def make_request(self, agence, project):
        time = 'where ' + self.condition[4:] if len(self.condition) > 1 else ""
        if agence == "Toutes les agences" and project == "Tous les projets" and self.time_interval == False:
            query = f"SELECT * FROM Projets {time}"
            rows = self.cursor.execute(query).fetchall()
        elif agence == "Toutes les agences" and project == "Tous les projets" and self.time_interval == True:
            query = f"SELECT * FROM Projets where date_debut >= ? and date_fin <= ?"
            rows = self.cursor.execute(query, (self.debut, self.fin)).fetchall()
        
        elif agence == "Toutes les agences" and self.time_interval == False:
            query = f"SELECT * FROM Projets where categorie = ?" + self.condition
            rows = self.cursor.execute(query, (project,)).fetchall()
        elif agence == "Toutes les agences" and self.time_interval == True:
            query = f"SELECT * FROM Projets where date_debut >= ? and date_fin <= ? and categorie = ?"
            rows = self.cursor.execute(query, (self.debut, self.fin, project)).fetchall()

        elif project == "Tous les projets" and self.time_interval == False:
            query = f"SELECT * FROM Projets where code_agence = ?" + self.condition
            rows = self.cursor.execute(query, ((str(agence), )) ).fetchall()
        elif project == "Tous les projets" and self.time_interval == True:
            query = f"SELECT * FROM Projets where date_debut >= ? and date_fin <= ? and code_agence = ?"
            rows = self.cursor.execute(query, (self.debut, self.fin, str(agence))).fetchall()

        elif self.time_interval == False:
            query = f"SELECT * FROM Projets where code_agence = ? and categorie=? " + self.condition
            rows = self.cursor.execute(query, (str(agence), project)).fetchall()
        else:
            query = f"SELECT * FROM Projets where code_agence = ? and categorie = ?  and date_debut >= ? and date_fin <= ?"
            rows = self.cursor.execute(query, (str(agence), project, self.debut, self.fin)).fetchall()
        return rows

    def display_editable_df(self, agence, project, col2):
        print(project)
        rows = self.make_request(agence, project)
        try:
            df = pd.DataFrame(rows, columns=['Index', 'Catégorie', 'Titre', 'Description', 'Début', 'Fin', "Agence"])
            cols = df.columns.tolist()
            # Reindex to have the last column first
            cols = [cols[-1]] + cols[:-1]
            df = df[cols]
            index = df["Index"]
            df = df.drop(columns=["Index"])
        except Exception as e:
            print(e)
            df = pd.DataFrame()
        st.session_state.updated_df = st.data_editor(df, num_rows="dynamic",  key="my_key", on_change=callback, args=[index, self.cursor, self.conn, self, agence])
        with col2:
            display_circular_chart(df["Catégorie"].to_list())

    def create_form(self):
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
            print("Semestre: ", st.session_state["semestre"])
            self.add_agence(agence=agence_picker, category=category, title=title,
                        description=description, begin=first_date, end=second_date)

    def selection(self):
        st.write("<b>Filtre</b>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns((0.5, 0.5, 1))

        with col1:
            agences = [i for i in self.agences_name]
            agences = list(sorted(agences))
            agences.insert(0, "Toutes les agences")
            chosen_agence = st.selectbox("Agence", agences)
        with col2:
            projects = list(sorted(categ))
            projects.insert(0, "Tous les projets")
            chosen_project = st.selectbox("Projet", projects)
        col1, col2 = st.columns((1, 0.5))
        with col1:
            if chosen_agence or chosen_project:
                self.display_editable_df(chosen_agence, chosen_project, col2)
        # Set the layout to a menu-like structure
        sidebar = st.sidebar
        # Create a form to add an agency
        with sidebar:
            st.write("Ajouter une tâche")
            with st.form("Ajouter une tâche"):
                self.create_form()

    def mark_card(self):
            colors = ["green", "yellow", "red"]
            longitudes = self.localisation["longitude"].to_list()
            latitudes = self.localisation["latitude"].to_list()
            agences = self.localisation["code_agence"].to_list()
            self.agences_name = agences
            counts, infos = request_db(agences, self.conn, self.condition)
            if self.marker_cluster != None:
                self.marker_cluster.remove_from(self.map_agencies)
            #marker_cluster = MarkerCluster().add_to(self.map_agencies)
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
                                        border_width=4)
                marker = folium.Marker(location=[y, x],
                                    icon=icon,
                                    id=f'marker-{i}',
                                    tooltip=f'Agence {agence}',
                                    popup=folium.Popup(infos[agence], max_height=250, max_width=500))
                if agence in self.markers:
                    self.markers[agence].remove_from(self.map_agencies)
                self.markers[agence] = counts[i]
                marker.add_to(self.map_agencies)
            #self.marker_cluster = marker_cluster            

    def select_periods(self, debut, fin):
        self.time_interval = True
        self.debut = datetime.datetime.combine(debut, datetime.datetime.min.time())
        self.fin = datetime.datetime.combine(fin, datetime.datetime.min.time())
        return

    def display_time(self):
        concordance_semesters = {f"Année {self.year}":"all", 
                                  "1er Trimestre":"first",
                                  "2ème Trimestre":"second",
                                  "3ème Trimestre":"third",
                                  "4ème Trimestre":"fourth"}
        col1, col2= st.columns((0.5, 1))
        with col1:
            chosen_periode = st.selectbox("Période", [x for x in concordance_semesters])
        if chosen_periode and st.session_state["tmp"] != chosen_periode:
            st.session_state["semestre"] = semesters[concordance_semesters[chosen_periode]]
            st.session_state["tmp"] = chosen_periode
            st.cache_data.clear()
            st.rerun()
        
    def draw_map(self):

        self.today, self.marker_cluster, self.markers = init_data(self)
        self.time_interval = False
        st.write("<b>Sélectionner un intervalle de date ou une période</b>", unsafe_allow_html=True)
        col_1, col_2, col_3 = st.columns((0.5, 0.5, 0.5))
        with col_1:
            debut = st.date_input("Début", self.today )
        with col_2:
            fin = st.date_input("Fin", self.today)
        with col_3:
            st.markdown("<br>", unsafe_allow_html=True)
            selectionner = st.button("Sélectionner")
        if selectionner:
            self.select_periods(debut, fin)
        self.display_time()
        if len(self.markers) == 0:
            self.mark_card()
        # Display the map in Streamlit
        self.selection()              
        try:
            st_map = folium_static(self.map_agencies, width=800, height=800)
            #st_map = st_folium(self.map_agencies, width=600, height=700)
        except:
            print("Error rendering")
            print(traceback.format_exc())

@st.cache_resource()
def fetch_and_clean_data(_conn):
    geo_data = gpd.read_file("departements.geojson")
    query = f"SELECT * FROM Agences"
    localisation = pd.read_sql_query(query, _conn)

    today = datetime.date.today()
    if today.month > 8:
        year = today.year
    else:
        year = today.year - 1
    return geo_data, localisation, year

@st.cache_resource(hash_funcs={folium.Map: lambda _: None})
def create_map(_geo_data):
    map = folium.Map(location=[46.5, 2.5], zoom_start=6, tiles='CartoDB positron')
    folium.GeoJson(_geo_data).add_to(map)
    folium.plugins.Fullscreen().add_to(map)
    return map

def main():
    init_session_state()
    st.set_page_config(layout="wide")

    with sqlite3.connect('planning.db', check_same_thread=False) as conn:
        cursor = conn.cursor()
        geo_data, localisation, year = fetch_and_clean_data(conn)
        map_agency = create_map(geo_data)
        app = App(geo_data, conn, map_agency, cursor, localisation, year)


if __name__=="__main__":
    main()