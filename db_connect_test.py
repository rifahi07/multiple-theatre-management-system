
import mysql.connector

def get_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Ippu@457.",
        database="movietheatre"
    )
    return connection
